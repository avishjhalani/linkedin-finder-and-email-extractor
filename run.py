import os
import sys
import time
import webbrowser
import threading
import uvicorn

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://localhost:8000")

def main():
    port = int(os.getenv("PORT", 8000))
    print("=" * 60)
    print("  LinkedIn Finder & Email Extractor (YAMM-Ready)")
    print("=" * 60)
    print(f"Starting web server at http://localhost:{port} ...")
    
    # Only launch browser if running locally (not in headless cloud container)
    if os.getenv("RENDER") is None and os.getenv("DYNO") is None and os.getenv("SPACE_ID") is None:
        threading.Thread(target=open_browser, daemon=True).start()
    
    # Run uvicorn server
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    main()
