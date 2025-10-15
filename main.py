import os
import re
import json
import requests
from pathlib import Path
from fireworks.client import Fireworks
from datetime import datetime
from dotenv import load_dotenv  # ✅ NEW
from rich.console import Console
from rich.panel import Panel
from tqdm import tqdm


# ---------------- CONFIG ----------------
load_dotenv()

# ---------------- CONFIG ----------------
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
FIREWORK_API_KEY = os.getenv("FIREWORK_API_KEY")
MARKITDOWN_URL = os.getenv("MARKITDOWN_URL", "http://localhost:6000/extract")
FOLDER_NAME = os.getenv("FOLDER_NAME", "./Research_Papers")

fw = Fireworks(api_key=FIREWORK_API_KEY)
MODEL_NAME = os.getenv("MODEL_NAME", "accounts/fireworks/models/gpt-oss-20b")



# ---------------- MAIN ----------------
def main():
    print(f"🚀 Starting sync from {FOLDER_NAME}")
    folder = Path(FOLDER_NAME)

    if not folder.exists():
        print(f"❌ Folder not found: {FOLDER_NAME}")
        return

    pdf_files = list(folder.glob("*.pdf"))
    if not pdf_files:
        print("📂 No PDF files found.")
        return

    print(f"📚 Found {len(pdf_files)} PDF(s). Checking for new additions...")

    for filepath in tqdm(pdf_files, desc="📄 Processing papers", colour="magenta"):
        filename = filepath.name

        # Step 1 — check if file already recorded in Notion
        notion_page = find_notion_page_by_file_name(filename)
        if notion_page:
            print(f"✅ '{filename}' already in Notion — skipping reprocessing.")
            continue  # ⚡ Skip everything for existing files

        print(f"\n✨ New file detected: {filename}")
        text = extract_text_from_pdf(filepath)

        if not text.strip():
            print("⚠️ No text extracted — skipping...")
            continue
        
        # Step: compress text
        print("🪶 Paraphrasing & shortening extracted text...")
        compressed_text = compress_text_with_fireworks(text)

        summary_data = summarize_text(compressed_text)

        if not summary_data.get("one_sentence_summary", "").strip():
            print("⚠️ Empty summary — skipping...")
            continue

        # Step 2 — create a new record
        push_to_notion(filename, summary_data)

    print("\n✅ Sync complete — only new files were added.")
    
# ---------------- PDF EXTRACTOR ----------------
def extract_text_from_pdf(filepath: Path) -> str:
    """Try MarkItDown first, fallback to PyPDF2 if needed."""
    try:
        with open(filepath, "rb") as f:
            files = {"file": (filepath.name, f, "application/pdf")}
            res = requests.post(MARKITDOWN_URL, files=files, timeout=60)
            res.raise_for_status()
            data = res.json()
            if "text" in data and data["text"].strip():
                print("🧾 Extracted via MarkItDown ✅")
                return data["text"]
            raise ValueError("Empty MarkItDown response")
    except Exception as e:
        print(f"⚠️ MarkItDown failed ({e}), Unable to extracted-text - tried again")
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(filepath)
            text = " ".join(page.extract_text() or "" for page in reader.pages)
            print("🧾 Extracted again sucessfully ✅")
            return text.strip()
        except Exception as e2:
            print(f"❌ PyPDF2 failed: {e2}")
            return ""

# ---------------- Text-Compressor (Fireworks + LLM) ----------------
def compress_text_with_fireworks(text: str, model: str = MODEL_NAME) -> str:
    """
    Paraphrase and shorten the extracted text before summarization.
    Keeps core meaning, removes redundancy, and fits within ~1500 tokens.
    """
    if not text.strip():
        return ""

    prompt = f"""
    You are an efficient academic text compressor.

    Task:
    - Paraphrase and shorten the given text while keeping the main ideas, technical terms, and structure.
    - Remove redundancies, repeated phrasing, and irrelevant sections.
    - The output should be around 20-30% of the original length (~1500 tokens max).
    - Preserve meaning — do not summarize or alter conclusions.

    Text to compress:
    {text[:8000]}
    """

    try:
        response = fw.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise text compressor."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.2,
        )

        message = response.choices[0].message
        raw_output = (message.content or getattr(message, "reasoning_content", "") or "").strip()
        print("🪶 Text compressed successfully ✅")
        return raw_output

    except Exception as e:
        print(f"⚠️ Text compression failed: {e}")
        return text  # fallback to original
    
