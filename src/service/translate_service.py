import os
from src.infra.deepseek_client import translate_text_strict

def parse_transcript_segments(transcript_text: str) -> list[dict]:
    segments = []
    current = {"speaker": None, "english": "", "chinese": ""}
    mode = "none"
    for raw_line in transcript_text.splitlines():
        line = raw_line.strip()
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

def translate_file(input_path: str, output_path: str) -> None:
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()
    segments = parse_transcript_segments(content)
    with open(output_path, "w", encoding="utf-8") as f:
        for seg in segments:
            speaker = seg["speaker"]
            english = seg["english"]
            translation = translate_text_strict(english) if english else ""
            f.write(f"[{speaker}]: {english}\n")
            f.write(f"(中文): {translation}\n\n")

