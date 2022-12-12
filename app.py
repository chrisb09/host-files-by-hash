from flask import Flask
from flask import render_template, url_for, send_file, request

from flask_redis import FlaskRedis
from mockredis import MockRedis

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from threading import Thread, Lock, Event

import os, hashlib, time, math, json

REDIS_HOST = "localhost"
REDIS_HOST_PORT = 6379
REDIS_HOST_PASSWORD = ""
REDIS_URL = "redis://:password@localhost:6379/0"
WAIT_AFTER_FILECHANGE = 3
SOURCE_FILES = '["data"]'


if "REDIS_HOST" in os.environ:
    REDIS_HOST = os.environ["REDIS_HOST"]
    print(REDIS_HOST)
if "REDIS_HOST_PORT" in os.environ:
    REDIS_HOST_PORT = os.environ["REDIS_HOST_PORT"]
if "REDIS_HOST_PASSWORD" in os.environ:
    REDIS_HOST_PASSWORD = os.environ["REDIS_HOST_PASSWORD"]
if "REDIS_URL" in os.environ:
    REDIS_URL = os.environ["REDIS_URL"]
if "WAIT_AFTER_FILECHANGE" in os.environ:
    WAIT_AFTER_FILECHANGE = float(os.environ["WAIT_AFTER_FILECHANGE"])
if "SOURCE_FILES" in os.environ:
    SOURCE_FILES = json.loads(os.environ['SOURCE_FILES'])

full_scan_lock = Lock()

files_lock = Lock()
files_to_scan = dict()
files_to_remove = dict()


watched_files = dict()

class WaitForTimerThread(Thread):

    redis_client = None

    def __init__(self, stop_flag, redis_client):
        Thread.__init__(self)
        self.stopped = stop_flag
        self.redis_client = redis_client

    def run(self):
        while not self.stopped.wait(0.5):
            files_lock.acquire()
            try:
                ct = time.time()
                to_rem = list()
                for path in files_to_remove:
                    if files_to_remove[path] < ct:
                        to_rem.append(path)
                        if os.path.exists(path):
                            print("File still exists :/ "+path)
                            files_to_scan[path] = ct + WAIT_AFTER_FILECHANGE
                        else:
                            print("Remove "+path)
                            remove_old_path(self.redis_client, path)
                for path in to_rem:
                    del files_to_remove[path]
                to_rem = list()
                for path in files_to_scan:
                    if files_to_scan[path] < ct:
                        to_rem.append(path)
                        if os.path.exists(path):
                            scan_file(self.redis_client, path)
                for path in to_rem:
                    del files_to_scan[path]
            finally:
                files_lock.release()

def print_b(filesize):
    endings = ["B","KB","MB","GB","TB","PB","EB"]
    index = int(math.log(filesize+1, 1000))
    return ("%.2f"% (filesize/float(10**(3*index)) ) ) + " "+endings[index]

def watch_files(redis_client, path):

    watched_files[path] = Observer()
    event_handler = Handler(redis_client)
    watched_files[path].schedule(event_handler, path, recursive = True)
    watched_files[path].start()

class Handler(FileSystemEventHandler):

    redis_client = None

    def __init__(self, redis_client) -> None:
        super().__init__()
        self.redis_client = redis_client
    

    def on_created(self, event):
        if not event.is_directory:
            files_lock.acquire()
            try:
                path = os.path.abspath(event.src_path)
                files_to_scan[path] = time.time() + WAIT_AFTER_FILECHANGE
            finally:
                files_lock.release()

    def on_modified(self, event):
        if not event.is_directory:
            files_lock.acquire()
            try:
                path = os.path.abspath(event.src_path)
                files_to_scan[path] = time.time() + WAIT_AFTER_FILECHANGE
            finally:
                files_lock.release()

    def on_deleted(self, event):
        if not event.is_directory:
            files_lock.acquire()
            try:
                path = os.path.abspath(event.src_path)
                files_to_remove[path] = time.time() + WAIT_AFTER_FILECHANGE
            finally:
                files_lock.release()

    def on_moved(self, event):
        if not event.is_directory:
            files_lock.acquire()
            try:
                path = os.path.abspath(event.dest_path)
                files_to_scan[path] = time.time() + WAIT_AFTER_FILECHANGE
                path = os.path.abspath(event.src_path)
                files_to_remove[path] = time.time() + WAIT_AFTER_FILECHANGE
            finally:
                files_lock.release()



