from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import re
import os
from src.infra.deepseek_client import translate_text_strict
from src.config.settings import DEEPSEEK_API_KEY
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

if not DEEPSEEK_API_KEY:
    print("警告：未检测到 DEEPSEEK_API_KEY，DeepSeek 相关功能将不可用。")

TRANSCRIPT_FILE = "transcript_bilingual.txt"
HTML_FILE = "page_content.html"

# Global variable to cache title
PODCAST_TITLE = {"en": "Lenny's Podcast Transcript", "zh": "Lenny的播客成绩单"}

def get_podcast_title():
    """Extracts title from HTML and translates it if not already cached."""
    global PODCAST_TITLE
    
    # If we already have a custom title (not default), return it
    if PODCAST_TITLE["en"] != "Lenny's Podcast Transcript":
        return PODCAST_TITLE

    if not os.path.exists(HTML_FILE):
        return PODCAST_TITLE

    try:
        with open(HTML_FILE, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            full_title = title_tag.string.strip()
            # Clean up title (remove " | Sander Schulhoff" etc if needed, but user said "original title")
            # We'll keep the full title.
            PODCAST_TITLE["en"] = full_title
            
            # Translate title
            try:
                PODCAST_TITLE["zh"] = translate_text_strict(full_title)
            except Exception as e:
                print(f"Error translating title: {e}")
                PODCAST_TITLE["zh"] = full_title # Fallback

    except Exception as e:
        print(f"Error extracting title: {e}")

    return PODCAST_TITLE

def parse_transcript():
    """Parses the bilingual transcript into a list of dictionaries."""
    if not os.path.exists(TRANSCRIPT_FILE):
        return []

    with open(TRANSCRIPT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    segments = []
    current_segment = {"speaker": None, "english": "", "chinese": ""}
    mode = "none"  # "english", "chinese"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for Speaker pattern: [Name]:
        match_speaker = re.match(r'^\[(.*?)]: (.*)', line)
        if match_speaker:
            # Save previous segment
            if current_segment['speaker'] or current_segment['english'] or current_segment['chinese']:
                current_segment['english'] = current_segment['english'].strip()
                current_segment['chinese'] = current_segment['chinese'].strip()
                segments.append(current_segment)

            speaker = match_speaker.group(1)
            text = match_speaker.group(2)
            current_segment = {"speaker": speaker, "english": text, "chinese": ""}
            mode = "english"
            continue

        # Check for Chinese marker: (中文):
        if line.startswith("(中文):"):
            text = line[len("(中文):"):].strip()
            current_segment['chinese'] = text
            mode = "chinese"
            continue

        # Append to current mode
        if mode == "english":
            current_segment['english'] += " " + line
        elif mode == "chinese":
            current_segment['chinese'] += "\n" + line # Preserve newlines for Chinese if any

    # Add last segment
    if current_segment['speaker'] or current_segment['english'] or current_segment['chinese']:
        current_segment['english'] = current_segment['english'].strip()
        current_segment['chinese'] = current_segment['chinese'].strip()
        segments.append(current_segment)
        
    return segments

def save_transcript(segments):
    """Saves the segments back to the file in the correct format."""
    try:
        with open(TRANSCRIPT_FILE, 'w', encoding='utf-8') as f:
            for segment in segments:
                speaker = segment['speaker']
                english = segment['english']
                chinese = segment['chinese']
                
                f.write(f"[{speaker}]: {english}\n")
                f.write(f"(中文): {chinese}\n")
                f.write("\n") # Empty line between segments
        return True
    except Exception as e:
        print(f"Error saving transcript: {e}")
        return False

@app.route('/')
def index():
    titles = get_podcast_title()
    return render_template('index.html', title_en=titles['en'], title_zh=titles['zh'])

@app.route('/api/transcript')
def get_transcript():
    data = parse_transcript()
    return jsonify(data)

@app.route('/api/translate', methods=['POST'])
def translate_segment():
    data = request.json
    english_text = data.get('text')
    index = data.get('index') # Get the index of the segment to update
    
    if not english_text:
        return jsonify({"error": "No text provided"}), 400

    try:
        # 1. Perform Translation
        translated_text = translate_text_strict(english_text)

        # 2. Update File if index is provided
        if index is not None and isinstance(index, int):
            segments = parse_transcript()
            if 0 <= index < len(segments):
                segments[index]['chinese'] = translated_text
                save_transcript(segments)
            else:
                print(f"Warning: Index {index} out of bounds")

        return jsonify({"translation": translated_text})
    except Exception as e:
        print(f"Translation error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Initialize title on startup
    get_podcast_title()
    app.run(port=5001, debug=True)
