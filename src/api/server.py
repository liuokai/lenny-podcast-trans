from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os
import json
from bs4 import BeautifulSoup
import sys

# Ensure project root is on sys.path for 'src.*' imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.settings import EPISODES_DIR, EPISODES_CONFIG_PATH
from src.infra.deepseek_client import translate_text_strict

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))
CORS(app)

def list_episodes():
    items = []
    base = EPISODES_DIR
    if not os.path.exists(base):
        return items
    for slug in os.listdir(base):
        ep_dir = os.path.join(base, slug)
        if not os.path.isdir(ep_dir):
            continue
        items.append({
            "slug": slug,
            "has_transcript": os.path.exists(os.path.join(ep_dir, "transcript.txt")),
            "has_bilingual": os.path.exists(os.path.join(ep_dir, "transcript_bilingual.txt")),
        })
    return items

def load_bilingual(slug: str):
    path = os.path.join(EPISODES_DIR, slug, "transcript_bilingual.txt")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    segments = []
    current = {"speaker": None, "english": "", "chinese": ""}
    mode = "none"
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and "]: " in line:
            if current["speaker"] or current["english"] or current["chinese"]:
                current["english"] = current["english"].strip()
                current["chinese"] = current["chinese"].strip()
                segments.append(current)
            speaker = line[1:line.index("]: ")].strip()
            text = line[line.index("]: ") + 3 :]
            current = {"speaker": speaker, "english": text, "chinese": ""}
            mode = "english"
            continue
        if line.startswith("(中文):"):
            text = line[len("(中文):"):].strip()
            current["chinese"] = text
            mode = "chinese"
            continue
        if mode == "english":
            current["english"] += " " + line
        elif mode == "chinese":
            current["chinese"] += "\n" + line
    if current["speaker"] or current["english"] or current["chinese"]:
        current["english"] = current["english"].strip()
        current["chinese"] = current["chinese"].strip()
        segments.append(current)
    return segments

def load_titles(slug: str):
    path = os.path.join(EPISODES_DIR, slug, "page_content.html")
    title_en = "Lenny's Podcast Transcript"
    title_zh = "Lenny的播客成绩单"
    if not os.path.exists(path):
        return title_en, title_zh
    try:
        with open(path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        tag = soup.find("title")
        if tag and tag.string:
            title_en = tag.string.strip()
            # 简单调用翻译
            try:
                title_zh = translate_text_strict(title_en)
            except Exception:
                title_zh = title_en
    except Exception:
        pass
    return title_en, title_zh

@app.route("/")
def index():
    # 默认展示第一个已生成双语的节目
    eps = list_episodes()
    slug = None
    for e in eps:
        if e["has_bilingual"]:
            slug = e["slug"]
            break
    if slug is None and eps:
        slug = eps[0]["slug"]
    title_en, title_zh = load_titles(slug) if slug else ("Lenny's Podcast Transcript", "Lenny的播客成绩单")
    return render_template("index.html", title_en=title_en, title_zh=title_zh, slug=slug)

@app.route("/api/episodes")
def api_episodes():
    return jsonify(list_episodes())

@app.route("/api/transcript")
def api_transcript():
    slug = request.args.get("slug")
    if not slug:
        return jsonify([])
    data = load_bilingual(slug)
    return jsonify(data)

@app.route("/api/translate", methods=["POST"])
def api_translate_segment():
    payload = request.json or {}
    english_text = payload.get("text")
    slug = payload.get("slug")
    index = payload.get("index")
    if not english_text or not slug:
        return jsonify({"error": "缺少必要参数"}), 400
    try:
        translation = translate_text_strict(english_text)
        # 保存回文件
        path = os.path.join(EPISODES_DIR, slug, "transcript_bilingual.txt")
        segments = load_bilingual(slug)
        if isinstance(index, int) and 0 <= index < len(segments):
            segments[index]["chinese"] = translation
            with open(path, "w", encoding="utf-8") as f:
                for seg in segments:
                    f.write(f"[{seg['speaker']}]: {seg['english']}\n")
                    f.write(f"(中文): {seg['chinese']}\n\n")
        return jsonify({"translation": translation})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/title")
def api_title():
    slug = request.args.get("slug")
    if not slug:
        return jsonify({"title_en": "Lenny's Podcast Transcript", "title_zh": "Lenny的播客成绩单"})
    title_en, title_zh = load_titles(slug)
    return jsonify({"title_en": title_en, "title_zh": title_zh})

if __name__ == "__main__":
    app.run(port=5001, debug=True)
