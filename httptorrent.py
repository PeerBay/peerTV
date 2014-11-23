#~ import omxplayer
#~ def addTorrent(link):
	#~ 
#~ def tvStream():	

#!/usr/bin/python2
__credits__ = """Copyright (c) 2011 Roman Beslik <rabeslik@gmail.com>
Licensed under GNU LGPL 2.1 or later.  See <http://www.fsf.org/>.

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
"""

# to do:
# comment the source code
# libtorrent-rasterbar to python3
# HTTP timeout mplayer option
# "mplayer" does not respect "-cache" and "-cache-min" after seek
# "mplayer" sends HTTP requests too often for non-interleaved files

# done:

import BaseHTTPServer
from SocketServer import ThreadingMixIn
import httpheader
from cgi import escape as escape_html
import urllib
from mimetypes import guess_type as guess_mime_type
import libtorrent

import threading
import os
import os.path as fs
import sys
import io
import getopt
import signal
from time import sleep

import logging
import logging.config
import json
import base64

class reference(object):
	pass

def split_path_list(path):
	r = []
	while True:
		y, x = fs.split(path)
		if y==path:
			break;
		path = y
		r.append(x)
	return r

def range_spec_len(r):
	return r.last+1-r.first

def coerce_piece_par(s):
	try:
		b = int(s)
	except ValueError:
		return (227, "\"--piece-par\" is not an integer")
	if b<=0:
		return (228, "\"--piece-par\" must be positive")
	else:
		return (0, b)

class piece_server(object):
	def __init__(self):
		super(piece_server, self).__init__()
		self.lock = threading.Lock()
		self.array = []
	def init(self):
		self.torrent_handle.prioritize_pieces(self.torrent_info.num_pieces() * [0])
		logger = logging.getLogger("root")
		logger.debug("83"+str(self.torrent_info.num_pieces()))
	def push(self, read_piece_alert):
		if (self.torrent_handle == read_piece_alert.handle):
			self.lock.acquire()
			try:
				def f(record):
					_, _, piece = record
					return piece == read_piece_alert.piece
				for record in filter(f, self.array):
					event, channel, _ = record
					channel.append(read_piece_alert.buffer)
					event.set()
				self.array = filter(lambda record: not(f(record)), self.array)
			finally:
				self.lock.release()
	def pop(self, piece):
		logger = logging.getLogger("root")
		event = threading.Event()
		channel = []
		self.lock.acquire()
		s=self.torrent_handle.status()
		have_piece=s.pieces
		j=0
		for i in have_piece:
			if i>0:
				self.torrent_handle.piece_priority(j, 0)
			j+=1
		try:
			piece_par = self.piece_par.data
			def bound_in_torrent(start):
				return min(self.torrent_info.num_pieces(), start+piece_par)
			bound0 = bound_in_torrent(piece)
			phave = piece
			while have_piece[phave]:
				phave += 1
				self.torrent_handle.piece_priority(phave, 0)
			while phave < bound0 and have_piece[phave]:
				phave += 1
				self.torrent_handle.piece_priority(phave, 0)
			bound1 = bound_in_torrent(phave)
			p = phave
			while p < bound1:
				if p==phave:
					priority = 7
				else:
					priority = 2
				self.torrent_handle.piece_priority(p, priority)
				p += 1
			logger.debug("downloading of the pieces ["+str(phave)+", "+str(bound1)+") has been turned on")
			self.array.append((event, channel, piece))
			print self.torrent_handle.piece_priorities()
			print  "speed:",s.download_rate / 1000
			self.torrent_handle.set_piece_deadline(piece, 1, libtorrent.deadline_flags.alert_when_available)
		finally:
			self.lock.release()
		event.wait()
		return channel[0]
		

class alert_client(threading.Thread):
	def __init__(self):
		super(alert_client, self).__init__()
		self.daemon = True
	def run(self):
		logger = logging.getLogger("root")
		self.torrent_session.set_alert_mask(libtorrent.alert.category_t.storage_notification + libtorrent.alert.category_t.status_notification)
		while(True):
			self.torrent_session.wait_for_alert(1000)
			a = self.torrent_session.pop_alert()
			if (type(a) == libtorrent.read_piece_alert):
				logger.info("the piece "+str(a.piece)+" is received")
				self.piece_server.push(a)
			if (type(a) in [libtorrent.save_resume_data_alert, libtorrent.save_resume_data_failed_alert]
				and not (self.resume_alert is None)):
				self.resume_alert.push(a)
			if (type(a) == libtorrent.fastresume_rejected_alert):
				logger.info("resume data have been rejected"
					" because \""+str(a.error.message())+"\" (error code="+str(a.error.value())+")")

