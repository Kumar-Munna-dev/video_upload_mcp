"""
YouTube + voice server. Runs on Render; your PC makes the videos and calls it.

  python youtube_mcp.py auth main   one-time login on your PC -> ~/.youtube-mcp/tokens/main.json
  python youtube_mcp.py http        the web server (Render runs this)

Web endpoints (each needs the API key: header "Authorization: Bearer <API_KEY>" or ?key=<API_KEY>):
  POST /voice    JSON {"text", "speaker": "male", "pace": 1.0}            -> WAV audio (Sarvam AI)
  POST /upload?title=..&description=..&tags=a,b&privacy=private   body = MP4 bytes -> JSON {ok, url}
  /mcp           MCP tools for Claude: upload_video (from a link), channel_info

Render environment variables: API_KEY, YOUTUBE_TOKEN_MAIN (whole main.json), SARVAM_API_KEY
Nothing is kept on the server: every video is deleted right after its upload.
"""
import asyncio
import json
import os
import sys
import tempfile
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

mcp = MCPServer("youtube-uploader")


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

    async def upload(request):
        """Body = MP4 bytes, details in the query string. The file is deleted right after."""
        q = request.query_params
        fd, tmp = tempfile.mkstemp(suffix=".mp4")
        try:
            with open(fd, "wb") as f:
                async for chunk in request.stream():      # write to disk as it arrives: low memory
                    f.write(chunk)
            tags = [t.strip() for t in q.get("tags", "").split(",") if t.strip()]
            result = await asyncio.to_thread(upload_file, tmp, q.get("title", ""), q.get("description", ""),
                                             tags, q.get("privacy", "private"), q.get("account", "main"))
        finally:
            Path(tmp).unlink(missing_ok=True)
        return JSONResponse(result, 200 if result["ok"] else 500)

    app = mcp.streamable_http_app(stateless_http=True, host="0.0.0.0")
    app.router.routes += [Route("/voice", voice, methods=["POST"]), Route("/upload", upload, methods=["POST"])]

    async def check_key(scope, receive, send):
        """Allow only requests with  ?key=API_KEY  or  Authorization: Bearer API_KEY."""
        if scope["type"] == "http":
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
