#!/usr/bin/env python3
# 🌷 Ivy Research Assistant Launcher (Cross-platform)
# Handles environment setup, Notion OAuth connection, and launches main summarizer.

import os
import sys
import subprocess
import time
import platform
import secrets
import requests
import psutil
import webbrowser

ENV_DIR = "markit_env"
REQUIREMENTS_FILE = "requirements.txt"
MAIN_SCRIPT = "main.py"
LINODE_SERVER = "https://ivyllmnotion.io.vn"  # 🌐 Your public OAuth2 server


def run(cmd, check=True, shell=False, **kwargs):
    """Run a system command with live output."""
    try:
        return subprocess.run(cmd, check=check, shell=shell, **kwargs)
    except subprocess.CalledProcessError:
        print(f"⚠️  Command failed: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        if check:
            sys.exit(1)


def ensure_env():
    """Ensure virtual environment exists and dependencies installed."""
    if not os.path.isdir(ENV_DIR):
        print("⚙️  Creating new virtual environment...")
        run([sys.executable, "-m", "venv", ENV_DIR])

        pip_exe = os.path.join(
            ENV_DIR, "Scripts" if platform.system() == "Windows" else "bin", "pip"
        )
        print("📦 Installing dependencies...")
        run([pip_exe, "install", "--upgrade", "pip"])
        if os.path.isfile(REQUIREMENTS_FILE):
            run([pip_exe, "install", "-r", REQUIREMENTS_FILE])
        else:
            print("⚠️ No requirements.txt found.")
    else:
        print("🪄 Using existing environment.")


def get_env_value(key):
    """Read .env file for a variable."""
    if not os.path.isfile(".env"):
        return None
    with open(".env") as f:
        for line in f:
            if line.startswith(key + "="):
                return line.strip().split("=", 1)[1]
    return None


def save_to_env(key, value):
    """Append or update a key in .env file."""
    lines = []
    if os.path.exists(".env"):
        with open(".env") as f:
            lines = f.readlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith(key + "="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}\n")
    with open(".env", "w") as f:
        f.writelines(lines)


def verify_notion_token(token):
    """Check if the Notion token works."""
    try:
        res = requests.get(
            "https://api.notion.com/v1/users/me",
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
            },
            timeout=10,
        )
        if res.status_code == 200:
            data = res.json()
            workspace = data.get("bot", {}).get("workspace_name") or "Unknown"
            print(f"✅ Token verified — connected to workspace: {workspace}")
            return True
        else:
            print(f"❌ Notion verification failed ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        print(f"⚠️ Verification error: {e}")
        return False


def get_notion_token_from_server():
    """Connect to Linode OAuth2 server and retrieve Notion access token."""
    print("\n🌿 Connecting Ivy to your Notion workspace...")
    session_id = secrets.token_hex(8)

    # Step 1: open browser for user to log in
    auth_url = f"{LINODE_SERVER}/?session_id={session_id}"
    print(f"🌐 Opening browser: {auth_url}")
    webbrowser.open(auth_url)

    # Step 2: wait for server to process the callback
    print("⏳ Waiting for authorization (complete the Notion popup)...")
    token = None
    for _ in range(60):  # wait up to 60 seconds
        try:
            res = requests.get(f"{LINODE_SERVER}/api/get_token/{session_id}", timeout=5)
            if res.status_code == 200:
                data = res.json()
                token = data.get("access_token")
                if token:
                    print("🔑 Token received from Ivy server, verifying...")
                    if verify_notion_token(token):
                        save_to_env("NOTION_API_KEY", token)
                        print("💾 Token saved to .env successfully.")
                        return token
                    else:
                        print("🚫 Invalid Notion token. Aborting connection.")
                        sys.exit(1)
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)

    print("❌ Connection timeout or failed. Please try again.")
    sys.exit(1)

def start_extractor():
    """Check if MarkItDown extractor is running, otherwise start it."""
    url = "http://127.0.0.1:6000"

    # 🧹 Step 1 — Kill any stale Gunicorn process using port 6000
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'gunicorn' in (proc.info['name'] or '') and '127.0.0.1:6000' in ' '.join(proc.info.get('cmdline', [])):
                print(f"🧹 Killing old extractor process (PID {proc.info['pid']})...")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 🧠 Step 2 — Check if already running
    try:
        res = requests.get(url, timeout=2)
        if res.status_code == 200:
            print("✅ MarkItDown extractor already running on port 6000.")
            return
    except requests.exceptions.RequestException:
        pass

    # ⚙️ Step 3 — Start new Gunicorn process
    print("⚙️ Starting MarkItDown extractor on port 6000...")
    python_exe = os.path.join(
        ENV_DIR, "Scripts" if platform.system() == "Windows" else "bin", "python"
    )
    subprocess.Popen(
        [python_exe, "-m", "gunicorn", "-w", "2", "-b", "127.0.0.1:6000", "extractor:app"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 🔄 Step 4 — Wait for extractor to be ready
    for i in range(20):
        try:
            res = requests.get(url, timeout=2)
            if res.status_code == 200:
                print("✅ MarkItDown extractor started successfully.")
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)

    print("❌ Extractor failed to start within 20 seconds.")
    sys.exit(1)

def main():
    print("\n🌸 ------------------------------------------------------------")
    print("        Ivy — Your Personal Research Summarizer Assistant")
    print("------------------------------------------------------------ 🌸\n")

    # --- 1️⃣ Ensure Python env ready ---
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ is required.")
        sys.exit(1)
    ensure_env()

    # --- 2️⃣ Check Notion connection ---
    notion_token = get_env_value("NOTION_API_KEY")
    if not notion_token:
        notion_token = get_notion_token_from_server()
    else:
        print("🔑 Found existing Notion connection. Verifying...")
        if not verify_notion_token(notion_token):
            print("⚠️ Token invalid or expired — reconnecting...")
            notion_token = get_notion_token_from_server()

    # --- 3️⃣ Start extractor ---
    start_extractor()

    # --- 4️⃣ Run Ivy main summarizer ---
    python_exe = os.path.join(
        ENV_DIR, "Scripts" if platform.system() == "Windows" else "bin", "python"
    )
    print("\n🌿 Running Ivy — syncing your research papers with Notion...\n")
    run([python_exe, "main.py"])


if __name__ == "__main__":
    main()