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
    print("=" * 60)
    print("  LinkedIn Finder & Email Extractor (YAMM-Ready)")
    print("=" * 60)
    print("Starting web server at http://localhost:8000 ...")
    
    # Launch browser automatically in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run uvicorn server
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
