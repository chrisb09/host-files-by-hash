
let popup = null;
let thumbnail = null;
let previous = null;

function toggleThumbnail(e, element) {
    popup = document.getElementById("thumbnail");
    thumbnail = document.getElementById("thumbnail_image")
    thumbnail_id = element.substring(3)
    if (previous == null || thumbnail_id != previous) {
        previous = thumbnail_id;
        thumbnail.src = "thumbnail/sha1/"+thumbnail_id+"";
        x=e.clientX;
        y=e.clientY;
        var rect = e.target.getBoundingClientRect();
        y = parseInt((rect.top + rect.bottom) / 2) + window.scrollY;


        popup.style.top=Math.min(window.scrollY+screen.height-150, Math.max(150, y))+'px';
        popup.style.left='200px';
        popup.style.visibility = "visible";
    }

}

document.documentElement.addEventListener('mouseleave', loseFocus());

function loseFocus() {
    if (popup != null)
        popup.style.visibility = "hidden";
    previous = null;
}

function on_thumbnail_click() {
    if (previous != null) {
        window.open('sha1/'+previous, '_blank').focus();
    }
}


window.onmousemove = function (e) {
    var x = e.clientX,
        y = e.clientY;
    t = e.target
    //console.log(e.target)
    //console.log(t.tagName)
    remove = true
    if (t != null ) {
        if (t.tagName == "A" && t.parentNode.tagName == "TD" &&
            t.parentNode.parentNode.tagName == "TR" &&
            t.parentNode.parentNode.classList.contains("file_entry")){
                remove = false
        }
        else if (t.tagName == "TD" && t.parentNode.tagName == "TR" &&
            t.parentNode.classList.contains("file_entry")){
                remove = false
        }
        else if (t.tagName == "TR" && t.classList.contains("file_entry")){
                remove = false
        }
        else if (t.id != null){
            if (t.id == "thumbnail"){
                remove = false
            }
            else if (t.id == "thumbnail_image"){
                remove = false
            }
        }
    }
    if (remove) {
        loseFocus()
    }
    //<tr id='tr:"+sha1+"' onmouseover='toggleThumbnail(event,\"tr:"+sha1+"\")'><td><a href='"+url_for('get_by_md5', md5=md5)+"' target='_blank'>"+md5+"</a></td><td><a href='"+url_for('get_by_sha1', sha1=sha1)+"' target='_blank'>"+sha1+"<a/></td><td>"+os.path.basename(path)+"</td><td>"+print_b(os.path.getsize(path))+"</td></tr>"
    
};
