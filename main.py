#!/usr/bin/python
import subprocess
import time
import re
import web
import os
import shutil
import pipes
import string
import threading
import libtorrent as lt
import sys
import youtube_dl
from json import loads
import requests
import couchdb
import lib.astralradio as astralradio
import lib.streamtheworld as streamtheworld
import lib.tunein as tunein
from uuid import getnode as get_mac
import unicodedata
import urllib2
import dbus
from subprocess import Popen
from BeautifulSoup import BeautifulSoup
import guessit
import urllib
import HTMLParser
import subdown 
import gzip
import omxcon
global ses,handles,tor
import sys
import omxcon
import pexpect
import urllib
import bittorrent2player as bit
_FILE_INFO_CMD = '/usr/bin/omxplayer -i "%s"'


play=True
duration =None
seconds_per_piece=7
paused=True
playing_video=None
playing_time=0
omx_time=0

handles=[]	
streamfolder="/home/pi/streams/"
cmd = "omxplayer -o hdmi -b  %s %s"
couch = couchdb.Server()
streams=couch["streams"]
magnets=couch["magnets"]
tunes=couch["tunes"]
tor={}

htmlParser = HTMLParser.HTMLParser()
urls = (
'^/image/?(.*)$','Image',
'^/upload', 'Upload',
'^/$','Interface',
'^/magnet/?(.*)$','Magnet',
'^/qmagnet/?(.*)$','qMagnet',
'^/channel/?(.*)$','Channel',
'^/stream/?(.*)$','Stream',
'^/serve/?(.*)$','Serve',
'^/searchtune/?(.*)$','searchTunes',
'^/selectTune/?(.*)$','selectTune',
'^/omx/?(.*)$/?(.*)$','omxCMD',
'^/stop$','stopMagnet',
'^/progress$','magnetProgress',
'^/shutdown$','Shutdown',
'^/play/(.*)$','Play',
'^/restart','Restart',
'^/playlist/?(.*)$','Playlist',
'^/([^/]*)$','Other'
)
state_str = ['queued', 'checking', 'downloading metadata', \
	'downloading', 'finished', 'seeding', 'allocating', 'checking fastresume']

PLAYABLE_TYPES = ['.264','.avi','.bin','.divx','.f4v','.h264','.m4e','.m4v','.m4a','.mkv','.mov','.mp4','.mp4v','.mpe','.mpeg','.mpeg4','.mpg','.mpg2','.mpv','.mpv2','.mqv','.mvp','.ogm','.ogv','.qt','.qtm','.rm','.rts','.scm','.scn','.smk','.swf','.vob','.wmv','.xvid','.x264','.mp3','.flac','.ogg','.wav', '.flv', '.mkv']
MEDIA_RDIR = '../movies'
PAGE_FOLDER = 'omxfront/'
PAGE_NAME = 'interface.htm'
OMXIN_FILE='omxin'
play_list = []
playable={}

class Upload:
    def GET(self):
        return """<html><head></head><body>
<form method="POST" enctype="multipart/form-data" action="">
<input type="file" name="myfile" />
<br/>
<input type="submit" />
</form>
</body></html>"""

    def POST(self):
        x = web.input(myfile={})
        web.debug(x['myfile'].filename) # This is the filename
        web.debug(x['myfile'].value) # This is the file contents
        web.debug(x['myfile'].file.read()) # Or use a file(-like) object
        raise web.seeother('/upload')

class Serve:
	def GET(self,file):
		print file
		fileid=file.rsplit("/",1)[0]
		magnet=magnets[fileid]
		playable[magnet["link"]]=False
		magnetthread=threading.Thread(target=startMagnet,args=(magnet["link"],))
		raise web.redirect("/static/"+file)
class omxCMD:
	def GET(self,cmd,idx=None):
		global playingvideo
		#~ if playingvideo==None:
			#~ return {"error":"no playing video"}
		if cmd=="pause" or cmd=="play":
			return playingvideo.Play()
		elif cmd=="fseek":
			return playingvideo.Seek(30)
		elif cmd=="bseek":
			return 	playingvideo.Seek(-30)
		elif cmd=="stop":
			stop=playingvideo.Stop()
			playingvideo=None
			return stop
		elif cmd=="mute":
			return playingvideo.Mute()		
		elif cmd=="lfseek":
			return playingvideo.Next()
		elif cmd=="lbseek":
			return 	playingvideo.Previous()
		elif cmd=="listsubs":
			return playingvideo.ListSubs()
		elif cmd=="selectsub":
			return playingvideo.SelectSub(idx)		
