import hashlib

def generic_hash(hash_f, fname):
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_f.update(chunk)
    return hash_f.hexdigest()

def hash_md5(fname):
    return generic_hash(hashlib.md5(), fname)

def hash_sha1(fname):
    return generic_hash(hashlib.sha1(), fname)