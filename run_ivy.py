#!/usr/bin/env python3
# 🌷 Ivy Research Assistant Launcher (Cross-platform, Python version)
# A user-friendly launcher for your research summarization + Notion sync workflow.
# Handles environment setup, dependency installation, and backend orchestration automatically.

import os
import sys
import subprocess
import time
import platform
import shutil

# --- SETTINGS ---
ENV_DIR = "markit_env"
REQUIREMENTS_FILE = "requirements.txt"
EXTRACTOR_APP = "extractor:app"
MAIN_SCRIPT = "main.py"
EXTRACTOR_PORT = 6000

print("\n🌸 ------------------------------------------------------------")
print("        Ivy — Your Personal Research Summarizer Assistant")
print("------------------------------------------------------------ 🌸\n")

# --- 1️⃣ Check Python ---
if sys.version_info < (3, 9):
    print("❌ Python 3.9+ is required. Please upgrade your Python installation.")
    sys.exit(1)

# --- Utility functions ---
def run(cmd, check=True, shell=False, **kwargs):
    """Run a system command with live output."""
    try:
        return subprocess.run(cmd, check=check, shell=shell, **kwargs)
    except subprocess.CalledProcessError:
        print(f"⚠️  Command failed: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        if check:
            sys.exit(1)

def activate_env():
    """Activate the virtual environment for subprocesses."""
    if platform.system() == "Windows":
        activate_script = os.path.join(ENV_DIR, "Scripts", "activate")
    else:
        activate_script = os.path.join(ENV_DIR, "bin", "activate")
    return activate_script

def in_venv():
    return sys.prefix != sys.base_prefix

# --- 2️⃣ Check or Create Virtual Environment ---
if not os.path.isdir(ENV_DIR):
    print("⚙️  No virtual environment found. Creating one...")
    run([sys.executable, "-m", "venv", ENV_DIR])

    pip_exe = os.path.join(ENV_DIR, "Scripts" if platform.system() == "Windows" else "bin", "pip")

    if os.path.isfile(REQUIREMENTS_FILE):
        print("📦 Installing dependencies...")
        run([pip_exe, "install", "--upgrade", "pip"])
        run([pip_exe, "install", "-r", REQUIREMENTS_FILE])
    else:
        print("⚠️  No requirements.txt found — please ensure it’s included in your package.")

    print("✅ Environment setup complete.\n")
else:
    print("🪄 Using existing virtual environment.\n")

# --- 3️⃣ Ensure Gunicorn is Installed ---
pip_exe = os.path.join(ENV_DIR, "Scripts" if platform.system() == "Windows" else "bin", "pip")
try:
    subprocess.run([pip_exe, "show", "gunicorn"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except Exception:
    print("📦 Installing Gunicorn...")
    run([pip_exe, "install", "gunicorn"])

# --- 4️⃣ Start MarkItDown Extractor Backend ---
print(f"🧾 Starting MarkItDown extractor on port {EXTRACTOR_PORT}...")
env = os.environ.copy()
env["FLASK_ENV"] = "production"

python_exe = os.path.join(ENV_DIR, "Scripts" if platform.system() == "Windows" else "bin", "python")

extractor_cmd = [
    python_exe, "-m", "gunicorn",
    "-w", "2",
    "-b", f"0.0.0.0:{EXTRACTOR_PORT}",
    EXTRACTOR_APP
]

with open("extractor.log", "w") as log_file:
    extractor_proc = subprocess.Popen(extractor_cmd, stdout=log_file, stderr=log_file, env=env)

time.sleep(3)
if extractor_proc.poll() is None:
    print(f"✅ MarkItDown extractor running (PID: {extractor_proc.pid})")
else:
    print("❌ Failed to start extractor. Check extractor.log for details.")
    sys.exit(1)

# --- 5️⃣ Run Ivy Main Summarizer ---
print("\n🌿 Running Ivy — syncing your research papers with Notion...\n")
try:
    result = run([python_exe, MAIN_SCRIPT], check=False)
    main_exit = result.returncode
except KeyboardInterrupt:
    print("\n🛑 Interrupted by user.")
    main_exit = 1

# --- 6️⃣ Cleanup ---
print("\n🪶 Shutting down MarkItDown extractor...")
extractor_proc.terminate()
try:
    extractor_proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    extractor_proc.kill()

# --- 7️⃣ Finish Message ---
print("")
if main_exit == 0:
    print("🌷 ------------------------------------------------------------")
    print(" Ivy has finished syncing your papers successfully! ✨")
    print(" You can drop new PDFs into ./Research_Papers anytime.")
    print("------------------------------------------------------------ 🌷\n")
else:
    print("⚠️  Ivy encountered an error. Please check the console output.\n")