class Other:
	def GET(self,name):
		return '[{\"message\":\"OK\"}]'
class Channel:
	def GET(self,url):

		channel=threading.Thread(target=saveChannel,args=(url,))
		channel.start()
		return url 
class Stream:
	def GET(self,url):
		
		stream=threading.Thread(target=startStream,args=(url,))
		stream.start()
		return url 
class Image:
	def GET(self,url):
		subprocess.Popen('killall fbi',shell=True)
		image=threading.Thread(target=startImage,args=(url,))
		image.start()
		return url 
class searchTunes:
	def GET(self,term):
		termsearch=threading.Thread(target=tuneSearch,args=(term,))
		termsearch.start()
		return term
class selectTune:
	def GET(self,tune):
		return tune		   
class stopMagnet:
	def GET(self):
		global deleted
		deleted=True
		return "deleted"
class magnetProgress:
	def GET(self):
		return s.progress		
class Play:
	def GET(self,fileid):
		global deleted , playable
		deleted=False
		magnet=magnets[fileid]
		set_subtitles=""
		#~ if "subs" in magnet["htmlmovie"]:
			#~ for i in magnet["htmlmovie"]["subs"]:
				#~ set_subtitles=set_subtitles+" "+i["subpath"].replace("(","\(").replace(")","\)").replace(" ","\ ")
		playable[magnet["link"]]=False
		magnetthread=threading.Thread(target=startMagnet,args=(magnet["link"],))
		magnetthread.start()
		return {"wait":1}
class PlayStream:
	def GET(self,link):
		stream=streams[link]
		url=web.webapi.urllib.unquote(url)
		stream=threading.Thread(target=startStream,args=(url,))
		stream.start()	
		return omxplay(stream["htmlmovie"]["path"])
class Magnet:
	def GET(self,uri):
		uri="magnet:?"+uri
		print uri
		global deleted
		deleted=False
		magnet=threading.Thread(target=startMagnet,args=(uri,))
		magnet.start()
		return "ok"
class qMagnet:
	def GET(self,uri):
		uri="magnet:?"+uri
		print uri
		global deleted
		deleted=False
		magnet=threading.Thread(target=qmagnet,args=(uri,))
		magnet.start()
				
class Shutdown:
	def GET(self):
		subprocess.call('/sbin/shutdown -h now',shell=True)
		return '[{\"message\":\"OK\"}]'

class Interface:
	def GET(self):
		page_file = open(os.path.join(PAGE_FOLDER,PAGE_NAME),'r')
		page = page_file.read()
		page_file.close()
		web.header('Content-Type', 'text/html')
		return page

class Restart:
	def GET(self):
		omx_restart()
		return "ok"
class Path:
	def GET(self, path=''):
		itemlist = []
		if path.startswith('..'):
			path = ''
		for item in os.listdir(os.path.join(MEDIA_RDIR,path)):
			if os.path.isfile(os.path.join(MEDIA_RDIR,path,item)):
				fname = os.path.splitext(item)[0]
				fname = re.sub('[^a-zA-Z0-9\[\]\(\)\{\}]+',' ',fname)
				fname = re.sub('\s+',' ',fname)
				fname = string.capwords(fname.strip())
				singletuple = (os.path.join(path,item),fname,'file')
			else:
				fname = re.sub('[^a-zA-Z0-9\']+',' ',item)
				fname = re.sub('\s+',' ',fname)
				fname = string.capwords(fname.strip())
				singletuple = (os.path.join(path,item),fname,'dir')
			itemlist.append(singletuple)
		itemlist = [f for f in itemlist if not os.path.split(f[0])[1].startswith('.')]
		itemlist = [f for f in itemlist if os.path.splitext(f[0])[1].lower() in PLAYABLE_TYPES or f[2]=='dir']
		list.sort(itemlist, key=lambda alpha: alpha[1])
		list.sort(itemlist, key=lambda dirs: dirs[2])
		outputlist=[]
		for line in itemlist:
			outputlist.append('{\"path\":\"'+line[0]+'\", \"name\":\"'+line[1]+'\", \"type\":\"'+line[2]+'\"}')
		return '[\n'+',\n'.join(outputlist)+']'

