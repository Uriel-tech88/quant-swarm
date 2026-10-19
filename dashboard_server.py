
import http.server
import socketserver
import os

PORT = 9119
os.chdir(r'C:\\Users\\gqama\\AppData\\Local\\hermes\\quant_swarm\\backtests')

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Dashboard server running on port {PORT}")
    httpd.serve_forever()
