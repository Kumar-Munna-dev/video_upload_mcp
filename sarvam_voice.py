"""
Sarvam AI text-to-speech: real-sounding Indian voices (Hindi by default).

API key (never put it in code):
    PC:     ~/.youtube-mcp/sarvam_key.txt     (just the key, one line)
    Cloud:  environment variable SARVAM_API_KEY

Try it:   python sarvam_voice.py "नमस्ते दोस्तों!"  male   -> hello.wav
"""
import base64
import io
import json
import os
import re
import sys
import urllib.request
import wave
from pathlib import Path

URL = "https://api.sarvam.ai/text-to-speech"
MODEL = "bulbul:v4-flash"
MALE, FEMALE = "shubh_hi_stories_dramatic", "simran_hi_narration"
# A few good Hindi voices. Any other Bulbul V4 Flash voice name (e.g. ritu_hi_reels) also works.
GOOD_VOICES = {
    "male": MALE, "female": FEMALE,
    "shubh_hi_stories_dramatic": "male, story / riddle (default)",
    "shubh_hi_stories_mixed": "male, calm story",
    "mukul_hi_suspense": "male, suspense / mystery",
    "anand_hi_documentary": "male, documentary",
    "simran_hi_narration": "female, narration (default female)",
    "ritu_hi_reels": "female, lively reels",
    "ishita_hi_ads": "female, ads",
}


def api_key() -> str:
    key = os.environ.get("SARVAM_API_KEY")
    file = Path.home() / ".youtube-mcp" / "sarvam_key.txt"
    if not key and file.exists():
        key = file.read_text().strip()
    if not key:
        raise RuntimeError("No Sarvam API key. Put it in ~/.youtube-mcp/sarvam_key.txt or set SARVAM_API_KEY.")
    return key


def _one_request(text: str, speaker: str, pace: float, language: str) -> bytes:
    body = json.dumps({"text": text, "language_code": language, "model": MODEL,
                       "speaker": speaker, "pace": pace, "speech_sample_rate": 24000}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json",
                                                         "api-subscription-key": api_key()})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        if "not recognized" in msg:
            raise RuntimeError(f"Unknown voice '{speaker}'. Try: {', '.join(k for k in GOOD_VOICES if '_' in k)}") from None
        raise RuntimeError(f"Sarvam error {e.code}: {msg[:300]}") from None
    return base64.b64decode("".join(data["audios"]))


def _chunks(text: str, limit: int = 2000) -> list[str]:
    """Split long text at sentence ends (the API takes up to 2500 characters)."""
    parts, cur = [], ""
    for sentence in re.split(r"(?<=[.?!।])\s+", text.strip()):
        if cur and len(cur) + len(sentence) > limit:
            parts.append(cur)
            cur = ""
        cur = f"{cur} {sentence}".strip()
    return parts + [cur] if cur else parts


def speak(text: str, speaker: str = MALE, pace: float = 1.0, language: str = "hi-IN") -> bytes:
    """Text -> WAV bytes. speaker: "male", "female" or a full voice name. Long text is sent in pieces and joined."""
    speaker = {"male": MALE, "female": FEMALE}.get(speaker, speaker)
    pieces = [_one_request(c, speaker, pace, language) for c in _chunks(text)]
    if len(pieces) == 1:
        return pieces[0]
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        for i, p in enumerate(pieces):
            with wave.open(io.BytesIO(p)) as r:
                if i == 0:
                    w.setparams(r.getparams())
                w.writeframes(r.readframes(r.getnframes()))
    return out.getvalue()


def seconds(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes)) as r:
        return round(r.getnframes() / r.getframerate(), 2)


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "नमस्ते दोस्तों! ये सर्वम की असली जैसी आवाज़ है।"
    wav = speak(text, sys.argv[2] if len(sys.argv) > 2 else MALE)
    Path("hello.wav").write_bytes(wav)
    print(f"hello.wav ({seconds(wav)} s)")