#This class is not complete yet and only populates the global playlist.
#TO-DO
class Playlist:
   def GET(self, item=''):
	   f = open('/var/local/omxplay', 'r')
	   return f

if __name__ == "__main__":
	app = web.application(urls,globals())
	app.run()
	

def omx_restart():
	subprocess.Popen('killall omxplayer.bin',shell=True)
	
def omx_send(command):
	print command
	pos=dbusIfaceProp.Position
	dbusIfaceKey.Action(dbus.Int32(command))
	if command=="15":
		for t in tor:
			tor[t]=False

def omx_play(file,link,subs):
	opts=""
	if subs!="":
		opts=" --align center --subtitles "+subs
	moviefile=file.replace("(","\(").replace(")","\)").replace(" ","\ ")
	
	global object , dbusIfaceProp ,dbusIfaceKey ,playable
	try:
		dbusIfaceKey.Action(dbus.Int32(15))
	except:
		print "no dbus "
	while not playable[link]:
		print "waiting playable"
		time.sleep(5) 
		if tor[link]==False:
			print "movie  stopped" + file
			playable={}	
			return "stopped"
	playable={}	
	return  {"duration":dbusIfaceProp.Duration(),"position":dbusIfaceProp.Position()}
def get_pieces(start, end,seconds_per_piece):
	j=1
	print " from %d to %d " % (start,end) ,
	sys.stdout.flush()
	for i in xrange(start,end):
		h.piece_priority(i,7)