# ---------------- SUMMARIZER (Fireworks + LLM) ----------------
def summarize_text(text: str, style: str = "concise academic") -> dict:
    """Summarize academic text into structured fields."""
    if not text:
        return {k: "" for k in [
            "title", "objective", "methods", "results", "contributions", 
            "one_sentence_summary", "authors", "tags"
        ]}

    prompt = f"""
    You are a precise academic summarizer.

    Your goal:
    - Produce a **concise summary** in a **{style}** tone.
    - Ensure the output is strictly valid JSON (no markdown or commentary).
    - Each key must be short, factual, and written in clear academic English.

    Return ONLY a JSON object with these exact keys:
    - title
    - objective
    - methods
    - results
    - contributions
    - one_sentence_summary
    - authors (comma-separated)
    - tags (list of short keywords or research areas)

    Text to summarize (truncated if long):
    {text[:4000]}
    """

    try:
        response = fw.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful research assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,  # 🧠 hard limit on model output size
            temperature=0.3,
        )

        # Safely handle None or reasoning-only responses
        
        message = response.choices[0].message
        raw_output = (message.content or getattr(message, "reasoning_content", "") or "").strip()
        # Extract JSON portion safely
        json_start = raw_output.find("{")
        json_end = raw_output.rfind("}") + 1
        json_str = raw_output[json_start:json_end]
        data = json.loads(json_str)

        # Ensure all keys exist
        for k in ["title", "objective", "methods", "results", "contributions", "one_sentence_summary", "authors", "tags"]:
            data.setdefault(k, "" if k != "tags" else [])

        print("🧠 Structured summary generated ✅")
        return data

    except Exception as e:
        print(f"⚠️ Fireworks summarization failed: {e}")
        sentences = re.findall(r"[^.!?]+[.!?]+", text)
        return {
            "title": "",
            "objective": "",
            "methods": "",
            "results": "",
            "contributions": "",
            "one_sentence_summary": " ".join(sentences[:3]) if sentences else text[:300],
            "authors": "",
            "tags": [],
        }

# ---------------- NOTION HELPERS ----------------
def find_notion_page_by_title(title: str):
    """Search Notion database for an existing page by title."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    payload = {"filter": {"property": "Title", "title": {"equals": title}}}

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        results = data.get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"⚠️ Notion query failed: {e}")
        return None

def normalize_text(value):
    """Ensure the value is a string, flattening lists or dicts."""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)

def find_notion_page_by_file_name(file_name: str):
    """Search Notion database for an existing page by File-Name (used as primary key)."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    payload = {"filter": {"property": "File-Name", "rich_text": {"equals": file_name}}}

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        results = data.get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"⚠️ Notion query failed: {e}")
        return None

def update_notion_summary(page_id: str, summary_data: dict, file_name: str = ""):
    """Update structured properties in an existing Notion page (no upload, only local file reference)."""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    payload = {
        "properties": {
            "Objective": {"rich_text": [{"text": {"content": normalize_text(summary_data.get("objective", ""))}}]},
            "Methods": {"rich_text": [{"text": {"content": normalize_text(summary_data.get("methods", ""))}}]},
            "Results": {"rich_text": [{"text": {"content": normalize_text(summary_data.get("results", ""))}}]},
            "Contributions": {"rich_text": [{"text": {"content": normalize_text(summary_data.get("contributions", ""))}}]},
            "Summary": {"rich_text": [{"text": {"content": normalize_text(summary_data.get("one_sentence_summary", ""))}}]},
            "Author": {"rich_text": [{"text": {"content": normalize_text(summary_data.get("authors", ""))}}]},
            "Tag": {"multi_select": [{"name": normalize_text(t)} for t in summary_data.get("tags", [])]},
            "Status": {"select": {"name": "Updated"}},
            # 👇 record the local filename as reference (no upload)
            "File-Name": {"rich_text": [{"text": {"content": normalize_text(file_name or summary_data.get('title', ''))}}]},
        }
    }

    res = requests.patch(url, json=payload, headers=headers, timeout=30)
    if res.status_code >= 400:
        print(f"❌ Notion update failed ({res.status_code}): {res.text}")
    else:
        print(f"✅ Updated Notion page: {summary_data.get('title', 'Untitled')} ({file_name})")

def push_to_notion(name: str, summary_data: dict):
    """Create a new Notion page with structured summary fields (no file upload, only local file reference)."""
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Title": {"title": [{"text": {"content": normalize_text(summary_data.get('title') or name)}}]},
            "Objective": {"rich_text": [{"text": {"content": normalize_text(summary_data.get('objective', ''))}}]},
            "Methods": {"rich_text": [{"text": {"content": normalize_text(summary_data.get('methods', ''))}}]},
            "Results": {"rich_text": [{"text": {"content": normalize_text(summary_data.get('results', ''))}}]},
            "Contributions": {"rich_text": [{"text": {"content": normalize_text(summary_data.get('contributions', ''))}}]},
            "Summary": {"rich_text": [{"text": {"content": normalize_text(summary_data.get('one_sentence_summary', ''))}}]},
            "Author": {"rich_text": [{"text": {"content": normalize_text(summary_data.get('authors', ''))}}]},
            "Tag": {"multi_select": [{"name": normalize_text(t)} for t in summary_data.get("tags", [])]},
            "Status": {"select": {"name": "To Read"}},
            "Date-Added": {"date": {"start": datetime.now().astimezone().isoformat()}},
            # 👇 Record local file name as a reference
            "File-Name": {"rich_text": [{"text": {"content": normalize_text(name)}}]},
        },
    }

    res = requests.post(url, json=payload, headers=headers, timeout=30)
    if res.status_code >= 400:
        print(f"❌ Notion API Error ({res.status_code}): {res.text}")
    else:
        print(f"✅ Added new page: {summary_data.get('title', name)} ({name})")
# ---------------- ENTRY ----------------
if __name__ == "__main__":
    console = Console()
    console.print(Panel.fit(
        f"🌷 [bold magenta]Welcome to Ivy![/bold magenta]\n"
        f"Your personal research summarizer 🌸\n\n"
        f"📂 Watching folder: [bold]{FOLDER_NAME}[/bold]\n"
        "🧠 Ready to extract and summarize papers into Notion.\n\n"
        "Tip: Drop any new PDF in the folder and let Ivy do the rest ✨",
        border_style="magenta"
    ))

    main()