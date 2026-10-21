"""One-command launcher: creates a private virtual environment, installs packages, starts Crave and opens the browser.
Usage:  python run.py        (Windows: double-click run.bat   |   Mac/Linux: ./run.sh)"""
import os, socket, subprocess, sys, threading, venv, webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
BACK, VENV = os.path.join(ROOT, "backend"), os.path.join(ROOT, ".venv")
VPY = os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")

def free_port(start=8000):
    for p in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    sys.exit("No free port between 8000 and 8019. Close other programs and try again.")

def main():
    if sys.version_info < (3, 9):
        sys.exit(f"Python 3.9 or newer is required (you have {sys.version.split()[0]}). Download it from python.org.")
    if os.path.abspath(sys.prefix) != os.path.abspath(VENV):          # step 1: set up the private environment
        if not os.path.exists(VPY):
            print("Creating a private Python environment (first run only)...")
            venv.create(VENV, with_pip=True)
        print("Installing packages (first run takes about a minute)...")
        subprocess.check_call([VPY, "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", os.path.join(BACK, "requirements.txt")])
        sys.exit(subprocess.call([VPY, os.path.abspath(__file__)]))   # step 2: re-run inside it
    sys.path.insert(0, BACK); os.chdir(BACK)
    import uvicorn
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    print(f"\n  Crave is running at {url}\n  Admin: admin@crave.test / admin1234   Customer: ayesha@mail.test / demo1234\n  Press Ctrl+C to stop.\n")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("main:app", host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    main()