def startMagnet(link):
	bit.serve_torrent(magnet=link)
	return
	
	global s , ses ,handles, tor ,playingvideo
	print link
	found=False
	seconds_per_piece=7
	print handles
	if link in handles:
		return "its running"
	else:	
		for handle in handles:
			print handle
			handles[handle].save_resume_data()
			tor={}
			ses.remove_torrent(handles[handle])
	tor[link]= True		
	handles={}
	handles[link] = lt.add_magnet_uri(ses, str(link), params)		
	h=handles[link]
	print "searching metadata.wait!"
	while (not h.has_metadata()):
		time.sleep(.1)

	if found==False:
		print handles		
	info = h.get_torrent_info()
	piecestart,pieceend,piece_length,video=find_offsets(info)
	prio=h.piece_priorities()
	add_pieces=4	
	start=piecestart
	end=piecestart+add_pieces
	
	#~ print h.piece_priorities()
	h.set_sequential_download(True)		
	state_str = ['queued', 'checking', 'downloading metadata', \
	'downloading', 'finished', 'seeding', 'allocating', 'checking fastresume']


	
	#~ prio=h.piece_priorities()
	#~ for i in xrange(len(prio)):
		#~ h.piece_priority(i,1)
	#~ print prio
	playing=False
	movie = {}
	try:
		movie['title'] = video_info["title"]
		movie['year'] = video_info["year"]
		movie['quality'] = video_info["format"]
		movie['suffix'] = video_info["mimetype"]
	except:	
		movie['title'] = h.name()
	magnet={}
	subtitles=""
	if h.name() not in magnets:
		movie["path"]="/home/pi/movies/"+video
		
		movie=fillInFromOmdb(movie)
		
		magnet["htmlmovie"]=movie
		magnet["link"]=link
		print 'saved : ', h.name()
	else:
		magnet=magnets[h.name()]
	b=False		
	if "subs" not in magnet["htmlmovie"] and b:
		searchList = [{'sublanguageid':"eng,ell",'query':h.name(),'imdbid':magnet["htmlmovie"]["id"].replace("tt","")}]
		subtitlesList = subdown.server.SearchSubtitles(session['token'], searchList)
		if subtitlesList["data"]!=False:
			magnet["htmlmovie"]["subs"]={}
			nosubs=True
			for i in subtitlesList["data"]:
				if i["ISO639"] not in magnet["htmlmovie"]["subs"]:
					magnet["htmlmovie"]["subs"][i["ISO639"]]=[]
				#~ Popen(["sh downsub.sh %s %s" %(i["SubDownloadLink"],movie["path"].rsplit(".",1)[0].replace("(","\(").replace(")","\)").replace(" ","\ ")+"_"+i["ISO639"]+"_"+str(c))], shell=True)
				subtitles=subtitles+ magnet["htmlmovie"]["path"].rsplit("/",1)[0]+"/"+i["SubFileName"]+","
				open(magnet["htmlmovie"]["path"].rsplit("/",1)[0]+"/"+i["SubFileName"],'w')
				if nosubs==True:
					Popen(["sh downsub.sh %s %s" %(i["SubDownloadLink"],magnet["htmlmovie"]["path"].rsplit("/",1)[0]
					.replace("(","\(")
					.replace(")","\)")
					.replace(" ","\ ")+"/"+i["SubFileName"])], shell=True)
					nosubs=False
				magnet["htmlmovie"]["subs"][i["ISO639"]].append({
				"subname":i["SubFileName"],
				"subdate":i["SubAddDate"],
				"tarlink":i["SubDownloadLink"],
				"username":i["UserNickName"],
				"ziplink":i["ZipDownloadLink"],
				"rating":i["SubRating"]
				})
			magnet["htmlmovie"]["subs"]["omxsub"]=subtitles	
	elif b :
		subtitles=magnet["htmlmovie"]["subs"]["omxsub"]
	print subtitles			
	magnets[h.name()]=magnet	
	#~ h.queue_position_top() 	
	#~ h.resume()
	print dir(h)	
	play=True
	for op in xrange(start,start+add_pieces):
		h.piece_priority(op,7)
	for op in xrange(start+add_pieces,pieceend):
		h.piece_priority(op,0)	
	playing_video=None
	while play==True:
	
		s = h.status()
		have_pieces=s.pieces
		prio=h.piece_priorities()
		#~ print s.list_peers
		#~ print s.num_complete
		print prio
		#~ print have_pieces	
		j=0
		soon=add_pieces
		for i in xrange(start,pieceend):
			if have_pieces[start]:
				start+=1
			if have_pieces[i] and (prio[i]==7 or prio[i]==2) :
				h.piece_priority(i,0)
				soon=soon-1
		if soon<add_pieces:
			h.piece_priority(start,7)
			for i in xrange(start+1,pieceend):
				if not have_pieces[i] and prio[i]!=7 and soon<add_pieces:
					h.piece_priority(i,2)
					soon=soon+1	
				if soon==add_pieces:
					break	
	
		#~ if have_pieces[start] or s.progress>=0.5:
		full_pieces=0
		for p in xrange(piecestart,pieceend):
			if have_pieces[p]:
				full_pieces=full_pieces+1
				
				
		if start>add_pieces:	
				
			if playing_video==None:
				print "start playing"
				duration=get_duration("/home/tv/movies/"+video)
				playing_video=omxcon.omxplayer("/home/tv/movies/"+video)
				print duration
				paused=False
				omx_time=0
				seconds_per_piece=duration/(pieceend-piecestart)
			elif playing_video!=None:
				position=playing_video.prop.Position()
				omx_position=(position/1000000)	
				web_position=omx_position
				torrent_position=full_pieces/(pieceend-piecestart)
				downloaded=start/pieceend
				print pieceend,piecestart,start
				print "omx:", omx_position/duration ,"%,torrent:",downloaded
				if torrent_position>=(omx_position+0.02):
					print "pause torrent"
					h.pause()
				else:
					#~ h.resume()	
					print "resume torrent"
					
				played=omx_time/duration
				if (played+0.01)>downloaded and paused==False:
					paused=True
					print "pause"
					playing_video.Play()
				elif (played+0.01)<downloaded:
					paused=False
					print "resume"
					playing_video.Play()
			if duration!=None and not paused:
				omx_time=omx_time+seconds_per_piece
		print '\r%.2f%%  (d: %.1f kb/s u: %.1f kB/s p: %d) %s , %d full from %d pieces , sequential pieces %d ' % \
			(s.progress * 100, s.download_rate / 1000, s.upload_rate / 1000, \
			s.num_peers, state_str[s.state],full_pieces, end-piecestart,start),
		#~ sys.stdout.flush()		
				
		time.sleep(seconds_per_piece)
		
			#~ add_pieces=add_pieces+1		
			#~ while have_pieces[start]:
				#~ start=start+1
				#~ end=start+add_pieces
				#~ playing_time=playing_time+seconds_per_piece	
			#~ get_pieces(start, end,seconds_per_piece)
			#~ h.set_piece_deadline(start,seconds_per_piece)
		#~ elif duration!=None and paused==False and omx_time>=(playing_time-seconds_per_piece):
			#~ print "pause"
			#~ h.set_piece_deadline(start,seconds_per_piece*1000)
			#~ paused=True
			#~ playing_video.Play()
	

	#~ while tor[link]==True:
		#~ s = h.status()
		#~ time.sleep(3)
		#~ print '\r%.2f%% complete (down: %.1f kb/s up: %.1f kB/s peers: %d) %s' % \
			#~ (s.progress * 100, s.download_rate / 1000, s.upload_rate / 1000, \
			#~ s.num_peers, state_str[s.state]),
		#~ sys.stdout.flush()
		#~ if state_str[s.state] in ['downloading', 'finished', 'seeding']:
			#~ global playable
			#~ if  playing==False and s.progress>=0.01:
				#~ playing=True
				#~ playable[link]=True
				#~ playingvideo=omxcon.omxplayer("/home/pi/movies/"+video,subtitles)
				#~ print "its playing"	
		#~ if state_str[s.state] in ['finished', 'seeding']:
				#~ tor[link]=False
				#~ print "torrent end"
	ses.remove_torrent(h)
	tor={}				
