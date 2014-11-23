import dbus
import subprocess
import os
import re
import time
#~ import omxcon
#~ a=omxcon.OMXPlayer("video.mp4")

OMXPLAYER_LIB_PATH='/opt/vc/lib:/usr/lib/omxplayer'
LOCAL_LIB_PATH='/usr/local/lib'


class omxplayer():
	def __init__(self, mrl,subs=None):
		self.mrl = mrl
		keepratio=True
		options=""
		cmd=["omxplayer"]
		if mrl.startswith('.'):
			raise IOError('Unsafe path. Please use full path.')

		if mrl.startswith('/') and not os.access(mrl, os.R_OK):
			raise IOError('No permission to read %s' % mrl)
		if not mrl.startswith('http'):
			video_info = detect_video_information(mrl)
			if video_info == False:
				raise IOError('Media "%s" not found' % mrl)
				
			self.video_size = (video_info[0], video_info[1])
			self.audio_stream_list = video_info[2]
		cmd.extend([self.mrl , "--blank","-o","both","--threshold","7"])
		#~ if subs!="" or subs!=None:
			#~ self.subtitles=subs.split(",")
			#~ suboptions="--align center --no-ghost-box --subtitles"
			#~ suboptions=suboptions.split(' ')
			#~ suboptions.extend(self.subtitles)
			#~ cmd.extend(suboptions)
			#~ self._subtitle_toggle = True
		self._paused = False
		self._subtitle_toggle = False
		self._volume = 0 # 0db
		self._mute=False
		self.audio_stream_index = 1
		self.options = options
		if self.options!="":
			m = re.search('(-n|--aidx) (\d+)', self.options)
			if m:
				self.audio_stream_index = int(m.group(2))
				if self.audio_stream_index > len(self.audio_stream_list):
					self.audio_stream_index = len(self.audio_stream_list)
				elif self.audio_stream_index < 1:
					self.audio_stream_index = 1	

		
		if self.options!="":
			cmd.extend(self.options.split(' '))
		print cmd
		try:
			files=os.listdir("/tmp")
			for f in files:
				if f.startswith("omxplayer"):
					os.remove("/tmp/"+f)
			self.proc = subprocess.Popen(cmd)
		#except OSError as e:
		except Exception as e:
			raise e
		time.sleep(5)	
		with open('/tmp/omxplayerdbus', 'r+') as f:
			omxplayerdbus = f.read().strip()
			print omxplayerdbus
		bus = dbus.bus.BusConnection(omxplayerdbus)
		object = bus.get_object('org.mpris.MediaPlayer2.omxplayer','/org/mpris/MediaPlayer2', introspect=False)
		self.prop = dbus.Interface(object,'org.freedesktop.DBus.Properties')
		self.key = dbus.Interface(object,'org.mpris.MediaPlayer2.Player')
		self.duration=self.prop.Duration()
		print {"duration":self.duration,"position":self.prop.Position()}

	def Seek(self,seconds):
		if self.prop.CanSeek():
			self.key.Seek(dbus.Int64(seconds*1000000))
			time.sleep(1)	
			return {"position":self.prop.Position()}	
		else:
			return {"error":"can't seek"}
	def Play(self):
		self.key.Pause()
		if self._paused:
			self._paused=False
		else:
			self._paused=True
		return	{"paused":self._paused}
	def Stop(self):
		if self.prop.CanQuit():
			time.sleep(0.3)
			position=self.prop.Position()
			time.sleep(0.3)
			self.key.Stop()
			return {"position":position}
		else:
			return {"error":"can't quit"}	
	def Mute(self):
		if self._mute:
			self._mute=False
			self.prop.Unmute()
			return {"mute":False}
		else:	
			self._mute=True	
			self.prop.Mute()
			return {"mute":True}		
	def Next(self):
		if self.prop.CanGoNext():
			self.key.Next()
			return {"position":self.prop.Position()}	
		else:
			return {"error":"can't go next"}			
	def Previous(self):
		if self.prop.CanGoPrevious():
			self.key.Previous()
			return {"position":self.prop.Position()}	
		else:
			return {"error":"can't go previous"}
	def ListSubs(self):
		return self.key.ListSubtitles()
	def SelectSub(self,subidx):
		return self.key.SelectSubtitle(dbus.Int32(subidx))			

def detect_video_information(mrl):
	'''
	return:
		(width, height, audio_stream_list)
		(0, 0) - unknown size.
		False - file not found or command failed.
	'''
	OMXPLAYER='/usr/bin/omxplayer.bin'
	try:
		output = subprocess.Popen([OMXPLAYER, "-i", mrl], 
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			env={"LD_LIBRARY_PATH": OMXPLAYER_LIB_PATH}).communicate()
	except OSError:
		return False

	result = output[0].strip()
	#debug(result)
	if result.endswith(' not found.'):
		return False

	video_width = 0
	video_height = 0
	m = re.search(r'Video: .+ (\d+)x(\d+)', result)
	# m will be None or re.Match
	if m:
		print "Video size detected: %s, %s" % (m.group(1), m.group(2))
		video_width = int(m.group(1))
		video_height = int(m.group(2))
	else:
		debug("Size of video is unknown")

	m = re.findall(r'Stream #(.+): Audio: (.+)', result)
	if m:
		audio_stream_list = m
	else:
		audio_stream_list = []

	return video_width, video_height, audio_stream_list


def estimate_visual_size(x, y, width, height, video_width, video_height):

	wg = float(width) / float(video_width)
	hg = float(height) / float(video_height)

	if (wg >= hg):
		visual_w = int(round(hg * video_width))
		visual_h = height
	else:
		visual_w = width
		visual_h = int(round(wg * video_height))
	debug("visual_w: %d, visual_h: %d" % (visual_w, visual_h))

	center_vertical_offset = 0
	center_horizon_offset = 0

	if (visual_w != width):
		center_horizon_offset = (width - visual_w) / 2
	if (visual_h != height):
		center_vertical_offset = (height - visual_h) / 2
	visual_x = int(round(x + center_horizon_offset))
	visual_y = int(round(y + center_vertical_offset))
	debug("visual_x: %d; visual_y: %d" % (visual_x, visual_y))
	return visual_x, visual_y, visual_w, visual_h


def run_console_command(cmd):
	return subprocess.call(cmd.split())

# http://www.raspberrypi.org/phpBB3/viewtopic.php?f=35&t=9789
def turn_off_cursor():
	run_console_command('setterm -cursor off')

def turn_on_cursor():
	run_console_command('setterm -cursor on')

def prevent_screensaver():
	run_console_command('setterm -blank off -powerdown off')



def kill_process(pid):
	try:
		os.kill(pid, signal.SIGKILL)
	except:
		pass


def terminate_self(signum, func):
	#~ global Service
	#~ Service.terminate_all_players()
	#~ remove_pid_file()
	#~ log("Terminate service (signal: %d)" % signum)
	#sys.exit(0) # this will be hang.
	os._exit(0)


def get_pid_filepath():
	'this service is run by nobody. it could not save pid to /var/run.'
	return "/tmp/omxplayer-dbus-service.pid"


def remove_pid_file():
	try:
		os.remove(get_pid_filepath())
	except:
		pass

			