class torrent_file_bt2p(object):
	def write(self, dest, r):
		logger = logging.getLogger("root")
		request_done = False
		while (not(request_done)):
			piece_slice = self.map_file(r.first)
			logger.info("the piece "+str(piece_slice.piece)+" has been requested")
			data = self.piece_server.pop(piece_slice.piece)
			if data is None:
				logger.warning("pop_piece() is None for the piece "+str(piece_slice.piece))
				request_done = True
			else:
				available_length = range_spec_len(r)
				end = piece_slice.start + available_length
				if (end>=len(data)):
					end = len(data)
					available_length = len(data)-piece_slice.start
				logger.debug("writing the data=(piece="+str(piece_slice.piece) \
					+", interval=["+str(piece_slice.start)+", "+str(end)+"))")
				dest.write(data[piece_slice.start:end])
				logger.debug("the data have been written")
				r.first += available_length
				request_done = r.first>r.last

class torrent_read_bt2p(object):
	def write_html(self, s):
		return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>"""+escape_html(self.torrent_info.name())+"""</title>
</head>
<body>
"""+s+"""
</body>
</html>
"""
	def write_html_index(self, piece_par):
		t = {}
		error = []
		for f in self.torrent_info.files():
			t0 = t
			level = 0
			xs = split_path_list(f.path)
			level_n = len(xs)
			for x in reversed(xs):
				key_found = x in t0
				if level+1 >= level_n:
					if key_found:
						error.append("duplicate file: "+f.path)
					else:
						t0[x] = ("file", f)
				else:
					if key_found:
						tag, t1 = t0[x]
						if not (tag == "dir"):
							error.append("file and directory: "+f.path)
							break
						t0 = t1
					else:
						t1 = {}
						t0[x] = ("dir", t1)
						t0 = t1
				level += 1
		def flat(t, level):
			r = []
			for x, y in sorted(t.iteritems(), key = lambda x: x[0]):
				tag, z = y
				# indent_s = level*"&mdash;"
				indent_s = " style=\"padding-left:"+str(30*level)+"pt\""
				if "file"==tag:
					f = z
					r.append("""
<tr>
	<td"""+indent_s+"""><a href="""+"\""+urllib.pathname2url("/"+f.path)+"\""+""">"""+escape_html(x)+"""</a></td>
	<td>"""+str(f.size)+"""</td>
</tr>
""")
				elif "dir"==tag:
					r.append("""
<tr><td colspan=\"2\""""+indent_s+""">"""+escape_html(x)+"""</td></tr>
""")
					r.append(flat(z, level+1))
				else:
					pass
			return "".join(r)
		file_tree_s = flat(t, 0)
		error2s = lambda x: "<li>"+escape_html(x)+"</li>"
		if 0==len(error):
			error_s = ""
		else:
			error_s = "<p>error:</p><ol>"+"".join(map(error2s, error))+"</ol>"
		return self.write_html("""<p><form method=\"get\" action=\"/\"><strong>piece_par:</strong> """+str(piece_par)+""" <input type=\"text\" name=\"piece_par\" value=\""""+str(piece_par)+"""\" maxlength="6" size="8" /> <input type=\"submit\" value=\"change\" /></form></p>
<h1>torrent parameters</h1>
<p><strong>name:</strong> """+escape_html(self.torrent_info.name())+"""</p>
<p><strong>comment:</strong></p>
<p>"""+escape_html(self.torrent_info.comment())+"""</p>
<p><strong>size:</strong> """+str(self.torrent_info.total_size())+"""</p>
<p><strong>piece length in bytes:</strong> """+str(self.torrent_info.piece_length())+"""</p>
<table>
<tr>
	<th>file</th>
	<th>size</th>
</tr>
"""+file_tree_s+"""</table>"""+error_s)

	def init(self):
		self.info_hash = self.torrent_info.info_hash()
	def find_file(self, http_path):
		p = urllib.url2pathname(http_path)
		for i, f0 in enumerate(self.torrent_info.files()):
			if "/"+f0.path == p:
				f1 = torrent_file_bt2p()
				f1.size = f0.size
				f1.map_file = lambda offset: self.torrent_info.map_file(i, offset, 1)
				f1.content_type = guess_mime_type(f0.path)
				return f1
		return None