def toAscii(str):
	return unicodedata.normalize('NFKD', str).encode('ascii', 'ignore')

def fillInFromOmdb(movie):
	"fills in data from www.omdbapi.com"
		
	def askOmdb(movie):
		parameters = [
			("t", movie['title']),
			("y", movie['year']),
			("tomatoes", "true"),
			("plot", "full")
		]
		#~ if movie['id']:
			#~ parameters = [
				#~ ("i", movie['id']),
				#~ ("y", movie['year']),
				#~ ("tomatoes", "true"),
				#~ ("plot", "full")
			#~ ]
		query = urllib.urlencode(parameters, True)
		req = urllib2.Request("http://www.omdbapi.com/?" + query)
		response = urllib2.urlopen(req)
		omdb = loads( response.read() )
		response.close()

		if omdb['Response'] == "True" and omdb['Type'] == "movie":
			if len( omdb['tomatoRating'] ) == 1:
				omdb['tomatoRating'] = omdb['tomatoRating'] + ".0"
			elif omdb['tomatoRating'] == "N/A":
				omdb['tomatoRating'] = ""
			omdb['tomatoConsensus'] = htmlParser.unescape(omdb['tomatoConsensus'])
			movie['omdb'] = omdb
			movie['genres'] = map(unicode.strip, omdb['Genre'].split(",") )
			movie['actors'] = map(unicode.strip, omdb['Actors'].split(",") )
			movie['directors'] = map(unicode.strip, omdb['Director'].split(",") )
			movie['runtime'] = omdb['Runtime'].replace(" h ", ":").replace(" min", "")
			
			movie['id'] = omdb['imdbID']
			#~ try:
			
			
			
			try:
				fanart=loads(requests.get("http://fanart.tv/webservice/movie/d4456d0fa3ac211a91e6edff66623ac4/"+movie["id"]+"/JSON/").text)
			except:
				fanart=None
			if type(fanart)!=list and fanart!=None:
				movie["omdb"]["fanart"]= fanart[[i for i in fanart][0]]
			#~ except:
				#~ print "no fanart"
			# "2:4" -> "2:04"
			shortMatches = re.findall(r':\d$', movie['runtime'])
			if shortMatches:
				movie['runtime'] = movie['runtime'][:-2] + ":0" + movie['runtime'][-1]
			
			# "2 h" -> "2:00"
			shortHourMatches = re.findall(r' h$', movie['runtime'])
			if shortHourMatches:
				movie['runtime'] = movie['runtime'][:-2] + ":00"
					
			#~ print "found with omdbapi: " + movie['omdb']['Title']

			return movie
		else:
			movie['genres'] = []
			movie['actors'] = []
			return False

	try:
		res = askOmdb(movie)
	except:
		res=""
	if not res:
		# search IMDB with Google's i'm feeling lucky
		
		try:
			gquery = 'http://www.google.com/search?q='+urllib.quote_plus( toAscii(movie['title']) + ' film')+'&domains=http%3A%2F%2Fimdb.com&sitesearch=http%3A%2F%2Fimdb.com&btnI=Auf+gut+Gl%C3%BCck%21'
			req = urllib2.Request(url=gquery)
			req.add_header('Accept-Language', 'en-US')
			useragent = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'
			req.add_header('User-Agent', useragent)
			gr = urllib2.urlopen(req)
			matches = re.findall(r'<title>.*</title>', gr.read())
			imatch = re.findall(r'(tt[0-9]{7})', gr.geturl())
			gr.close()
			if matches and "site:http://imdb.com" not in matches[0]:
				title = matches[0][7:-15]
				tmatch = re.findall(r' \([a-zA-Z0-9 ]*\)$', title)
				if tmatch:
					title = title.replace(tmatch[0], "")
					movie['year'] = tmatch[0][2:-1]
				print "found on IMDB with Google: " + matches[0] + " -> " + title
				if imatch:
					movie['id'] = imatch[0]
				movie['title'] = title
				res = askOmdb(movie)
				if res:
					movie = res
				else:
					movie['genres'] = ["Unknown"]
					movie['title'] = movie['upperCaseTitle']
					print "couldn't find anywhere: '" + title + "', " + movie['year']
		except:	
			print "No movie info"		
	          
	return movie				
