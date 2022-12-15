import math

def mstr(x): #converts bytes to string only if x is bytes
    if type(x) == type(bytes()):
        return x.decode("utf-8")
    return x


def print_b(filesize):
    endings = ["B","KB","MB","GB","TB","PB","EB"]
    index = int(math.log(filesize+1, 1000))
    return ("%.2f"% (filesize/float(10**(3*index)) ) ) + " "+endings[index]