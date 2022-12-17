from flask import Flask
from flask import render_template, url_for, send_file, redirect

from flask_redis import FlaskRedis
try:
    from mockredis import MockRedis
except ImportError as e:
    MockRedis = None

from host_file_by_hash.util import mstr, print_b
from host_file_by_hash.scanning import ScanThread, WaitForTimerThread, watch_files, check_existing_entries, set_wait_after_filechange

from threading import Event

import os, time, shutil, signal
from datetime import datetime

CONFIG_PATH = "config.py"

SOURCE_FILES = ["./data"] #temp

stop_flag = None

def signal_handler(sig, frame):
    if stop_flag is not None:
        stop_flag.set()
    exit()

signal.signal(signal.SIGINT, signal_handler)

if "CONFIG_PATH" in os.environ:
    CONFIG_PATH = os.environ["CONFIG_PATH"]
    print("Set config path: "+CONFIG_PATH)

if not os.path.exists("instance/"+CONFIG_PATH):
    print("Config file not found. Create one and use default config.")
    shutil.copyfile("host_file_by_hash/default_config.py", 'instance/config.py')


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile(CONFIG_PATH)

    set_wait_after_filechange(3)

    if "REDIS_URL" in os.environ:
        app.config['REDIS_URL'] = os.environ["REDIS_URL"]


    id = None

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
            wait_thread = WaitForTimerThread(stop_flag, redis_client, app.config["COLLECTIONS"])
            wait_thread.start()
            print("Cleaning up old entries")
            print("  Removed: "+str(check_existing_entries(redis_client, app.config["COLLECTIONS"])))
            print("Serving the following directories:")
            for collection in app.config["COLLECTIONS"]:
                for folder in app.config["COLLECTIONS"][collection]["paths"]:
                    watch_files(redis_client, collection, folder)
            scan_thread = ScanThread(redis_client, app.config["COLLECTIONS"])
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
        message = """<center><h1>There is no file with a corresponding hash available.</h1>
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
        message = """<center><h1>There is no file with a corresponding hash available.</h1>
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
                return redirect(url_for('thumbnails/sha1', sha1=list(members)[0]), code=302)
        if sha1 is not None:
            path = "thumbnails/"+sha1+".png"
            if os.path.exists(path):
                return send_file(path)
        return redirect(url_for("static", filename="/icon/undefined.png"), 302)

    @app.route('/<collection>/')
    def index(collection=None):
        if collection is None:
            return "", 404
        if not collection in app.config["COLLECTIONS"]:
            return "", 404
        
        start_time = time.time()
        count = 0
        text = ""
        for path in redis_client.smembers("coll:"+str(collection)):
            path = mstr(path)
            key = "path:"+path
            print(key)
            count += 1
            values = redis_client.lrange(key, 0, -1)
            if len(values) != 2:
                continue
            md5, sha1 = values
            md5 = mstr(md5)
            sha1 = mstr(sha1)
            path = mstr(key)[5:]
            #text += "<tr id='tr:"+sha1+"' class='file_entry' onmouseover='toggleThumbnail(event,\"tr:"+sha1+"\")'><td><a href='"+url_for('get_by_md5', md5=md5)+"' target='_blank'>"+md5+"</a></td><td><a href='"+url_for('get_by_sha1', sha1=sha1)+"' target='_blank'>"+sha1+"<a/></td><td>"+os.path.basename(path)+"</td><td>"+print_b(os.path.getsize(path))+"</td></tr>"
            text += "<tr id='tr:"+sha1+"' class='file_entry' onmouseover='toggleThumbnail(event,\"tr:"+sha1+"\")'><td><a href='sha1/"+sha1+"' target='_blank'>"+os.path.basename(path)+"<a/></td><td>"+print_b(os.path.getsize(path))+"</td></tr>"
        
        time_in_ms = int(1000*(time.time()-start_time))

        return render_template('index.html',
                                            index_js= "static/index.js",
                                            index_css="static/index.css",
                                            text=text,
                                            time_in_ms=time_in_ms,
                                            strftime=strftime,
                                            file_count=str(count)+" file"+("s" if count!=1 else ""))
    @app.route("/<collection>")
    @app.route("/<collection>/")
    @app.route("/<collection>/<var1>")
    @app.route("/<collection>/<var1>/<var2>")
    @app.route("/<collection>/<var1>/<var2>/<var3>")
    @app.route('/collection/<path:path>')
    def collection(collection, var1=None, var2=None, var3=None, path=None):
        if collection in app.config["COLLECTIONS"]:
            if var1 is not None:
                if var1 == "index":
                    return index(collection=collection)
                elif var1 == "md5":
                    return get_by_md5(md5=var2)
                elif var1 == "sha1":
                    return get_by_sha1(sha1=var2)
                elif var1 == "thumbnail":
                    m = None
                    if var2 == "md5":
                        m = var3
                    s = None
                    if var2 == "sha1":
                        s = var3
                    return thumbnail(md5=m, sha1=s)
                elif var1 == "static":
                    #print("Manual static server!!!")
                    p = "static"
                    if var2 is not None:
                        p = os.path.join(p, var2)
                    if var3 is not None:
                        p = os.path.join(p, var3)
                    if path is not None:
                        print(path)
                    #print(p)
                    #print(os.path.abspath(p))
                    return send_file(p)
            return redirect(url_for('index', collection=collection), code=302)
        return "", 404

        
    @app.route("/")
    def default():
        return "", 404

#    @app.errorhandler(404)
#    def page_not_found(error):
#        return redirect(url_for('index'), code=302)

    return app



def strftime():
    now = datetime.today()
    format="%d.%m.%Y %H:%M:%S"
    return now.strftime(format) 