def qmagnet(link):
	global s , ses
	print link
	downloaded=False
	for i in magnets:
		if "link" in magnets[i]:
			if magnets[i]["link"]==link:
				downloaded=True
				break
	if downloaded==False:		
		h = lt.add_magnet_uri(ses, str(link), params)		
		while (not h.has_metadata()):
			time.sleep(.1)
		info = h.get_torrent_info()
		size=0
		for i in info.files():
			if i.size>=size:
				size=i.size
				video=i.path
		video_info=guessit.guess_video_info(video)
		prio=h.piece_priorities()
		for i in xrange(int(0.03*len(prio)),len(prio)):
			h.piece_priority(i,0)
		movie = {}
		magnet={}
		try:
			movie['title'] = video_info["title"]
			movie["path"]="/home/pi/movies/"+video
			movie['year'] = video_info["year"]
			movie['quality'] = video_info["format"]
			movie['suffix'] = video_info["mimetype"]
		except:	
			movie['title']=h.name()
			movie["path"]="/home/pi/movies/"+video
		try:
			movie=fillInFromOmdb(movie)
		except:
			print "no info for movie"
		magnet["htmlmovie"]=movie
		magnet["link"]=link
		print movie["path"]

		magnets[h.name()]=magnet
		try:
			if "omdb" in magnet["htmlmovie"]:
				urllib.urlretrieve(magnet["htmlmovie"]["omdb"]['Poster'], filename=os.path.dirname(movie["path"])+'/poster.jpg')
				with open(os.path.dirname(movie["path"])+'/poster.jpg') as img:
					data=img.read()
					magnets.put_attachment(magnet,data,"poster.jpg","image/jpg")
		except:
			print "no poster"
		print 'saved : ', h.name()
	
	
def saveChannel(link):
	print "aaaaaaaaa"+link
	html = urllib2.urlopen(link).read()
	soup = BeautifulSoup(html)
	all_links = soup.findAll("a")
	i=0
	searchmagnet=[]
	for link in all_links:
		
		if link["href"].startswith("magnet"):
			#~ searchmagnet.append(threading.Thread(target=qmagnet,args=(link["href"],)))
			#~ searchmagnet[i].start()	
			#~ i=i+1	
			qmagnet(link["href"])
	print all_links
def startImage(link):
	subprocess.Popen(["fbi","-T","1","-t","5","-a","-e","-cachemem","50",link])
