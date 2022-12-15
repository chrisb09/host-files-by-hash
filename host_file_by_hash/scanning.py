import time, os, re

from threading import Thread, Lock

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from host_file_by_hash.util import mstr
from host_file_by_hash.redis import remove_old_path
from host_file_by_hash.hashing import hash_md5, hash_sha1
from host_file_by_hash.thumbnail import generate_thumbnail

file_to_scan_lock = Lock()

files_to_scan = dict()
files_to_remove = dict()
watched_files = dict()


WAIT_AFTER_FILECHANGE = 10

def set_wait_after_filechange(value):
    WAIT_AFTER_FILECHANGE = value

class ScanThread(Thread):

    redis_client = None
    collections = None

    def __init__(self, redis_client, collections):
        Thread.__init__(self)
        self.redis_client = redis_client
        self.collections = collections

    def run(self):
        print("Scanning...")
        for collection in self.collections:
            print("  "+collection)
            for folder in self.collections[collection]["paths"]:
                print("    "+folder)
                scan_all(self.redis_client, folder, collection, self.collections, log=True)
        print("Scan done")

class WaitForTimerThread(Thread):

    redis_client = None
    collections = None

    def __init__(self, stop_flag, redis_client, collections):
        Thread.__init__(self)
        self.stopped = stop_flag
        self.redis_client = redis_client
        self.collections = collections

    def run(self):
        while not self.stopped.wait(0.5):
            ct = time.time()
            to_rem = list()
            file_to_scan_lock.acquire()
            try:
                for path in files_to_remove:
                    if files_to_remove[path][0] < ct:
                        to_rem.append(path)
                        if os.path.exists(path):
                            files_to_scan[path] = (ct + WAIT_AFTER_FILECHANGE, files_to_scan[path][1])
                        else:
                            remove_old_path(self.redis_client, path, files_to_scan[path][1])
                for path in to_rem:
                    del files_to_remove[path]
                to_rem = list()
                for path in files_to_scan:
                    if files_to_scan[path][0] < ct:
                        to_rem.append(path)
                        if os.path.exists(path):
                            scan_file(self.redis_client, path, files_to_scan[path][1], self.collections)
                for path in to_rem:
                    del files_to_scan[path]
            finally:
                file_to_scan_lock.release()


def watch_files(redis_client, collection, path):
    if not os.path.exists(path):
        os.makedirs(path)
    if os.path.exists(path):
        watched_files[path] = Observer()
        event_handler = Handler(redis_client, collection)
        watched_files[path].schedule(event_handler, path, recursive = True)
        watched_files[path].start()

class Handler(FileSystemEventHandler):

    redis_client = None
    collection = None

    def __init__(self, redis_client, collection) -> None:
        super().__init__()
        self.redis_client = redis_client
        self.collection = collection
    

    def on_created(self, event):
        if not event.is_directory:
            path = os.path.abspath(event.src_path)
            file_to_scan_lock.acquire()
            try:
                files_to_scan[path] = (time.time() + WAIT_AFTER_FILECHANGE, self.collection)
            finally:
                file_to_scan_lock.release()

    def on_modified(self, event):
        if not event.is_directory:
            path = os.path.abspath(event.src_path)
            file_to_scan_lock.acquire()
            try:
                files_to_scan[path] = (time.time() + WAIT_AFTER_FILECHANGE, self.collection)
            finally:
                file_to_scan_lock.release()

    def on_deleted(self, event):
        if not event.is_directory:
            file_to_scan_lock.acquire()
            try:
                path = os.path.abspath(event.src_path)
                files_to_remove[path] = (time.time() + WAIT_AFTER_FILECHANGE, self.collection)
            finally:
                file_to_scan_lock.release()

    def on_moved(self, event):
        if not event.is_directory:
            path = os.path.abspath(event.dest_path)
            file_to_scan_lock.acquire()
            try:
                files_to_scan[path] = (time.time() + WAIT_AFTER_FILECHANGE, self.collection)
                path = os.path.abspath(event.src_path)
                files_to_remove[path] = (time.time() + WAIT_AFTER_FILECHANGE, self.collection)
            finally:
                file_to_scan_lock.release()

def check_black_and_whitelist(path, collection, collections):
    whitelisted = len(collections[collection]["whitelist"]) == 0
    blacklisted = False
    for wl in collections[collection]["whitelist"]:
        if not re.search(wl, path) is None:
            whitelisted = True
            break
    for bl in collections[collection]["blacklist"]:
        if not re.search(bl, path) is None:
            blacklisted = True
            break
    return whitelisted and not blacklisted

def check_existing_entries(redis_client, collections):
    removed_count = 0
    for collection in collections:
        for path in redis_client.smembers("coll:"+str(collection)):
            if not check_black_and_whitelist(path, collection, collections):
                remove_old_path(redis_client, path, collection)
                removed_count += 1
    return removed_count

def scan_file(redis_client, path, collection, collections, use_cache=True):
    path = os.path.abspath(path)
    if check_black_and_whitelist(path, collection, collections):
        path_key = "path:"+path
        collection_key = "coll:"+str(collection)
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
        redis_client.sadd(collection_key, path)
        return (md5, sha1)
    return None


def scan_all(redis_client, path, collection, collections, use_cache=True, log=False):
    last_log = time.time() + 30
    count = 0
    for root, dirs, files in os.walk(path):
        for name in files:
            full_path = os.path.abspath(os.path.join(root, name))
            remove_old_path(redis_client, full_path, collection)
            scan_file(redis_client, full_path, collection, collections, use_cache=use_cache)
            count += 1
            if log and time.time() > last_log:
                last_log = time.time() + 30
                print("Scanning files complete to "+str(int(count*100//len(files)))+"%")