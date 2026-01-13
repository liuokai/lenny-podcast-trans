import os
import time
import json
from src.service.scrape_service import scrape_to_files, slug_from_url
from src.service.translate_service import translate_file
from src.config.settings import EPISODES_DIR, EPISODES_CONFIG_PATH

CONFIG_PATH = EPISODES_CONFIG_PATH
BASE_DIR = EPISODES_DIR

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def process_episode(url):
    slug, input_path = scrape_to_files(url)
    output_path = os.path.join(BASE_DIR, slug, "transcript_bilingual.txt")
    translate_file(input_path, output_path)
    return True

def run_once():
    data = load_config()
    changed = False
    for ep in data.get("episodes", []):
        if ep.get("status") != "completed":
            ok = process_episode(ep["url"])
            ep["status"] = "completed" if ok else "error"
            changed = True
    if changed:
        save_config(data)

def watch_loop():
    last_mtime = os.path.getmtime(CONFIG_PATH)
    run_once()
    while True:
        try:
            time.sleep(2)
            mtime = os.path.getmtime(CONFIG_PATH)
            if mtime != last_mtime:
                last_mtime = mtime
                run_once()
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR, exist_ok=True)
    watch_loop()