def startStream(link):
	if link.split(".").pop()  in ["mp4","mp3"]:
		playingvideo=omxcon.omxplayer(str(link))
	else:
		link=web.webapi.urllib.unquote(link)
		ydl = youtube_dl.YoutubeDL({'outtmpl': '%(id)s%(ext)s'})
		# Add all the available extractors
		ydl.add_default_info_extractors()
		
		result = ydl.extract_info(link
		    , download=False # We just want to extract the info
		    )
		
		if 'entries' in result:
		    # Can be a playlist or a list of videos
		    video = result['entries'][0]
		else:
		    # Just a video
		    video = result
		
		print(video)
		video_url = video['url']
		playingvideo=omxcon.omxplayer(video_url)
		stream={}
		htmlmovie={"omdb":{}}
		#~ ydl = youtube_dl.YoutubeDL({'outtmpl': '%(title)s.%(ext)s'})
		#~ # Add all the available extractors
		#~ ydl.download([link])
		#~ videoName=ydl.prepare_filename(video)
		#~ playing=True
		#~ playable[link]=True
		#~ playingvideo=omxcon.omxplayer("/root/"+videoName)
		#~ ydl.add_default_info_extractors()
		#~ result = ydl.extract_info(link
			#~ , download=False # We just want to extract the info
			#~ )
		#~ if 'entries' in result:
			#~ # Can be a playlist or a list of videos
			#~ video = result['entries'][0]
		#~ else:
			#~ # Just a video
			#~ video = result
		#~ if link not in streams:
			#~ if 'upload_date' in video:
				#~ htmlmovie["Released"]=video['upload_date']
			#~ htmlmovie["omdb"]['Website']=video['extractor']
			#~ if 'like_count' in video:
				#~ htmlmovie["omdb"]['imdbVotes']=video['like_count']
			#~ if "duration" in video:
				#~ htmlmovie["runtime"]=video['duration']
			#~ if 'view_count' in video:	
				#~ htmlmovie["views"]=video['view_count']
			#video['playlist']
			#~ htmlmovie["title"]=video['title']
			#htmlmovie[""]=video['playlist_index']
			#~ if "dislike_count" in video:
				#~ htmlmovie["tomatoRotten"]=video['dislike_count']
			#video['age_limit']
			#~ if 'thumbnail' in video:
				#~ htmlmovie["omdb"]["Poster"]=video['thumbnail']
			#~ if 'description' in video:
				#~ htmlmovie["omdb"]["Plot"]=video['description']
			#~ htmlmovie["quality"]=video['format']
			#~ if 'uploader' in video:
				#~ htmlmovie["Writer"]=video['uploader']
			#~ video['subtitles']
			#~ video['url']
			#~ video['ext']
			#~ if "youtube" in video['extractor']:
				#~ genre=[loads(requests.get("https://gdata.youtube.com/feeds/api/videos?q="+video['webpage_url_basename']+"&alt=json&fields=entry/category").text)["feed"]["entry"][0]["category"][1]["label"]]
				#~ print genre
				#~ htmlmovie["genres"]=genre
			#~ htmlmovie['base']=link
			#~ htmlmovie["omdb"]['Website']=video['webpage_url']
			#~ htmlmovie["directory"]=streamfolder
			#~ videoName=ydl.prepare_filename(video)	
			#~ htmlmovie["path"]=streamfolder+videoName
			#~ stream["htmlmovie"]=htmlmovie
			#~ streams[link]=stream
			#~ ydl.download([link])
			#~ playing=True
			#~ playable[link]=True
			#~ playingvideo=omxcon.omxplayer("/home/pi/"+videoName)
			#~ print "its playing"	
		#~ else:
			#~ ydl.download([link])

	
def tuneSearch(term):
	__partnerid__ = 'yvcOjvJP'
	mac = get_mac()
	tune = tunein.TuneIn(__partnerid__, serial=mac, locale="el-GR")
	if "genres" not in tunes:
		genre={}
		genres=tune.describe_genres()
		for i in genres:
			genre[i["guide_id"]]=i["text"]
		tunes["genres"]=genre
	genre=tunes["genres"]
	print term
	results = tune.search(term, 'standard')
	tunesearch={"term":term,"tune":results}	
	tunes[term]=tunesearch
	








def check_value(value):
	if value is None:
		return ''
	return normalize_unicode(value)
def normalize_unicode(text):
	if text and not isinstance(text, unicode):
		return text
	if not text or len(text) == 0:
		return ''
	return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore')
def get_value(tuple, key):
	if key not in tuple:
		return ''
	return check_value(tuple[key])
def get_int(tuple, key):
	if key not in tuple:
		return 0
	return int(check_value(tuple[key]))
def get_max_preset_num(elementslist):
	maxpresetnum = 0
	for element in elementslist:
		if 'show' in element and get_int(element['show'], 'preset_number') > maxpresetnum:
			maxpresetnum = get_int(element['show'], 'preset_number')
		elif 'station' in element and get_int(element['station'], 'preset_number') > maxpresetnum:
			maxpresetnum = get_int(element['station'], 'preset_number')
		elif 'link' in element and tune.is_custom_url_id(get_value(element['link'], 'guide_id')) and get_int(element['link'], 'preset_number') > maxpresetnum:
			maxpresetnum = get_int(element['link'], 'preset_number')
	return maxpresetnum
def __read_element__(element):
	outline = {}
	for key in element:
		outline[key] = element[key]
	return outline
