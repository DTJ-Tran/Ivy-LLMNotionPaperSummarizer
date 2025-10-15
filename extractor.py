from flask import Flask, request, jsonify
from flask_cors import CORS
from markitdown import MarkItDown
import tempfile, os

app = Flask(__name__)
CORS(app)  # 👈 allow cross-origin requests

md = MarkItDown()

# 🩵 Add a simple GET health check route
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "MarkItDown extractor is running."})

@app.route("/extract", methods=["POST"])
def extract():
    """Convert uploaded PDF file to Markdown text."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file.save(tmp.name)
            markdown_text = md.convert(tmp.name).text_content
        os.remove(tmp.name)
        return jsonify({"text": markdown_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=6000)