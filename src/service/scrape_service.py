import os
import re
import json
import requests
from bs4 import BeautifulSoup
from src.config.settings import EPISODES_DIR

def slug_from_url(url: str) -> str:
    path = url.split("?")[0]
    parts = path.strip("/").split("/")
    if "p" in parts:
        idx = parts.index("p")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return parts[-1] if parts else "episode"

def fetch_page(url: str) -> str:
    r = requests.get(url)
    r.raise_for_status()
    return r.text

def extract_preloads(soup: BeautifulSoup):
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and "window._preloads" in script.string:
            m = re.search(r'window\._preloads\s*=\s*JSON\.parse\("(.+?)"\)', script.string)
            if m:
                raw = m.group(1)
                try:
                    unescaped = raw.encode('utf-8').decode('unicode_escape')
                    return json.loads(unescaped)
                except Exception:
                    continue
    return None

def find_transcript_url(data: dict) -> str:
    url = None
    if 'post' in data and 'podcastUpload' in data['post']:
        upload = data['post']['podcastUpload']
        if upload and 'transcription' in upload:
            url = upload['transcription'].get('transcript_url')
    if url:
        return url
    found_urls = []
    def walk(obj):
        if isinstance(obj, dict):
            for _, v in obj.items():
                if isinstance(v, str) and "transcription.json" in v and "http" in v:
                    found_urls.append(v)
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
    walk(data)
    if found_urls:
        return found_urls[0]
    return None

def resolve_signed_http(transcript_url: str, data: dict) -> str:
    if not transcript_url.startswith("s3://"):
        return transcript_url
    path_part = transcript_url.replace("s3://substack-video/", "")
    def find_signed(obj):
        if isinstance(obj, dict):
            for _, v in obj.items():
                if isinstance(v, str) and path_part in v and "http" in v:
                    return v
                res = find_signed(v)
                if res:
                    return res
        elif isinstance(obj, list):
            for item in obj:
                res = find_signed(item)
                if res:
                    return res
        return None
    http_url = find_signed(data)
    if not http_url:
        raise RuntimeError("未找到已签名的 HTTP transcript URL")
    return http_url

def detect_speakers(data: dict) -> tuple[str, str]:
    host = "Host"
    guest = "Guest"
    if 'post' in data and 'publishedBylines' in data['post']:
        bylines = data['post']['publishedBylines']
        if bylines and len(bylines) > 0:
            host = bylines[0].get('name', host)
    if 'post' in data and 'title' in data['post']:
        title = data['post']['title']
        if "|" in title:
            parts = title.split("|")
            if len(parts) > 1:
                guest = parts[-1].strip()
    return host, guest

def download_transcript_json(http_url: str) -> list[dict]:
    r = requests.get(http_url)
    r.raise_for_status()
    return r.json()

def build_text(transcript_data: list[dict], host_name: str, guest_name: str) -> str:
    speaker_map = {}
    found_intro = False
    for segment in transcript_data[:20]:
        text = segment.get('text', '').lower()
        speaker = segment.get('speaker')
        if "my guest is" in text or "welcome to the podcast" in text or "welcome back" in text:
            speaker_map[speaker] = host_name
            other_id = "SPEAKER_0" if speaker == "SPEAKER_1" else "SPEAKER_1"
            speaker_map[other_id] = guest_name
            found_intro = True
            break
    if not found_intro:
        speaker_map["SPEAKER_1"] = host_name
        speaker_map["SPEAKER_0"] = guest_name
    full_text = ""
    current_speaker = None
    for segment in transcript_data:
        speaker_id = segment.get('speaker', 'Unknown')
        speaker_name = speaker_map.get(speaker_id, speaker_id)
        text = segment.get('text', '').strip()
        if not text:
            continue
        if speaker_name != current_speaker:
            full_text += f"\n\n[{speaker_name}]: "
            current_speaker = speaker_name
        full_text += text + " "
    return full_text.strip()

def scrape_to_files(url: str, out_dir: str | None = None) -> tuple[str, str]:
    slug = slug_from_url(url)
    if not out_dir:
        out_dir = os.path.join(EPISODES_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)

    html = fetch_page(url)
    soup = BeautifulSoup(html, 'html.parser')
    data = extract_preloads(soup)
    if not data:
        raise RuntimeError("页面中未找到 window._preloads 数据")
    with open(os.path.join(out_dir, "page_content.html"), "w", encoding="utf-8") as pf:
        pf.write(html)

    raw_url = find_transcript_url(data)
    if not raw_url:
        raise RuntimeError("未找到 transcript URL")
    http_url = resolve_signed_http(raw_url, data)
    t_data = download_transcript_json(http_url)
    host_name, guest_name = detect_speakers(data)
    text = build_text(t_data, host_name, guest_name)

    transcript_path = os.path.join(out_dir, "transcript.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(text)
    return slug, transcript_path