def generic_hash(hash_f, fname):
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_f.update(chunk)
    return hash_f.hexdigest()

def hash_md5(fname):
    return generic_hash(hashlib.md5(), fname)

def hash_sha1(fname):
    return generic_hash(hashlib.sha1(), fname)

def scan_file(redis_client, path, use_cache=True):
    path = os.path.abspath(path)
    path_key = "path:"+path
    cache_key = "cache:"+path+":"+str(os.path.getsize(path))
    md5 = None
    sha1 = None
    scan = True
    if redis_client.exists(cache_key):
        scan = False
        values = redis_client.lrange(cache_key, 0, -1)
        if len(values) != 2:
            scan = True
        else:
            md5, sha1 = values
        #md5 = md5.decode("utf-8")
        #sha1 = sha1.decode("utf-8")
    if scan:
        md5 = hash_md5(path)
        sha1 = hash_sha1(path)
    md5_key  = "md5:" +md5
    sha1_key = "sha1:"+sha1
    redis_client.sadd(md5_key, path)
    redis_client.sadd(sha1_key, path)
    redis_client.delete(path_key)
    redis_client.rpush(path_key, md5)
    redis_client.rpush(path_key, sha1)
    redis_client.delete(cache_key)
    redis_client.rpush(cache_key, md5)
    redis_client.rpush(cache_key, sha1)
    return (md5, sha1)

def delete_redis_set_if_empty(redis_client, key):
    if redis_client.exists(key) and redis_client.scard(key) == 0:
        redis_client.delete(key)