class http_responder_bt2p(BaseHTTPServer.BaseHTTPRequestHandler):
	def send_common_header(self):
		self.send_header("Accept-Ranges", "bytes")
		self.send_header("ETag", self.server.torrent.info_hash)
	def read_from_torrent(self, torrent_file):
		logger = logging.getLogger("root")
		file_size = torrent_file.size
		def content_range_header(r):
			return "bytes "+str(r.first)+"-"+str(r.last)+"/"+str(file_size)
		content_type, content_encoding = torrent_file.content_type
		if content_type is None:
			content_type = "application/octet-stream"
			content_encoding = None
		def send_header_content_type():
			self.send_header("Content-Type", content_type)
			if not (content_encoding is None):
				self.send_header("Content-Encoding", content_encoding)
		def write_content_type():
			self.wfile.write("Content-Type: "+content_type+"\r\n")
			if not (content_encoding is None):
				self.send_header("Content-Encoding: "+content_encoding+"\r\n")
		hr = self.headers.get("Range")
		is_whole = True
		if not (hr is None): # http://deron.meranda.us/python/httpheader/
			try:
				hr_parsed = httpheader.parse_range_header(hr)
				try:
					
					hr_parsed.fix_to_size(file_size)
					hr_parsed.coalesce()
					self.send_response(206)
					self.send_common_header()
					if hr_parsed.is_single_range():
						r = hr_parsed.range_specs[0]
						send_header_content_type()
						self.send_header("Content-Length", range_spec_len(r))
						self.send_header("Content-Range", content_range_header(r))
						self.end_headers()
						torrent_file.write(self.wfile, r)
						logger.debug("317:  ",hr_parsed,self.wfile,range_spec_len(r), content_range_header(r))
						######################################################################################################################################~ 
						
					else: # this code is not tested
						import random, string
						boundary = '--------' + ''.join([ random.choice(string.letters) for i in range(32) ])
						self.send_header("Content-Type", "multipart/byteranges; boundary="+boundary)
						self.end_headers()
						
						for r in hr_parsed.range_specs:
							self.wfile.write(boundary+"\r\n")
							write_content_type()
							self.wfile.write("Content-Length: "+str(range_spec_len(r))+"\r\n")
							self.wfile.write("Content-Range: "+content_range_header(r)+"\r\n\r\n")
							torrent_file.write(self.wfile, r)
							self.wfile.write("\r\n"+boundary+"--\r\n")
							logger.debug( "333:  ",r,str(range_spec_len(r)),content_range_header(r),self.wfile,boundary)
						######################################################################################################################################~ 

					is_whole = False
				except httpheader.RangeUnsatisfiableError:
					self.send_response(416)
					self.send_common_header()
					self.send_header("Content-Range", "*/"+str(file_size))
					self.end_headers()
					is_whole = False
			except httpheader.ParseError:
				pass
		if is_whole:
			self.send_response(200)
			self.send_common_header()
			send_header_content_type()
			self.send_header("Content-Length", str(file_size))
			self.end_headers()
			r = httpheader.range_spec()
			r.first = 0
			r.last = file_size-1
			torrent_file.write(self.wfile, r)
			logger.debug( "347:  ",self.wfile,r.first,r.last,file_size)
			######################################################################################################################################~ 
	def do_GET(self):
		logger = logging.getLogger("root")
		try:
			logger.info(self.command)
			logger.info(self.path)
			logger.info(self.headers)
			piece_par_req = "/?piece_par="
			if "/"==self.path:
				self.send_response(200)
				self.send_common_header()
				self.send_header("Content-Type", "application/xhtml+xml")
				s = self.server.torrent.write_html_index(self.server.piece_par.data)
				self.send_header("Content-Length", str(len(s)))
				self.end_headers()
				self.wfile.write(s)
			elif self.path[0:len(piece_par_req)]==piece_par_req:
				self.send_response(200)
				self.send_common_header()
				self.send_header("Content-Type", "text/plain")
				tag, value = coerce_piece_par(self.path[len(piece_par_req):])
				if 0==tag:
					self.server.piece_par.data = value
					logger.info("piece_par was set to "+str(value))
					s = "ok "+str(value)
				else:
					s = "error "+value
				s += "\r\n"
				self.send_header("Content-Length", str(len(s)))
				self.end_headers()
				self.wfile.write(s)
			else:
				torrent_file = self.server.torrent.find_file(self.path)
				if not torrent_file:
					self.send_response(404)
					self.end_headers()
				else:
					torrent_file.piece_server = self.server.piece_server
					self.read_from_torrent(torrent_file)
		except IOError, e:
			logger.debug("IOError")
			raise e
		finally:
			logger.debug("the thread answering the request has been terminated")

