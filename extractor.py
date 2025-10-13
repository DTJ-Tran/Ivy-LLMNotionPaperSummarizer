from flask import Flask, request, jsonify
from flask_cors import CORS
from markitdown import MarkItDown
import tempfile, os

app = Flask(__name__)
CORS(app)  # 👈 allow cross-origin requests

md = MarkItDown()

@app.route("/extract", methods=["POST"])
def extract():
    file = request.files["file"]
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        file.save(tmp.name)
        markdown_text = md.convert(tmp.name).text_content
        os.remove(tmp.name)
        return jsonify({"text": markdown_text})

if __name__ == "__main__":
    app.run(port=6000)