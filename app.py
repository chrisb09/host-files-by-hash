from flask import Flask
from flask import render_template, url_for, send_file, request, redirect

from flask_redis import FlaskRedis
try:
    from mockredis import MockRedis
except ImportError as e:
    MockRedis = None

from host_file_by_hash import thumbnail

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from threading import Thread, Lock, Event

import os, hashlib, time, math, json, signal
from datetime import datetime

REDIS_URL = "redis://:password@localhost:6379/0"
WAIT_AFTER_FILECHANGE = 3
SOURCE_FILES = ["data"]

stop_flag = None

def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    stop_flag.set()
    exit()

def mstr(x): #converts bytes to string only if x is bytes
    if type(x) == type(bytes()):
        return x.decode("utf-8")
    return x

signal.signal(signal.SIGINT, signal_handler)

if "REDIS_URL" in os.environ:
    REDIS_URL = os.environ["REDIS_URL"]
if "WAIT_AFTER_FILECHANGE" in os.environ:
    WAIT_AFTER_FILECHANGE = float(os.environ["WAIT_AFTER_FILECHANGE"])
if "SOURCE_FILES" in os.environ:
    SOURCE_FILES = json.loads(os.environ['SOURCE_FILES'])

full_scan_lock = Lock()

files_to_scan = dict()
files_to_remove = dict()


watched_files = dict()

class ScanThread(Thread):

    redis_client = None
    folders = None

    def __init__(self, redis_client, folders):
        Thread.__init__(self)
        self.redis_client = redis_client
        self.folders = folders

    def run(self):
        for folder in self.folders:
            scan_all(self.redis_client, folder, log=True)
        print("Scan done")

class WaitForTimerThread(Thread):

    redis_client = None

    def __init__(self, stop_flag, redis_client):
        Thread.__init__(self)
        self.stopped = stop_flag
        self.redis_client = redis_client

    def run(self):
        while not self.stopped.wait(0.5):
            ct = time.time()
            to_rem = list()
            for path in files_to_remove:
                if files_to_remove[path] < ct:
                    to_rem.append(path)
                    if os.path.exists(path):
                        files_to_scan[path] = ct + WAIT_AFTER_FILECHANGE
                    else:
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

def print_b(filesize):
    endings = ["B","KB","MB","GB","TB","PB","EB"]
    index = int(math.log(filesize+1, 1000))
    return ("%.2f"% (filesize/float(10**(3*index)) ) ) + " "+endings[index]

def watch_files(redis_client, path):
    if not os.path.exists(path):
        os.makedirs(path)
    if os.path.exists(path):
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
            path = os.path.abspath(event.src_path)
            files_to_scan[path] = time.time() + WAIT_AFTER_FILECHANGE()

    def on_modified(self, event):
        if not event.is_directory:
            path = os.path.abspath(event.src_path)
            files_to_scan[path] = time.time() + WAIT_AFTER_FILECHANGE

    def on_deleted(self, event):
        if not event.is_directory:
                path = os.path.abspath(event.src_path)
                files_to_remove[path] = time.time() + WAIT_AFTER_FILECHANGE

    def on_moved(self, event):
        if not event.is_directory:
            path = os.path.abspath(event.dest_path)
            files_to_scan[path] = time.time() + WAIT_AFTER_FILECHANGE
            path = os.path.abspath(event.src_path)
            files_to_remove[path] = time.time() + WAIT_AFTER_FILECHANGE



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
        md5 = mstr(md5)
        sha1 = mstr(sha1)
    if scan:
        print(path)
        md5 = hash_md5(path)
        sha1 = hash_sha1(path)
        generate_thumbnail(path, sha1)
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
            md5 = mstr(md5)
            sha1 = mstr(sha1)
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
    # thumbnail.close_unoserver()
        

def get_all_args(args):
    d = dict()
    for e in args.lists():
        d[e[0]] = e[1]
    return d