def remove_old_path(redis_client, full_path):
    path_key = "path:"+full_path
    size_key = "size:"+full_path
    if redis_client.exists(path_key):
        values = redis_client.lrange(path_key, 0, -1)
        for i in range(0,len(values)//2):
            md5 = values[2*i]
            sha1 = values[2*i+1]
            #md5 = md5.decode("utf-8")
            #sha1 = sha1.decode("utf-8")
            redis_client.srem("md5:"+md5, full_path)
            redis_client.srem("sha1:"+sha1, full_path)
            delete_redis_set_if_empty(redis_client, "md5:"+md5)
            delete_redis_set_if_empty(redis_client, "sha1:"+sha1)
        redis_client.delete(path_key)
        redis_client.delete(size_key)


def scan_all(redis_client, path, use_cache=True, log=False):
    last_log = time.time() + 30
    count = 0
    for root, dirs, files in os.walk(path):
        for name in files:
            full_path = os.path.abspath(os.path.join(root, name))
            remove_old_path(redis_client, full_path)
            scan_file(redis_client, full_path, use_cache=use_cache)
            count += 1
            if log and time.time() > last_log:
                last_log = time.time() + 30
                print("Scanning files complete to "+str(int(count*100//len(files)))+"%")
        

def get_all_args(args):
    d = dict()
    for e in args.lists():
        d[e[0]] = e[1]
    return d




def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping()
    app.config['REDIS_HOST'] = REDIS_HOST
    app.config['REDIS_PORT'] = REDIS_HOST_PORT
    app.config['REDIS_DB'] = 0
    app.config['REDIS_PASSWORD'] = REDIS_HOST_PASSWORD
    app.config['REDIS_URL'] = REDIS_URL

    if app.testing:
        print("Testing")
        redis_client = FlaskRedis.from_custom_provider(MockRedis)
    else:
        print("Production")
        redis_client = FlaskRedis(app, decode_responses=True)
    redis_client.init_app(app)


    stop_flag = Event()
    wait_thread = WaitForTimerThread(stop_flag, redis_client)
    wait_thread.start()


    if full_scan_lock.acquire(blocking=False):
        try:
            print("Serving the following directories:")
            for sf in SOURCE_FILES:
                print("  "+sf)
                watch_files(redis_client, sf)
                scan_all(redis_client, sf, log=True)
            print("All done")
        finally:
            full_scan_lock.release()
    else:
        full_scan_lock.acquire()
        full_scan_lock.release()

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    @app.route('/md5/<md5>')
    def get_by_md5(md5=None):
        message = """<center><h1>There is no file with a corresponding hash available.</h1></br>
                    <h2>You can find a list <a href='"""+url_for('index')+"""'>here</a>.</h2>
                    </center> 
                    """
        if md5 is None:
            return message
        key = "md5:"+md5
        if redis_client.exists(key):
            filename = redis_client.sscan(key)[1][0]
            return send_file(filename)
        return message

    @app.route('/sha1/<sha1>')
    def get_by_sha1(sha1=None):
        message = """<center><h1>There is no file with a corresponding hash available.</h1></br>
                    <h2>You can find a list <a href='"""+url_for('index')+"""'>here</a>.</h2>
                    </center> 
                    """
        if sha1 is None:
            return message
        key = "sha1:"+sha1
        if redis_client.exists(key):
            filename = redis_client.sscan(key)[1][0]
            return send_file(filename)
        return message

    # a simple page that says hello
    @app.route('/file')
    def file():
        md5 = request.args.get('md5')
        sha1 = request.args.get('sha1')
        args = get_all_args(request.args)
        if "md5" in args:
            for m in args["md5"]:
                key = "md5:"+m
                if redis_client.exists(key):
                    filename = redis_client.sscan(key)[1][0]#.decode("utf-8")
                    return send_file(filename)
        if "sha1" in args:
            for m in args["sha1"]:
                key = "sha1:"+m
                if redis_client.exists(key):
                    filename = redis_client.sscan(key)[1][0]#.decode("utf-8")
                    return send_file(filename)
        print(args)
        return "<center><h1>There is no file with a corresponding hash available.</h1><center>"

    @app.route('/index')
    def index():
        text = """
        <html>
            <head>
                <style>
                    .styled-table {
                        border-collapse: collapse;
                        margin: 25px 0;
                        font-size: 0.9em;
                        font-family: sans-serif;
                        min-width: 400px;
                        box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
                        max-width: 25%;

                    }
                    .styled-table thead tr {
                        background-color: #00F879;
                        color: #ffffff;
                        text-align: left;
                    }
                    .styled-table th,
                    .styled-table td {
                        padding: 12px 15px;
                    }
                    .styled-table tbody tr {
                        border-bottom: 1px solid #dddddd;
                    }

                    .styled-table tbody tr:nth-of-type(even) {
                        background-color: #f3f3f3;
                    }

                    .styled-table tbody tr:last-of-type {
                        border-bottom: 2px solid #009879;
                    }
                    .styled-table tbody tr.active-row {
                        font-weight: bold;
                        color: #009879;
                    }
                    a,a:visited,a:hover,a:active{
                        -webkit-backface-visibility:hidden;
                                backface-visibility:hidden;
                        position:relative;
                        text-decoration:none;
                        color:black;
                    }
                    a:hover{
                        color:#DE3163;
                    }

                </style>
            </head>
            <body>
                <center>
                <table class="styled-table">
                    <tr>
                        <td>MD5</td>
                        <td>SHA1</td>
                        <td>Name</td>
                        <td>Size</td>
                    </tr>"""
        for key in redis_client.scan_iter("path:*"):
            values = redis_client.lrange(key, 0, -1)
            if len(values) != 2:
                print(key)
                print("too many entries:")
                print(values)
                continue
            md5, sha1 = values
            #md5 = md5.decode("utf-8")
            #sha1 = sha1.decode("utf-8")
            path = key[5:]#.decode("utf-8")[5:]
            text += "<tr><td><a href='"+url_for('get_by_md5', md5=md5)+"' target='_blank'>"+md5+"</a></td><td><a href='"+url_for('get_by_sha1', sha1=sha1)+"' target='_blank'>"+sha1+"<a/></td><td>"+os.path.basename(path)+"</td><td>"+print_b(os.path.getsize(path))+"</td><td></tr>"

            print(key)

        text += "</table></center>"
        #print(redis_client.get('index'))
        #redis_client.set('potato', '"zoomer boomer jet DANGER ZONE.webm"')
        #print(redis_client.get('potato'))
        return text

    return app
