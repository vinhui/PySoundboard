import http.server
import http.server
import mimetypes
import os
import re
import tempfile

from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget

import config as cfg
from soundboard import Soundboard

if cfg.REQUIRES_AUTH or cfg.USE_ADMIN_AUTH:
    import base64


class StoppableHTTPServer(http.server.HTTPServer):
    def run(self):
        try:
            self.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            # Clean-up server (close socket, etc.)
            print("Stopping server")
            self.server_close()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        super(Handler, self).__init__(request, client_address, server)
        self.is_user = False
        self.is_admin = False

    def do_GET(self):
        # Construct a server response.
        try:
            if not self.check_auth():
                return

            if self.path.endswith(".js") or \
                    self.path.endswith(".html") or \
                    self.path.endswith(".css") or \
                    self.path.endswith(".ico") or \
                    self.path.endswith(".png") or \
                    self.path.endswith(".jpg"):
                f = self.send_head()
                if f:
                    self.copyfile(f, self.wfile)
                    f.close()
            else:
                if self.path == "/auth" and not self.is_user:
                    self.send_response(401)
                    self.send_header(
                        'WWW-Authenticate',
                        'Basic realm="Authenticate"')
                    self.end_headers()
                    return
                else:
                    self.send_response(200)
                    self.send_header('Content-type', "text/html")
                    self.end_headers()

                if str(self.path).startswith("/playsound/"):
                    name = str(self.path)[11:]
                    SOUNDBOARD.play_sound_by_name(name)
                    self.wfile.write(b"Attempting to play sound")
                elif self.path == "/reload/":
                    SOUNDBOARD.reload_config()
                    self.wfile.write(b"Config reloaded")
                else:
                    f = open(cfg.HTML_FILE, "r").read()
                    self.wfile.write(
                        self.parsefile(f).encode('utf-8')
                    )
        except Exception as ex:
            print("ERROR: {0}".format(ex))
            self.send_response(500)
            self.end_headers()
            if cfg.VERBOSE_LOGGING:
                raise ex

    def do_POST(self):
        try:
            if not self.check_auth(True):
                return

            self.send_response(200)
            self.send_header('Content-type', "text/html")
            self.end_headers()

            self.wfile.write(b"")
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            if self.path == "/upload-sound/":
                f = tempfile.NamedTemporaryFile(delete=False)
                f.close()

                file = FileTarget(f.name)
                parser = StreamingFormDataParser(headers=self.headers)
                parser.register("file", file)
                parser.data_received(post_data)
                mime, encoding = mimetypes.guess_type(file.multipart_filename)
                print("Received file '{0}' with mimetype '{1}'".format(file.multipart_filename, mime))
                if str(mime).startswith("audio"):
                    save_path = cfg.SOUNDS_DIR + "/" + file.multipart_filename
                    print("Saving file to '{0}'".format(save_path))
                    os.rename(f.name, save_path)
                    self.wfile.write(b"Sound saved")
                else:
                    os.remove(f.name)
                    self.wfile.write(b"Not a sound file!")
        except Exception as ex:
            print("ERROR: {0}".format(ex))
            self.send_response(500)
            self.end_headers()
            if cfg.VERBOSE_LOGGING:
                raise ex

    def log_message(self, format, *args):
        if cfg.VERBOSE_LOGGING:
            http.server.SimpleHTTPRequestHandler.log_message(self, format, *args)

    def check_auth(self, adminonly=False):
        success = True
        admin_correct = False
        user_correct = False

        authheader = self.headers['Authorization']
        if authheader and \
                authheader.startswith('Basic'):
            credentials = authheader.split(' ')[1]
            decoded = base64.b64decode(bytes(credentials, 'utf8')).decode('utf-8')
            user, password = decoded.split(":")

            admin_correct = \
                user == cfg.AUTH_ADMIN_USER and \
                password == cfg.AUTH_ADMIN_PASS

            user_correct = \
                user == cfg.AUTH_USER and \
                password == cfg.AUTH_PASS

        if cfg.REQUIRES_AUTH or \
                adminonly and cfg.USE_ADMIN_AUTH:
            success = (adminonly and admin_correct) or \
                      (not adminonly and (admin_correct or user_correct))

        if not success:
            if cfg.VERBOSE_LOGGING:
                print("Showing login prompt to user")
            message = "The PySoundboard requires login" if not adminonly \
                else "For this part you need to login as admin"
            self.send_response(401)
            self.send_header(
                'WWW-Authenticate',
                'Basic realm="' + message + '"')
            self.end_headers()

        self.is_user = user_correct or admin_correct
        self.is_admin = not cfg.USE_ADMIN_AUTH or admin_correct

        if success and cfg.VERBOSE_LOGGING:
            print("is user: {0}, is admin: {1}".format(self.is_user, self.is_admin))

        return success

    def parsefile(self, file):
        result = file
        if not self.is_admin:
            regex = re.compile(r"(\#admin.*?\#end)", re.IGNORECASE | re.DOTALL)
            result = re.sub(regex, '', result)
        else:
            result = result.replace("#admin", "")
            result = result.replace("#end", "")
        return result


if not os.path.exists(cfg.SOUNDS_DIR):
    os.makedirs(cfg.SOUNDS_DIR)

SOUNDBOARD = Soundboard()

if __name__ == '__main__':
    print('Server listening on port {0}...'.format(cfg.PORT))
    HTTPD = StoppableHTTPServer(('', cfg.PORT), Handler)
    HTTPD.run()
