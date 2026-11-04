"""
FloraChain B2B — Nursery Supply Platform
Stage 2: Flask Application Server with Authentication & RBAC

Usage:
    python run.py

Rollback:
    python run_legacy.py (Restores standalone static prototype server)
"""

import sys
import os
import socket
import webbrowser

# Enable demo role switcher explicitly for local development runtime
os.environ.setdefault('FLORACHAIN_ALLOW_DEMO_ROLE_SWITCH', 'true')

from app import create_app

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def find_available_port(start_port=8000, max_attempts=10):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return start_port

def start_server():
    os.chdir(BASE_DIR)
    port = find_available_port(8000)
    url = f"http://127.0.0.1:{port}/"

    print("=" * 68)
    print("🌿 FloraChain B2B — Nursery Supply Platform")
    print("=" * 68)
    print(f"🚀 Server running at:       {url}")
    print(f"📁 Serving frontend from:   {BASE_DIR}")
    print(f"🗄️ Database initialized at: data/florachain.db (WAL mode)")
    print(f"🌐 Health endpoint:         http://127.0.0.1:{port}/api/health")
    print(f"🔑 Auth endpoint:           http://127.0.0.1:{port}/api/auth/login")
    print(f"🎛️ Demo Role Switcher:      Enabled (local development runner)")
    print("⏹️  To stop the server, press Ctrl + C in this terminal window.")
    print("=" * 68 + "\n")

    app = create_app()

    import threading
    def _open_browser_when_ready():
        import time
        time.sleep(1.0)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 FloraChain B2B Server stopped successfully.")

if __name__ == "__main__":
    start_server()
