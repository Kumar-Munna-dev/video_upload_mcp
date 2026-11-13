"""
Your PC talks to the Render server: make a voice, upload a video. Standard library only.

  python render_client.py voice "नमस्ते दोस्तों!" out.wav [male|female|<voice name>]
  python render_client.py upload video.mp4 info.json        info.json = {"title", "description", "tags", "privacy", "category",
                                                                       "account": "main"}   (or "accounts": ["pixelkatha3d", "riddlespixo"],
                                                                       or "account": "all" = every connected channel)
  python render_client.py channels                           every channel the server can upload to

Server: env YT_SERVER (default below). API key: env API_KEY, or the file apikey.txt next to this script,
or ~/.youtube-mcp/api_key.txt. No YouTube token or Sarvam key is needed on the PC.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SERVER = os.environ.get("YT_SERVER", "https://youtube-mcp-5wk1.onrender.com").rstrip("/")


def api_key() -> str:
    key = os.environ.get("API_KEY")
    for f in (Path(__file__).with_name("apikey.txt"), Path.home() / ".youtube-mcp" / "api_key.txt"):
        if not key and f.exists():
            key = f.read_text().strip()
    if not key:
        raise RuntimeError("No API key: put it in apikey.txt next to render_client.py")
    return key


def _post(path: str, data, content_type: str, length: int | None = None) -> bytes:
    headers = {"Authorization": f"Bearer {api_key()}", "Content-Type": content_type}
    if length is not None:
        headers["Content-Length"] = str(length)
    req = urllib.request.Request(SERVER + path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=900) as r:   # long: the free server may need ~1 min to wake up
            return r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Server error {e.code}: {e.read().decode(errors='replace')[:300]}") from None


def voice(text: str, speaker: str = "male", pace: float = 1.0) -> bytes:
    """Text -> WAV bytes (Sarvam AI on the server)."""
    body = json.dumps({"text": text, "speaker": speaker, "pace": pace}).encode()
    return _post("/voice", body, "application/json")


def channels() -> dict:
    """{account: {ok, title, subscribers, videos}} for every channel the server has a token for."""
    req = urllib.request.Request(SERVER + "/channels", headers={"Authorization": f"Bearer {api_key()}"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Server error {e.code}: {e.read().decode(errors='replace')[:300]}") from None


def upload(video: str, title: str, description: str = "", tags=(), privacy: str = "private",
           category: str = "22", account: str = "main") -> dict:
    """Send an MP4 to the server, which uploads it to one YouTube channel and deletes it. Returns {ok, url, ...}."""
    query = urllib.parse.urlencode({"title": title, "description": description,
                                    "tags": ",".join(tags), "privacy": privacy,
                                    "category": category, "account": account})
    size = os.path.getsize(video)
    with open(video, "rb") as f:
        return json.loads(_post(f"/upload?{query}", f, "video/mp4", size))


def accounts_of(info: dict) -> list[str]:
    """Channels named in an info.json: "accounts": [..], or "account": "x" / "all". Default ["main"]."""
    names = info.get("accounts") or [info.get("account") or "main"]
    if isinstance(names, str):
        names = [names]
    if "all" in names:   # every channel once (main and pixelkatha3d may be the same channel)
        seen, names = set(), []
        for account, c in channels().items():
            if c.get("ok") and c["title"] not in seen:
                seen.add(c["title"])
                names.append(account)
    return names


def upload_info(video: str, info: dict) -> dict:
    """Upload one MP4 to every channel in info.json. One channel -> its result; several -> {ok, results}."""
    results = {}
    for account in accounts_of(info):
        try:
            results[account] = upload(video, info["title"], info.get("description", ""), info.get("tags", []),
                                      info.get("privacy", "private"), str(info.get("category", "22")), account)
        except Exception as e:
            results[account] = {"ok": False, "error": str(e)}
    if len(results) == 1:
        return {**next(iter(results.values())), "account": next(iter(results))}
    return {"ok": all(r.get("ok") for r in results.values()), "results": results}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "voice":
        Path(a[2]).write_bytes(voice(a[1], a[3] if len(a) > 3 else "male"))
        print(f"saved {a[2]}")
    elif len(a) == 3 and a[0] == "upload":
        info = json.loads(Path(a[2]).read_text(encoding="utf-8"))
        print(json.dumps(upload_info(a[1], info), ensure_ascii=False))
    elif a == ["channels"]:
        print(json.dumps(channels(), ensure_ascii=False, indent=2))
    else:
        print(__doc__)
