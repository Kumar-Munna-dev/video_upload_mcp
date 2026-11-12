"""
YouTube + voice server. Runs on Render; your PC makes the videos and calls it.

  python youtube_mcp.py auth main   one-time login on your PC -> ~/.youtube-mcp/tokens/main.json
  python youtube_mcp.py http        the web server (Render runs this)

Web endpoints (each needs the API key: header "Authorization: Bearer <API_KEY>" or ?key=<API_KEY>):
  POST /voice    JSON {"text", "speaker": "male", "pace": 1.0}            -> WAV audio (Sarvam AI)
  POST /upload?title=..&description=..&tags=a,b&privacy=private   body = MP4 bytes -> JSON {ok, url}
  /mcp           MCP tools for Claude (add as a connector, so ANY chat can use it):
                 make_voice -> voice download link · upload_link -> one-time link to POST the MP4 to
                 upload_video (from a public link) · channel_info
Links made by make_voice / upload_link need no key, are random, work for 1 hour and only once (upload).

Render environment variables: API_KEY, YOUTUBE_TOKEN_MAIN (whole main.json), SARVAM_API_KEY
Nothing is kept on the server: every video is deleted right after its upload.
"""
import asyncio
import json
import os
import secrets
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from mcp.server.mcpserver import MCPServer

import sarvam_voice

BASE = Path.home() / ".youtube-mcp"
SCOPES = ["https://www.googleapis.com/auth/youtube"]
PUBLIC_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:8080").rstrip("/")   # Render sets this
LINK_LIFE = 3600                     # seconds a voice / upload link stays valid
VOICES: dict[str, dict] = {}         # token -> {"wav", "expires"}   (in memory, max 20)
UPLOADS: dict[str, dict] = {}        # token -> {"meta", "expires"}  (one-time upload links)

mcp = MCPServer("youtube-uploader")


def _new_token(store: dict, **item) -> str:
    """Forget expired links, add a new one, return its random token."""
    now = time.time()
    for k in [k for k, v in store.items() if v["expires"] < now]:
        store.pop(k)
    while len(store) >= 20:
        store.pop(next(iter(store)))
    token = secrets.token_urlsafe(24)
    store[token] = {**item, "expires": now + LINK_LIFE}
    return token


def _take(store: dict, token: str, once: bool = False):
    item = store.pop(token, None) if once else store.get(token)
    return item if item and item["expires"] >= time.time() else None


# ---------------------------------------------------------------- YouTube