class http_server_bt2p(ThreadingMixIn, BaseHTTPServer.HTTPServer):
	pass

class resume_alert(object):
	def __init__(self):
		super(resume_alert, self).__init__()
		self.lock = threading.Lock()
	def push(self, alert):
		self.lock.acquire()
		try:
			self.channel.append(alert)
			self.event.set()
		finally:
			self.lock.release()
	def pop(self):
		event = threading.Event()
		channel = []
		self.lock.acquire()
		try:
			self.channel = channel
			self.event = event
			self.torrent_handle.save_resume_data()
		finally:
			self.lock.release()
		event.wait()
		self.channel = None
		return channel[0]

class resume_save(object):
	def __init__(self):
		super(resume_save, self).__init__()
		self.lock = threading.Lock()
		self.last = False
	def save(self, last):
		self.lock.acquire()
		try:
			if not self.last:
				logger = logging.getLogger("root")
				alert = self.resume_alert.pop()
				if type(alert)==libtorrent.save_resume_data_alert:
					io.open(self.file_name, "wb").write(libtorrent.bencode(alert.resume_data))
					logger.debug("resume data have been written to: "+self.file_name)
				else:
					logger.warning("can not obtain resume data, error code: "+str(alert.error_code))
				self.last = last
		finally:
			self.lock.release()

class resume_timer(threading.Thread):
	def __init__(self):
		super(resume_timer, self).__init__()
		self.daemon = True
	def run(self):
		while(True):
			sleep(60) # configuration. a time in seconds between savings of resume data
			self.resume_save.save(False)

def error_exit(exit_code, message):
	sys.stderr.write(message+"\n")
	sys.exit(exit_code)

class term_handler(object):
	def __init__(self):
		super(term_handler, self).__init__()
		self.h = {}
		self.set_all()
	def set_handler(self, name, f):
		self.h[name] = f
		self.set_all()
	def do(self):
		def get_default(key):
			def nop():
				pass
			if key in self.h:
				return self.h[key]
			else:
				return nop
		get_default("save_resume")()
		get_default("scavenge_pid")()
		sys.exit(os.EX_OK)
	def set_all(self):
		def f():
			self.do()
		signal.signal(signal.SIGTERM, f)

def main_resume(resume):
	success = None
	resume_data = None
	if not (resume is None):
		if fs.exists(resume):
			if fs.isfile(resume):
				resume_data = io.open(resume, "rb").read()
				success = True
			else:
				success = False
		else:
			success = True
	else:
		success = True
	if success:
		return resume_data
	else:
		error_exit(224, "\"--resume\" is not a regular file")

def main_log(l):
	log, log_conf = l
	if log:
		if log_conf is None:
			log_conf = "/etc/bittorrent2player/logging.conf" # configuration
		else:
			error_exit(229, "both \"--log\" and \"--log-conf\" are given, the logging configuration file name is ambiguous")
	if not (log_conf is None):
		logging.config.fileConfig(log_conf)
	else:
		logging.disable(logging.CRITICAL)

def main_ti(options, ih):
	info_hash_count, info_hash = ih
	if not ("hash-file" in options):
		if info_hash is None:
			error_exit(225,  "\"--hash-file\" or \"--info-hash-value-*\" is mandatory")
		else:
			if 1<info_hash_count:
				error_exit(235, "too many \"--info-hash-value-*\" options are given")
			else:
				options["info-hash"] = info_hash
	else:
		if not (info_hash is None):
			error_exit(234, "giving both \"--hash-file\" and \"--info-hash-value-*\" is not allowed")
	if info_hash is None and "info-hash-tracker" in options:
		if not (len(options["info-hash-tracker"])==0):
			error_exit(236, "\"--info-hash-tracker\" without \"--info-hash-value-*\" makes no sense")
	
def main_default(options):
	print "http://0.0.0.0:8000"
	if not ("domain-name" in options):
		options["domain-name"] = "0.0.0.0" # configuration
	if not ("port" in options):
		options["port"] = 8000 # configuration
	if not ("piece-par" in options):
		options["piece-par"] = 8 # configuration
	if not ("save-path" in options):
		error_exit(226, "\"--save-path\" is mandatory")

