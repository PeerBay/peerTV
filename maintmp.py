import httptorrent
import omxplayer
import stream
import web
#~ import remotekeyboard
#~ import remotemouse

import threading

urls = (
'^/stream/?(.*)$','Stream',
'^/standby/$','Standby',

)
omx_formats = omxplayer.FORMATS
fbi_formats= omxplayer.FBI_FORMATS
class Stream:
	def GET(self,url):
		stream=threading.Thread(target=startStream,args=(url,))
		stream.start()
		if url.find(".torrent")!=-1 or url.find("urn:btih:")!=-1 :
			return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
</head>
<body>
<a id="playOnTv"> Play on TV </a>
<a id="playHere"> Play here </a>
</body>
  <script src="https://code.jquery.com/jquery-1.10.2.min.js"></script>
<script> function ping(){
       var online
       $.ajax({
          url: 'http://peer.local:8000',
          success: function(result){
				offline=false
          },     
          error: function(result){
			   offline=true
          }
       });
		return online
    }function sleep(milliseconds) {
  var start = new Date().getTime();
  for (var i = 0; i < 1e7; i++) {
    if ((new Date().getTime() - start) > milliseconds){
      break;
    }
  }
}$("#playOnTv").click(function(){
		while(offline){
			sleep(2000)
			console.log("still sleeping")
		}
		window.location = "http://peer.local:8000"
})
</script>
</html>
"""		
		return url
class Standby:
	def GET(self):
		omxplayer.gallery()
		
def startStream(link):
	if link.split(".").pop()  in omx_formats:
		playing_video=omxplayer.omxplayer(str(link))
	elif link.split(".").pop()  in fbi_formats:
		shown_image= omxplayer.image(str(link))
	elif link.find(".torrent")!=-1 :
		httptorrent.serve_torrent(magnet=link)
	elif link.find("urn:btih:")!=-1:
		uri="magnet:?"+link
		httptorrent.serve_torrent(magnet=uri)
		
		playing_video=omxplayer.omxplayer("http://localhost:8000/"+httptorrent.path)	
	elif link.find(".pdf")!=-1:
		shown_pdf= omxplayer.pdf(str(link))
	else:
		playing_media=omxplayer.ytdl(link)	
		
if __name__ == "__main__":
	app = web.application(urls,globals())
	app.run()
					
