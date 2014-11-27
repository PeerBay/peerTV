import subprocess
import web
import os
			
urls = (
'^/key/?(.*)$','key',
'^/char/?(.*)$','char',
'^/screen/$','screen',
'^/mouse/?(.*)$','mouse',

)
os.environ["DISPLAY"]=':0.0'
class char:
	def GET(self,key):
		web.header('Access-Control-Allow-Origin',      '*')
		subprocess.call(["xdotool","type",key])
class key:
	def GET(self,key):
		web.header('Access-Control-Allow-Origin',      '*')
		subprocess.call(["xdotool","key",key])
class screen:
	def GET(self):
		web.header('Access-Control-Allow-Origin',      '*')
		subprocess.call(["import" ,"-window", "root" ,"/root/modules/peerTv/static/screenshot.jpg"])		
class mouse:
	def GET(self,coords):
		web.header('Access-Control-Allow-Origin',      '*')
		c=coords.split("-")
		subprocess.call(["xdotool","mousemove",c[0],c[1],"click",c[2]])
	
class MyApplication(web.application):
    def run(self, port=8888, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', port))

if __name__ == "__main__":
    app = MyApplication(urls, globals())
    app.run(port=8888)
		
