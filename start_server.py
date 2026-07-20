import http.server
import socketserver
import webbrowser
import threading
import time
import sys
import os

PORT = 8000
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(WORKSPACE_DIR, "web")

import json
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve from the web subfolder
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        # Intercept weather forecast requests for arbitrary coordinates
        if self.path.startswith('/api/forecast'):
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            lat_param = query_params.get('lat')
            lon_param = query_params.get('lon')
            name_param = query_params.get('name')
            
            if not lat_param or not lon_param:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Latitude and longitude parameters are required."}).encode('utf-8'))
                return
                
            try:
                lat = float(lat_param[0])
                lon = float(lon_param[0])
                name = name_param[0] if name_param else f"Coordinates ({lat:.4f}, {lon:.4f})"
                
                # Import libraries dynamically to prevent potential issues
                import imd_ping
                import update_forecasts
                
                # Fetch model base date to determine forecast intervals
                try:
                    model_str = imd_ping.get_model()
                    start_utc = datetime.strptime(model_str, "%Y%m%d%H")
                    start_ist = start_utc + timedelta(hours=5, minutes=30)
                except Exception as e:
                    print(f"Error fetching model date: {e}")
                    start_ist = datetime.now()
                
                print(f"[API Server] Fetching on-demand forecast for custom location: {name} ({lat}, {lon})")
                forecast_raw = imd_ping.get_forecast(lat, lon)
                analysis = update_forecasts.analyze_forecast(forecast_raw["forecast"], start_ist)
                
                plant_result = {
                    "id": "custom-" + f"{lat:.4f}-{lon:.4f}".replace(".", "-").replace("-", "_"),
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "boundaries": [],
                    "alert_level": analysis["alert_level"],
                    "reasons": analysis["reasons"],
                    "summary": analysis["summary"],
                    "forecast": analysis["details"]
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(plant_result).encode('utf-8'))
                
            except Exception as e:
                print(f"[API Server] Error processing forecast API request: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return
            
        super().do_GET()

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"\n=======================================================")
            print(f"  NHPC Weather Warning Dashboard local Web Server      ")
            print(f"=======================================================")
            print(f"  Serving files at: http://localhost:{PORT}/index.html")
            print(f"  Directory: {WEB_DIR}")
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
