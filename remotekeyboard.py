import subprocess
import web
import Xlib.XK
			
urls = (
'^/keycode/?(.*)$','keycode',
'^/char/?(.*)$','char',

)

class char:
	def GET(self,key):
		subprocess.call(["xdotool","key",key])

		
	
class MyApplication(web.application):
    def run(self, port=8080, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', port))

if __name__ == "__main__":
    app = MyApplication(urls, globals())
    app.run(port=8888)
		
