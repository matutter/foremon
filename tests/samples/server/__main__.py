from http.server import HTTPServer, BaseHTTPRequestHandler

def run(server_class=HTTPServer, handler_class=BaseHTTPRequestHandler):
    server_address = ('', 0)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

if __name__ == '__main__':
    print('starting ...')
    try:
        run()
    except KeyboardInterrupt:
        print('\rstopped')