def process_tunein_json(elements):
	elementslist = []
	for element in elements:
		if ('element' in element and element['element'] == 'outline'):
			if ('children' in element):
				for children in element['children']:
					if ('key' in element and element['key'] == 'shows'):
						if ('item' in children and children['item'] == 'show'):
							elementslist.append(
								{'show': __read_element__(children)})
						elif ('type' in children and children['type'] == 'link'):
							elementslist.append(
								{'link': __read_element__(children)})
						# else:
							# print('Ignoring outline-children-shows: %s' %
							# children)
					elif ('key' in element and element['key'] == 'stations'):
						if ('item' in children and children['item'] == 'station'):
							elementslist.append(
								{'station': __read_element__(children)})
						elif ('type' in children and children['type'] == 'link'):
							elementslist.append(
								{'link': __read_element__(children)})
						# else:
							# print('Ignoring outline-children-stations: %s' %
							# children)
					elif('key' in element and element['key'] == 'topics'):
						if ('item' in children and children['item'] == 'topic'):
							elementslist.append(
								{'topic': __read_element__(children)})
						elif ('type' in children and children['type'] == 'link'):
							elementslist.append(
								{'link': __read_element__(children)})
						# else:
							# print('Ignoring outline-children-topics: %s' %
							# children)
					else:
						if ('type' in children and children['type'] == 'audio'):
							if 'item' in children and children['item'] == 'station':
								elementslist.append(
									{'station': __read_element__(children)})
							elif 'item' in children and children['item'] == 'show':
								elementslist.append(
									{'show': __read_element__(children)})
							elif ('guide_id' in children and children['guide_id'][0] == 's'):
								elementslist.append(
									{'station': __read_element__(children)})
							elif ('guide_id' in children and children['guide_id'][0] == 't'):
								elementslist.append(
									{'topic': __read_element__(children)})
							elif ('guide_id' in children and children['guide_id'][0] == 'p'):
								if presets:
									elementslist.insert(children['preset_number'], {
														'show': __read_element__(children)})
								else:
									elementslist.append(
										{'show': __read_element__(children)})
						elif ('type' in children and children['type'] == 'link'):
							elementslist.append(
								{'link': __read_element__(children)})
						# else:
							# print('Ignoring outline-children: %s' % children)

			elif ('type' in element and element['type'] == 'audio' and 'guide_id' in element and element['guide_id'][0] == 's'):
				elementslist.append({'station': __read_element__(element)})
			elif ('type' in element and element['type'] == 'audio' and 'guide_id' in element and element['guide_id'][0] == 't'):
				elementslist.append({'topic': __read_element__(element)})
			elif ('type' in element and element['type'] == 'audio' and 'guide_id' in element and element['guide_id'][0] == 'p'):
				elementslist.append({'show': __read_element__(element)})
			elif ('type' in element and element['type'] == 'link'):
				elementslist.append({'link': __read_element__(element)})
			elif ('item' in element and element['item'] == 'show'):
				elementslist.append({'show': __read_element__(element)})
			elif ('item' in element and element['item'] == 'station'):
				elementslist.append({'station': __read_element__(element)})
			# else:
				# print('Ignoring outline: %s' % element)
		elif ('element' in element and element['element'] == 'show'):
			elementslist.append({'show': __read_element__(element)})
		elif ('element' in element and element['element'] == 'station'):
			elementslist.append({'station': __read_element__(element)})
		elif ('element' in element and element['element'] == 'topic'):
			elementslist.append({'topic': __read_element__(element)})
		elif ('element' in element and element['element'] == 'link'):
			elementslist.append({'link': __read_element__(element)})
		# else:
			# print('Ignoring: %s' % element)

	# if presets, reorder.
	if get_max_preset_num(elementslist) > 0:
		elementslist = reorder_preset_elements(elementslist)
	ips=[]
	for element in elementslist:
		
		g=""
		if "station" in element:
			#~ print element
			#~ print element["station"]["guide_id"]
			if "genre_id" in element["station"] and element["station"]["genre_id"][0]=="g":
				g=genre[element["station"]["genre_id"]]
				#~ 
			ips.append({
						"url":element["station"]["URL"],
						"Title":element["station"]["text"],
						"Plot":element["station"]["subtext"],
						"Poster":element["station"]["image"],
						"tomatoConsensus":g})
				
	return ips
