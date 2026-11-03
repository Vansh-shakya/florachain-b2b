"""
FloraChain B2B — Legacy Static HTTP Server (Fallback & Rollback Script)
Phase 2-4: Standalone Static Prototype Runner

Usage:
    python run_legacy.py
"""

import http.server
import socketserver
import webbrowser
import os
import sys

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def log_message(self, format, *args):
        sys.stdout.write(f"[Legacy Server] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()

def find_available_port(start_port=8000, max_attempts=10):
    import socket
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

def start_server():
    os.chdir(BASE_DIR)
    port = find_available_port(8000)
    url = f"http://127.0.0.1:{port}/index.html"

    print("=" * 60)
    print("🌿 FloraChain B2B — Legacy Static Prototype Server")
    print("=" * 60)
    print(f"🚀 Running at: {url}")
    print("=" * 60 + "\n")

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), QuietHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Legacy Server stopped.")

if __name__ == "__main__":
    start_server()
