import requests
from bs4 import BeautifulSoup
import json
import re
import sys
import os
import argparse

def slug_from_url(url):
    try:
        path = url.split("?")[0]
        parts = path.strip("/").split("/")
        if "p" in parts:
            idx = parts.index("p")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return parts[-1]
    except Exception:
        return "episode"

def scrape_transcript(url, output_file="transcript.txt", save_page_html=False):
    print(f"Fetching page: {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching page: {e}")
        return False

    soup = BeautifulSoup(response.text, 'html.parser')
    if save_page_html:
        try:
            with open(os.path.join(os.path.dirname(output_file), "page_content.html"), "w", encoding="utf-8") as pf:
                pf.write(response.text)
        except Exception as e:
            print(f"Error saving page HTML: {e}")
    
    # Find the window._preloads data
    scripts = soup.find_all('script')
    data = None
    
    for script in scripts:
        if script.string and "window._preloads" in script.string:
            match = re.search(r'window\._preloads\s*=\s*JSON\.parse\("(.+?)"\)', script.string)
            if match:
                json_str = match.group(1)
                try:
                    # Unescape twice because it's JSON inside a string inside JS
                    json_str_unescaped = json_str.encode('utf-8').decode('unicode_escape')
                    data = json.loads(json_str_unescaped)
                    break
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON from script: {e}")
                    continue

    if not data:
        print("Could not find window._preloads data in the page.")
        return False
        
    # Attempt to identify speakers
    host_name = "Host"
    guest_name = "Guest"
    
    # Get Host from publishedBylines
    if 'post' in data and 'publishedBylines' in data['post']:
        bylines = data['post']['publishedBylines']
        if bylines and len(bylines) > 0:
            host_name = bylines[0].get('name', 'Host')
            
    # Get Guest from title
    if 'post' in data and 'title' in data['post']:
        title = data['post']['title']
        # Common format: "Title | Guest Name"
        if "|" in title:
            parts = title.split("|")
            if len(parts) > 1:
                guest_name = parts[-1].strip()
    
    print(f"Identified potential speakers - Host: {host_name}, Guest: {guest_name}")

    # Navigate to the transcript URL
    # Path: post -> podcastUpload -> transcription -> transcript_url
    transcript_url = None
    
    # Try to find transcript URL in the current post
    if 'post' in data and 'podcastUpload' in data['post']:
        upload = data['post']['podcastUpload']
        if upload and 'transcription' in upload:
             transcript_url = upload['transcription'].get('transcript_url')
    
    # If not found directly, look for signed URLs in the data that match the pattern
    if not transcript_url:
        print("Transcript URL not found in standard location. Searching recursively...")
        # Helper to find URLs
        found_urls = []
        def find_urls(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, str) and "transcription.json" in v and "http" in v:
                        found_urls.append(v)
                    find_urls(v)
            elif isinstance(obj, list):
                for item in obj:
                    find_urls(item)
        
        find_urls(data)
        
        # Filter for URLs that might belong to the current post (using post ID if possible)
        # For now, just take the first one if available, or try to match post ID
        post_id = str(data.get('post', {}).get('id', ''))
        if found_urls:
            if post_id:
                for u in found_urls:
                    if post_id in u:
                        transcript_url = u
                        break
            if not transcript_url:
                transcript_url = found_urls[0] # Fallback to first found

    if not transcript_url:
        print("Could not find any transcript URL in the page data.")
        return False
        
    print(f"Found transcript URL: {transcript_url}")
    
    # The URL might be an s3:// URL which we can't fetch directly without signing
    # But usually the JSON contains the http version too.
    # If we only found the s3 URL, we are in trouble unless we found the signed http one.
    
    if transcript_url.startswith("s3://"):
        print("Found S3 URL, searching for HTTP equivalent...")
        # Search again for HTTP version
        http_url = None
        
        # We know the structure s3://substack-video/video_upload/...
        # We want https://substackcdn.com/video_upload/...
        # But we need the signature params.
        # Let's search specifically for the signed URL corresponding to this S3 path's file name
        
        # Extract filename/path part
        path_part = transcript_url.replace("s3://substack-video/", "")
        
        def find_signed_url(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, str) and path_part in v and "http" in v:
                        return v
                    res = find_signed_url(v)
                    if res: return res
            elif isinstance(obj, list):
                for item in obj:
                    res = find_signed_url(item)
                    if res: return res
            return None

        http_url = find_signed_url(data)
        
        if http_url:
            print(f"Found signed HTTP URL: {http_url}")
            transcript_url = http_url
        else:
            print("Could not find signed HTTP URL for the transcript.")
            # Last ditch effort: check if there is an 'unaligned_transcription.json' or similar that IS signed
            return False

    # Download transcript
    print("Downloading transcript...")
    try:
        t_response = requests.get(transcript_url)
        t_response.raise_for_status()
        transcript_data = t_response.json()
    except Exception as e:
        print(f"Error downloading/parsing transcript JSON: {e}")
        return False

    # Process transcript
    # Structure: list of objects with 'text', 'speaker', 'start', 'end'
    
    # Heuristic to map SPEAKER_0/SPEAKER_1 to Host/Guest
    # Look for "my guest is" pattern in the first 20 segments
    speaker_map = {}
    
    # Default assumption: usually SPEAKER_1 is Host if they introduce the guest
    # But let's verify
    
    found_intro = False
    for i, segment in enumerate(transcript_data[:20]):
        text = segment.get('text', '').lower()
        speaker = segment.get('speaker')
        
        if "my guest is" in text or "welcome to the podcast" in text or "welcome back" in text:
             # This speaker is likely the host
             speaker_map[speaker] = host_name
             # The other speaker ID (if simple 0/1 case) is likely the guest
             other_id = "SPEAKER_0" if speaker == "SPEAKER_1" else "SPEAKER_1"
             speaker_map[other_id] = guest_name
             found_intro = True
             print(f"Detected host ({host_name}) as {speaker} based on intro text.")
             break
    
    if not found_intro:
        print("Could not automatically detect speaker roles. Using default mapping (SPEAKER_1 = Host).")
        speaker_map["SPEAKER_1"] = host_name
        speaker_map["SPEAKER_0"] = guest_name

    full_text = ""
    current_speaker = None
    
    for segment in transcript_data:
        speaker_id = segment.get('speaker', 'Unknown')
        speaker_name = speaker_map.get(speaker_id, speaker_id) # Use mapped name or original ID
        
        text = segment.get('text', '').strip()
        
        if not text:
            continue
            
        if speaker_name != current_speaker:
            full_text += f"\n\n[{speaker_name}]: "
            current_speaker = speaker_name
        
        full_text += text + " "

    # Save to file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(full_text.strip())
    
    print(f"Transcript saved to {output_file}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", dest="url", default="https://www.lennysnewsletter.com/p/the-coming-ai-security-crisis")
    parser.add_argument("--out-dir", dest="out_dir", default=None)
    args = parser.parse_args()

    target_url = args.url
    out_dir = args.out_dir

    if not out_dir:
        slug = slug_from_url(target_url)
        out_dir = os.path.join("episodes", slug)

    output_path = os.path.join(out_dir, "transcript.txt")
    scrape_transcript(target_url, output_file=output_path, save_page_html=True)
