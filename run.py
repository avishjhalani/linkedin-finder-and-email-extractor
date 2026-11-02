import os
import sys
import webbrowser
import threading
import time
from pathlib import Path
import uvicorn

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

import socket

# Load .env file
env_file = ROOT_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

desired_port = int(os.environ.get("PORT", 8000))

def find_free_port(start_port: int, max_attempts: int = 10) -> int:
    """Finds the first available port if start_port is currently busy."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port

PORT = find_free_port(desired_port)

# Configure utf-8 stdout encoding for Windows compatibility
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://localhost:{PORT}")

if __name__ == "__main__":
    if PORT != desired_port:
        print(f"[!] Port {desired_port} is busy. Switched to free port {PORT}.")
    print(f"[*] Starting LinkedIn HR & Executive Lead Finder on http://localhost:{PORT}")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=False)