def login(account: str) -> None:
    """Open the browser, pick a Google account, save its token (do this on your PC)."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(BASE / "client_secret.json"), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent select_account")
    out = BASE / "tokens" / f"{account}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(creds.to_json())
    print(f"Token saved: {out}. Put its whole text in Render as YOUTUBE_TOKEN_{account.upper()}.")


def youtube(account: str = "main"):
    """YouTube API client. Token from env YOUTUBE_TOKEN_<ACCOUNT> (Render) or ~/.youtube-mcp/tokens/<account>.json."""
    token = os.environ.get(f"YOUTUBE_TOKEN_{account.upper()}")
    file = BASE / "tokens" / f"{account}.json"
    if not token and file.exists():
        token = file.read_text()
    if not token:
        raise RuntimeError(f"No YouTube token for '{account}'. Run: python youtube_mcp.py auth {account}")
    try:
        creds = Credentials.from_authorized_user_info(json.loads(token), SCOPES)
    except ValueError:
        raise RuntimeError("The YouTube token must be the WHOLE main.json text, from { to }.") from None
    if not creds.valid:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_file(path: str, title: str, description: str = "", tags: list[str] | None = None,
                privacy: str = "private", account: str = "main") -> dict:
    """Upload a video file to YouTube."""
    try:
        body = {"snippet": {"title": title[:100], "description": description, "tags": tags or [], "categoryId": "22"},
                "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
        media = MediaFileUpload(path, chunksize=4 * 1024 * 1024, resumable=True)
        request = youtube(account).videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()
        vid = response["id"]
        return {"ok": True, "video_id": vid, "url": f"https://youtu.be/{vid}",
                "privacy": response["status"]["privacyStatus"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------- MCP tools (for Claude)

@mcp.tool()
def upload_video(video_url: str, title: str, description: str = "", tags: list[str] | None = None,
                 privacy: str = "private") -> dict:
    """Upload a video to YouTube from a public download link (https://...mp4).
    title: max 100 characters (add #shorts for a Short). privacy: public | unlisted | private"""
    fd, tmp = tempfile.mkstemp(suffix=".mp4")
    try:
        with open(fd, "wb") as f, urllib.request.urlopen(video_url) as r:
            while chunk := r.read(1024 * 1024):
                f.write(chunk)
        return upload_file(tmp, title, description, tags, privacy)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        Path(tmp).unlink(missing_ok=True)


@mcp.tool()
def make_voice(text: str, speaker: str = "male", pace: float = 1.0) -> dict:
    """Make a real-sounding Hindi voice-over (Sarvam AI, Bulbul V4 Flash). Returns a WAV download link (1 hour).
    speaker: "male", "female", or a voice name like mukul_hi_suspense, ritu_hi_reels. pace: 0.5-2.0
    Download it with: curl -o voice.wav "<download_url>" """
    try:
        wav = sarvam_voice.speak(text, speaker, pace)
        token = _new_token(VOICES, wav=wav)
        return {"ok": True, "download_url": f"{PUBLIC_URL}/v/{token}.wav", "seconds": sarvam_voice.seconds(wav)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def upload_link(title: str, description: str = "", tags: list[str] | None = None, privacy: str = "private") -> dict:
    """Get a one-time link to upload a finished MP4 to YouTube (Pixel Katha 3D). Works for 1 hour.
    Then send the file:  curl -X POST --data-binary @video.mp4 -H "Content-Type: video/mp4" "<upload_url>"
    The server uploads it to YouTube, deletes it, and answers with the YouTube link.
    title: max 100 characters (add #shorts for a Short). privacy: public | unlisted | private"""
    token = _new_token(UPLOADS, meta={"title": title, "description": description, "tags": tags or [], "privacy": privacy})
    url = f"{PUBLIC_URL}/u/{token}"
    return {"ok": True, "upload_url": url,
            "how": f'curl -X POST --data-binary @video.mp4 -H "Content-Type: video/mp4" "{url}"'}


@mcp.tool()
def channel_info() -> dict:
    """Channel name, subscribers and video count."""
    try:
        c = youtube().channels().list(part="snippet,statistics", mine=True).execute()["items"][0]
        return {"ok": True, "title": c["snippet"]["title"], "subscribers": c["statistics"].get("subscriberCount"),
                "videos": c["statistics"].get("videoCount")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------- web server

def run_http() -> None:
    import uvicorn
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route

    api_key = os.environ.get("API_KEY")
    if not api_key:
        sys.exit("Set the API_KEY environment variable first (any long secret text).")

    async def voice(request):
        """JSON {text, speaker, pace} -> WAV."""
        data = await request.json()
        try:
            wav = await asyncio.to_thread(sarvam_voice.speak, data["text"], data.get("speaker", "male"),
                                          float(data.get("pace", 1.0)))
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, 400)
        return Response(wav, media_type="audio/wav")

    async def receive_and_upload(request, meta: dict):
        """Save the MP4 body to a temp file (as it arrives: low memory), upload it, delete it."""
        fd, tmp = tempfile.mkstemp(suffix=".mp4")
        try:
            with open(fd, "wb") as f:
                async for chunk in request.stream():
                    f.write(chunk)
            result = await asyncio.to_thread(upload_file, tmp, meta.get("title", ""), meta.get("description", ""),
                                             meta.get("tags", []), meta.get("privacy", "private"),
                                             meta.get("account", "main"))
        finally:
            Path(tmp).unlink(missing_ok=True)
        return JSONResponse(result, 200 if result["ok"] else 500)

    async def upload(request):
        """Body = MP4 bytes, details in the query string."""
        q = request.query_params
        tags = [t.strip() for t in q.get("tags", "").split(",") if t.strip()]
        return await receive_and_upload(request, {"title": q.get("title", ""), "description": q.get("description", ""),
                                                  "tags": tags, "privacy": q.get("privacy", "private"),
                                                  "account": q.get("account", "main")})

    async def upload_by_link(request):
        """One-time link from the upload_link tool: no key needed."""
        item = _take(UPLOADS, request.path_params["token"], once=True)
        if not item:
            return JSONResponse({"ok": False, "error": "link expired or already used: call upload_link again"}, 404)
        return await receive_and_upload(request, item["meta"])

    async def voice_file(request):
        """Voice made by the make_voice tool (link works for 1 hour)."""
        item = _take(VOICES, request.path_params["token"])
        if not item:
            return JSONResponse({"ok": False, "error": "voice link expired: call make_voice again"}, 404)
        return Response(item["wav"], media_type="audio/wav")

    app = mcp.streamable_http_app(stateless_http=True, host="0.0.0.0")
    app.router.routes += [Route("/voice", voice, methods=["POST"]), Route("/upload", upload, methods=["POST"]),
                          Route("/u/{token}", upload_by_link, methods=["POST"]),
                          Route("/v/{token}.wav", voice_file, methods=["GET"])]

    async def check_key(scope, receive, send):
        """Allow only requests with  ?key=API_KEY  or  Authorization: Bearer API_KEY.
        The random one-time links (/u/..., /v/...) are their own key."""
        if scope["type"] == "http" and not scope["path"].startswith(("/u/", "/v/")):
            headers = dict(scope["headers"])
            query = scope.get("query_string", b"").decode()
            if headers.get(b"authorization", b"").decode() != f"Bearer {api_key}" \
                    and f"key={api_key}" not in query.split("&"):
                return await JSONResponse({"error": "wrong or missing API key"}, 401)(scope, receive, send)
        await app(scope, receive, send)

    uvicorn.run(check_key, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "auth":
        login(sys.argv[2] if len(sys.argv) > 2 else "main")
    elif cmd == "http":
        run_http()
    else:
        mcp.run()   # MCP over stdio (local Claude)