def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping()
    app.config['REDIS_URL'] = REDIS_URL

    id = None
    if "TESTING" in os.environ:
        print("TESTING")
        app.config["TESTING"] = bool(os.environ["TESTING"])

    if app.testing:
        if MockRedis is None:
            print("MockRedis not found!")
            exit()
        redis_client = FlaskRedis.from_custom_provider(MockRedis)
        redis_client.init_app(app)
    else:
        redis_client = FlaskRedis(app, decode_responses=True)
        try:
            redis_client.init_app(app)
            r = redis_client.ping()
        except Exception:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("Redis-Database connection not found!")
            print("Using mockredis database. All scanned data is not persistent!")
            if MockRedis is None:
                print("MockRedis not found!")
                exit()
            redis_client = FlaskRedis.from_custom_provider(MockRedis)
            redis_client.init_app(app)

    if redis_client.setnx("master", 0):
        try:
            print("Wait 1s for other workers to realize they aren't the master")
            time.sleep(1)
            redis_client.delete("id")
            id = redis_client.incr("id", amount=0)

            redis_client.set("clients", 1)
            redis_client.delete("master")

            print("Initial Worker-"+str(id)+" started.")
            global stop_flag
            stop_flag = Event()
            wait_thread = WaitForTimerThread(stop_flag, redis_client)
            wait_thread.start()
            print("Serving the following directories:")
            for sf in SOURCE_FILES:
                print("  "+sf)
                watch_files(redis_client, sf)
            scan_thread = ScanThread(redis_client, SOURCE_FILES)
            scan_thread.start()
            print("Initial worker-"+str(id)+" started subsequent tasks.")
        finally:
            time.sleep(1)
            redis_client.delete("master")
        time.sleep(3)
        redis_client.delete("clients")
    else:
        while id is None:
            time.sleep(0.1)
            if redis_client.exists("clients"):
                id = redis_client.incr("id")
        print("Worker-"+str(id)+" started.")

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
            filename = mstr(redis_client.sscan(key)[1][0])
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
            filename = mstr(redis_client.sscan(key)[1][0])
            return send_file(filename)
        return message

    @app.route("/thumbnail/md5/<md5>")
    @app.route("/thumbnail/sha1/<sha1>")
    def thumbnail(md5=None, sha1=None):
        if md5 is None and sha1 is None:
            return "", 404
        if md5 is not None:
            #redis_client.sadd(md5_key, path)
            key = "md5:"+str(md5)
            if redis_client.exists(key):
                members = redis_client.smembers(key)
                print(members)
                return redirect(url_for('thumbnails/sha1', sha1=list(members)[0]), code=302)
        if sha1 is not None:
            path = "thumbnails/"+sha1+".png"
            if os.path.exists(path):
                return send_file(path)
        return redirect(url_for('static', filename="icon/undefined.png"), 302)

    @app.route('/index')
    def index():
        start_time = time.time()
        count = 0
        text = ""
        for key in redis_client.scan_iter("path:*"):
            count += 1
            values = redis_client.lrange(key, 0, -1)
            if len(values) != 2:
                continue
            md5, sha1 = values
            md5 = mstr(md5)
            sha1 = mstr(sha1)
            path = mstr(key)[5:]
            text += "<tr id='tr:"+sha1+"' class='file_entry' onmouseover='toggleThumbnail(event,\"tr:"+sha1+"\")'><td><a href='"+url_for('get_by_md5', md5=md5)+"' target='_blank'>"+md5+"</a></td><td><a href='"+url_for('get_by_sha1', sha1=sha1)+"' target='_blank'>"+sha1+"<a/></td><td>"+os.path.basename(path)+"</td><td>"+print_b(os.path.getsize(path))+"</td></tr>"

        
        time_in_ms = int(1000*(time.time()-start_time))

        index_js = app.url_for('static', filename='index.js')
        index_css = app.url_for('static', filename='index.css')
        return render_template('index.html',
                                            index_js=index_js,
                                            index_css=index_css,
                                            text=text,
                                            time_in_ms=time_in_ms,
                                            strftime=strftime,
                                            file_count=str(count)+" file"+("s" if count!=1 else ""))
    @app.route("/")
    def default():
        return redirect(url_for('index'), code=302)

    @app.errorhandler(404)
    def page_not_found(error):
        return redirect(url_for('index'), code=302)

    return app



def strftime():
    now = datetime.today()
    format="%d.%m.%Y %H:%M:%S"
    return now.strftime(format) 

def generate_thumbnail(path, hash_value):
    if not os.path.exists("thumbnails"):
        os.makedirs("thumbnails")
    options = {
        'trim': False,
        'height': 300,
        'width': 300,
        'quality': 85,
        'thumbnail': False
    }
    return thumbnail.generate_thumbnail(path, 'thumbnails/'+hash_value+'.png', verbose=True)