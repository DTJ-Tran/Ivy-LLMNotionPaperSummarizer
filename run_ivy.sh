#!/bin/bash
# 🌷 Ivy Research Assistant Launcher
# A smart startup script for your paper summarization + Notion sync workflow
# Handles environment setup, dependency installation, and service orchestration automatically.

# --- SETTINGS ---
ENV_DIR="markit_env"
REQUIREMENTS_FILE="requirements.txt"
EXTRACTOR_APP="extractor:app"
MAIN_SCRIPT="main.py"
EXTRACTOR_PORT=6000

echo ""
echo "🌸 ------------------------------------------------------------"
echo "        Ivy — Your Personal Research Summarizer Assistant"
echo "------------------------------------------------------------ 🌸"
echo ""

# --- 1️⃣ Check Python ---
if ! command -v python3 &> /dev/null; then
  echo "❌ Python 3 not found. Please install Python 3.9+ before running Ivy."
  exit 1
fi

# --- 2️⃣ Check or Create Virtual Environment ---
if [ ! -d "$ENV_DIR" ]; then
  echo "⚙️  No virtual environment found. Setting up a new one..."
  python3 -m venv "$ENV_DIR"
  source "$ENV_DIR/bin/activate"

  if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "📦 Installing dependencies..."
    pip install --upgrade pip
    pip install -r "$REQUIREMENTS_FILE"
  else
    echo "⚠️  No requirements.txt found — please ensure it’s included in your package."
  fi

  echo "✅ Environment setup complete."
else
  echo "🪄 Activating existing environment..."
  source "$ENV_DIR/bin/activate"
fi

# --- 3️⃣ Ensure Gunicorn is Installed ---
if ! command -v gunicorn &> /dev/null; then
  echo "📦 Installing Gunicorn (for Flask backend)..."
  pip install gunicorn
fi

# --- 4️⃣ Start MarkItDown Extractor Backend ---
echo ""
echo "🧾 Starting MarkItDown extractor on port $EXTRACTOR_PORT..."
export FLASK_ENV=production
gunicorn -w 2 -b 0.0.0.0:$EXTRACTOR_PORT $EXTRACTOR_APP > extractor.log 2>&1 &
EXTRACTOR_PID=$!

sleep 3
if ps -p $EXTRACTOR_PID > /dev/null; then
  echo "✅ MarkItDown extractor running (PID: $EXTRACTOR_PID)"
else
  echo "❌ Failed to start extractor. Check extractor.log for details."
  deactivate
  exit 1
fi

# --- 5️⃣ Run Ivy Main Summarizer ---
echo ""
echo "🌿 Running Ivy — syncing your research papers with Notion..."
python "$MAIN_SCRIPT"

MAIN_EXIT=$?

# --- 6️⃣ Cleanup ---
echo ""
echo "🪶 Shutting down MarkItDown extractor..."
kill $EXTRACTOR_PID 2>/dev/null
wait $EXTRACTOR_PID 2>/dev/null

# --- 7️⃣ Finish Message ---
if [ $MAIN_EXIT -eq 0 ]; then
  echo ""
  echo "🌷 ------------------------------------------------------------"
  echo " Ivy has finished syncing your papers successfully! ✨"
  echo " You can drop new PDFs into ./Research_Papers anytime."
  echo "------------------------------------------------------------ 🌷"
else
  echo "⚠️  Ivy encountered an error. Please check the console output."
fi

# --- 8️⃣ Deactivate Virtual Environment ---
deactivate