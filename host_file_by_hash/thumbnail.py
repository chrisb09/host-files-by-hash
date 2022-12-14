import os
from PIL import Image, ImageDraw, ImageFont

WIDTH = 300
HEIGHT = 300

#IMAGE_EXTENSIONS = [["bmp"],["cgm"],["g3"],["gif"],["ief"],["jpeg","jpg","jpe"],["ktx"],["png"],["btif"],["sgi"],["svg","svgz"],["tiff","tif"],["psd"],["uvi","uvvi","uvg","uvvg"],["djvu","djv"],["sub"],["dwg"],["dxf"],["fbs"],["fpx"],["fst"],["mmr"],["rlc"],["mdi"],["wdp"],["npx"],["wbmp"],["xif"],["webp"],["3ds"],["ras"],["cmx"],["fh","fhc","fh4","fh5","fh7"],["ico"],["jng"],["sid"],["bmp"],["pcx"],["pic","pct"],["pnm"],["pbm"],["pgm"],["ppm"],["rgb"],["tga"],["xbm"],["xpm"],["xwd"]]
IMAGE_EXTENSIONS = {'djvu','dxf','rgb','xpm','pcx','tga','pgm','ief','svgz','ppm','uvi','fbs','jpeg','ico','tiff','uvvi','ktx','pct','png','fh4','fst','webp','mdi','pic','gif','bmp','psd','wbmp','xif','pbm','jpg','wdp','npx','pnm','xwd','uvvg','jng','tif','cgm','uvg','btif','dwg','3ds','jpe','ras','sgi','fh7','svg','fh','xbm','sid','fpx','sub','rlc','fhc','djv','mmr','cmx','fh5','g3'}
#VIDEO_EXTENSIONS = [["3gp","3gpp"],["3g2"],["h261"],["h263"],["h264"],["jpgv"],["jpm","jpgm"],["mj2","mjp2"],["ts"],["mp4","mp4v","mpg4"],["mpeg","mpg","mpe","m1v","m2v"],["ogv"],["qt","mov"],["uvh","uvvh"],["uvm","uvvm"],["uvp","uvvp"],["uvs","uvvs"],["uvv","uvvv"],["dvb"],["fvt"],["mxu","m4u"],["pyv"],["uvu","uvvu"],["viv"],["webm"],["f4v"],["fli"],["flv"],["m4v"],["mkv","mk3d","mks"],["mng"],["asf","asx"],["vob"],["wm"],["wmv"],["wmx"],["wvx"],["avi"],["movie"],["smv"]]
VIDEO_EXTENSIONS = {'3g2','ogv','webm','avi','smv','m2v','viv','pyv','mpeg','h261','3gp','m1v','wm','asx','uvs','mov','uvh','mj2','ts','uvvp','mng','mks','fli','uvm','m4v','mk3d','mkv','jpgm','flv','uvv','wmx','mjp2','mpg4','uvvv','movie','jpgv','jpm','3gpp','fvt','mxu','m4u','f4v','qt','h263','mp4','uvu','uvp','dvb','wmv','wvx','uvvm','uvvu','mp4v','mpe','uvvh','asf','uvvs','mpg','vob','h264'}

def generate_thumbnail(input, output, verbose=False):
    width = str(WIDTH)
    height = str(HEIGHT)
    filename, file_extension = os.path.splitext(input)
    if file_extension[1:].lower() in VIDEO_EXTENSIONS:
        command = 'ffmpeg -hide_banner -loglevel error -y -i "'+input+'" -vf "thumbnail" -frames:v 1 -vf scale=w='+width+':h='+height+':force_original_aspect_ratio=decrease "'+output+'"'
        if verbose:
            print(command)
        os.system(command)
    elif file_extension[1:].lower() in IMAGE_EXTENSIONS:
        command = 'convert -thumbnail "'+width+'X'+height+'" "'+input+'"[0] "'+output+'"'
        if verbose:
            print(command)
        os.system(command)
    else:
        _create_generic_thumbnail(file_extension, output)

def _create_generic_thumbnail(text, path):

    img = Image.open("static/icon/undefined.png")

    text = text[:5]

    rotate = False
    position = (130-12*len(text), 120)

    if len(text) > 3:
        rotate = True
        position = (90-10*len(text), 70)
        
    if rotate:
        img = img.rotate(270)

    d = ImageDraw.Draw(img)
    d.text(position, text, fill=(0,0,0), font=ImageFont.truetype("static/font/OpenSans.ttf", size=96))

    if rotate:
        img = img.rotate(90)

    img.save(path)