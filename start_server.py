import http.server
import socketserver
import webbrowser
import threading
import time
import sys
import os

PORT = 8000
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve from the workspace directory where index.html is located
        super().__init__(*args, directory=WORKSPACE_DIR, **kwargs)

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"\n=======================================================")
            print(f"  NHPC Weather Warning Dashboard local Web Server      ")
            print(f"=======================================================")
            print(f"  Serving files at: http://localhost:{PORT}/index.html")
            print(f"  Directory: {WORKSPACE_DIR}")
            print(f"  Press Ctrl+C to stop the server.")
            print(f"=======================================================\n")
            httpd.serve_forever()
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Start server in a background daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to bind port
    time.sleep(0.8)
    
    # Open dashboard in default web browser
    dashboard_url = f"http://localhost:{PORT}/index.html"
    print(f"Launching dashboard in your default browser...")
    webbrowser.open(dashboard_url)
    
    # Keep main process alive to maintain the server
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping local web server. Goodbye!")
        sys.exit(0)