def serve_torrent(magnet=None,hash_file=None):
	options = {}
	main_log((True,None))
	#~ th = term_handler()
	options["save-path"]="/home/tv/"
	if magnet is not None:
		options["magnet"]=magnet
	elif hash_file is not None:
		options["hash-file"]=hash_file
	logger = logging.getLogger("root")
	def f():
		logger.debug("shutting down without a resume")
	#~ th.set_handler("save_resume", f)
	
	main_default(options)
	if "resume" in options:
		resume = options["resume"]
	else:
		resume = None
	resume_data = main_resume(resume)
	
	torrent_session = libtorrent.session()
	sp = libtorrent.session_settings()
	sp.choking_algorithm=3
	sp.request_timeout /= 5 # configuration
	sp.piece_timeout /= 5 # configuration
	sp.peer_timeout /= 10 # configuration
	sp.inactivity_timeout /= 10 # configuration
	torrent_session.set_settings(sp)
	torrent_session.listen_on(6881, 6891)
	
	torrent_descr = {
		"save_path": options["save-path"]
		}
	if "hash-file" in options:
		if hash_file.startswith("http"):
			import urllib2
			response = urllib2.urlopen(hash_file)
			f = response.read()
		else:	
			f=io.open(options["hash-file"], 'rb').read()
		e = libtorrent.bdecode(f)
		torrent_info = libtorrent.torrent_info(e)
		torrent_descr["ti"] = torrent_info
		torrent_handle= torrent_session.add_torrent(torrent_descr)
	
	if "magnet" in options:
		torrent_handle=libtorrent.add_magnet_uri(torrent_session, str(options["magnet"]), torrent_descr)
		
		
		#~ torrent_descr["info_hash"] = libtorrent.big_number(options["info-hash"])
		#~ torrent_descr["trackers"] = options["info-hash-tracker"]
	if not (resume_data is None):
		torrent_descr["resume_data"] = resume_data
	logger.debug("the torrent description: "+str(torrent_descr))
	torrent_handle.set_sequential_download(True)	
	logger.debug("the torrent handle "+str(torrent_handle)+" is created man")
	
	if "magnet" in options:
		if torrent_handle.status().state==libtorrent.torrent_status.downloading_metadata:
			metadata_received = False
			torrent_session.set_alert_mask(libtorrent.alert.category_t.status_notification)
			while(not metadata_received):
				torrent_session.wait_for_alert(1000)
				a = torrent_session.pop_alert()
				logger.debug("the alert "+str(a)+" is received")
				logger.debug("the torrent handle state is "+str(torrent_handle.status().state))
				metadata_received = type(a) == libtorrent.metadata_received_alert
			logger.debug("the torrent metadata are received from your network")
		torrent_info = torrent_handle.get_torrent_info()
		#~ size=0
		#~ j=0
		#~ for i in torrent_info.files():
			#~ if i.size>=size:
				#~ size=i.size
				#~ video=i.path	
				#~ file_id=j
			#~ j=j+1
		#~ f=info.files()[file_id]
		#~ video=f.path	
	#~ torrent_handle.set_ratio(0.5) # configuration. upload_speed/download_speed

	piece_par_ref0 = reference()
	piece_par_ref0.data = options["piece-par"]
	
	piece_server0 = piece_server()
	piece_server0.torrent_handle = torrent_handle
	piece_server0.torrent_info = torrent_info
	piece_server0.piece_par = piece_par_ref0
	piece_server0.init()

	alert_client0 = alert_client()
	alert_client0.torrent_session = torrent_session
	alert_client0.piece_server = piece_server0
	if "resume" in options:
		ra = resume_alert()
		ra.torrent_handle = torrent_handle
		
		rs = resume_save()
		rs.file_name = options["resume"]
		rs.resume_alert = ra
		
		rt = resume_timer()
		rt.resume_save = rs
		rt.start()
		
		alert_client0.resume_alert = ra
	else:
		alert_client0.resume_alert = None
	alert_client0.start()
	
	r = torrent_read_bt2p()
	r.torrent_handle = torrent_handle
	r.torrent_info = torrent_info
	r.init()
	
	http_server = http_server_bt2p((options["domain-name"], options["port"]), http_responder_bt2p)
	http_server.daemon_threads = True
	http_server.torrent = r
	http_server.piece_par = piece_par_ref0
	http_server.piece_server = piece_server0
	
	if "resume" in options:
		def f():
			logger.debug("shutting down with a resume")
			torrent_session.pause()
			rs.save(True)
		#~ th.set_handler("save_resume", f)
	try:
		 
		http_server.serve_forever()
		
	except KeyboardInterrupt:
		print "key interrupt"
		#~ th.do()

