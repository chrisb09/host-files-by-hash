

from host_file_by_hash.util import mstr

def delete_redis_set_if_empty(redis_client, key):
    if redis_client.exists(key) and redis_client.scard(key) == 0:
        redis_client.delete(key)

def remove_old_path(redis_client, full_path, collection):
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
    collection_key = "coll:"+str(collection)
    redis_client.srem(collection_key, full_path)