def main_options(options, l, ih, th):
	main_log(l)
	
	main_ti(options, ih)
	main_torrent_descr(options, th)

def main(argv=None):
	th = term_handler()
	if argv is None:
		argv = sys.argv
	try:
		crude_options, args = getopt.getopt(argv[1:], ""
			, ["resume=", "save-path=", "piece-par=", "domain-name=", "port="
			, "log", "log-conf="
			, "hash-file=", "info-hash-value-base16=", "info-hash-value-base32=", "info-hash-tracker="])
	except getopt.error, error:
		error_exit(221, "the option "+error.opt+" is incorrect because "+error.msg)
	if []!=args:
		error_exit(222, "only options are allowed, not arguments")
	options = {}
	log = False
	log_conf = None
	info_hash_count = 0
	info_hash = None
	options["info-hash-tracker"] = []
	for o, a in crude_options:
		if "--resume"==o:
			options["resume"] = a
		elif "--hash-file"==o:
			options["hash-file"] = a
		elif o.startswith("--info-hash-value-"):
			info_hash_count += 1
			if "--info-hash-value-base16"==o:
				info_hash = base64.b16decode(a)
			elif "--info-hash-value-base32"==o:
				info_hash = base64.b32decode(a)
		elif "--info-hash-tracker"==o:
			options["info-hash-tracker"].append(a)
		elif "--save-path"==o:
			options["save-path"] = a
		elif "--piece-par"==o:
			tag, value = coerce_piece_par(a)
			if 0==tag:
				options["piece-par"] = value
			else:
				error_exit(tag, value)
		elif "--log"==o:
			log = True
		elif "--log-conf"==o:
			log_conf = a
		elif "--domain-name"==o:
			options["domain-name"] = a
		elif "--port"==o:
			options["port"] = a
		else:
			error_exit(223, "an unknown option is given")
	main_options(options, (log, log_conf), (info_hash_count, info_hash), th)

def main_daemon(argv=None):
	th = term_handler()
	if argv is None:
		argv = sys.argv
	access_mode = (7*8+5)*8+5
	var_dir = fs.expanduser("~/.local/var")
	var_run_dir = fs.join(var_dir, "run")
	try:
		os.makedirs(var_run_dir, access_mode)
	except OSError:
		pass
	ex_pid_file_name = fs.join(var_run_dir, "bt2pd.pid") # configuration
	def scavenge_pid():
		os.unlink(ex_pid_file_name)
	if fs.exists(ex_pid_file_name):
		if fs.isfile(ex_pid_file_name):
			ex_pid = int(io.open(ex_pid_file_name, "r").read())
			success = False
			i = 10
			while (i>0 and not success):
				i -= 1
				try:
					os.kill(ex_pid, signal.SIGTERM)
				except OSError:
					success = True
				sleep(1)
			if not success:
				error_exit(231, "SIGTERM was sent to the existing process of this program, but it does not terminate")
			else:
				try:
					scavenge_pid()
				except OSError:
					pass
	if len(argv)==2:
		io.open(ex_pid_file_name, "w").write(unicode(os.getpid())+"\n")
		#~ th.set_handler("scavenge_pid", scavenge_pid)
		c = None
		try:
			if "XDG_CONFIG_HOME" in os.environ and os.environ["XDG_CONFIG_HOME"]:
				xdg_config_home = os.environ["XDG_CONFIG_HOME"]
			else:
				xdg_config_home = fs.join(os.environ["HOME"], ".config")
			c = json.load(io.open(fs.join(xdg_config_home, "bt2pd.conf")))
		except IOError:
			pass
		except ValueError:
			pass
		if c is None:
			error_exit(232, "error while reading the configuration file")
		if not ("save_path" in c):
			error_exit(233, "no parameter \"save_path\" in the configuration file")
		o = {"hash-file": argv[1], "save-path": c["save_path"].encode("utf8", "ignore")
			, "resume": fs.join(var_dir, "bt2pd.resume") # configuration
			}
		if "piece_par" in c:
			o["piece-par"] = c["piece_par"]
		main_options(o, (False, None), (0, None), th)
	elif len(argv)==1:
		sys.exit(os.EX_OK)
	else:
		error_exit(os.EX_USAGE, "more than 1 argument")

#~ if __name__ == "__main__":
	#~ main()
