"""
Simple YouTube Upload MCP Server

1) One-time login on your PC (opens browser):   python youtube_mcp.py auth main
2) Run locally for Claude (stdio):               python youtube_mcp.py
3) Run as a web server (Google Cloud Run):       python youtube_mcp.py http

On the cloud there is no browser and no saved token file, so the token is
given through an environment variable instead:
    YOUTUBE_TOKEN_MAIN   = contents of ~/.youtube-mcp/tokens/main.json
    API_KEY              = any secret password; clients must send it
"""
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

BASE = Path.home() / ".youtube-mcp"
CLIENT_SECRET = BASE / "client_secret.json"   # OAuth "Desktop app" JSON from Google Cloud
TOKENS = BASE / "tokens"                       # one token file per account
SCOPES = ["https://www.googleapis.com/auth/youtube"]

mcp = MCPServer("youtube-uploader")


# ---------------------------------------------------------------- login + tokens

def login(account: str) -> None:
    """Open the browser, let the user pick a Google account, save its token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent select_account")
    TOKENS.mkdir(parents=True, exist_ok=True)
    (TOKENS / f"{account}.json").write_text(creds.to_json())
    print(f"Logged in as '{account}'. Token saved in {TOKENS / f'{account}.json'}", file=sys.stderr)


def load_token(account: str) -> str | None:
    """Token JSON text: first from env var YOUTUBE_TOKEN_<ACCOUNT> (cloud), else from file (PC)."""
    env_value = os.environ.get(f"YOUTUBE_TOKEN_{account.upper()}")
    if env_value:
        return env_value
    file = TOKENS / f"{account}.json"
    return file.read_text() if file.exists() else None


def youtube(account: str):
    """Return a YouTube API client for an account (refreshes the token if expired)."""
    token = load_token(account)
    if not token:
        raise RuntimeError(f"Account '{account}' not logged in. Run: python youtube_mcp.py auth {account}")
    creds = Credentials.from_authorized_user_info(json.loads(token), SCOPES)
    if not creds.valid:
        creds.refresh(Request())   # new access token is kept in memory only
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def get_video_file(video: str) -> str:
    """If `video` is a web link, download it to a temp file. Return a local path."""
    if video.startswith(("http://", "https://")):
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        with urllib.request.urlopen(video) as r, tmp:
            while chunk := r.read(1024 * 1024):
                tmp.write(chunk)
        return tmp.name
    if not Path(video).is_file():
        raise FileNotFoundError(f"File not found: {video}")
    return video


# ---------------------------------------------------------------- MCP tools

@mcp.tool()
def upload_video(
    video: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    privacy: str = "private",
    account: str = "main",
) -> dict:
    """Upload a video to YouTube.

    video: a public download link (https://...mp4) OR a local file path.
           On the cloud server only links work.
    title: max 100 characters (add #shorts for a Short)
    privacy: public | unlisted | private
    account: account name (default "main")
    """
    path = None
    try:
        path = get_video_file(video)
        body = {
            "snippet": {"title": title[:100], "description": description,
                        "tags": tags or [], "categoryId": "22"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(path, chunksize=8 * 1024 * 1024, resumable=True)
        request = youtube(account).videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:          # upload in chunks
            _, response = request.next_chunk()

        vid = response["id"]
        return {"ok": True, "video_id": vid, "url": f"https://youtu.be/{vid}",
                "privacy": response["status"]["privacyStatus"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        if path and path != video:       # delete the downloaded temp file
            Path(path).unlink(missing_ok=True)


@mcp.tool()
def list_accounts() -> list[str]:
    """List the YouTube accounts this server can use."""
    names = {k[len("YOUTUBE_TOKEN_"):].lower() for k in os.environ if k.startswith("YOUTUBE_TOKEN_")}
    if TOKENS.exists():
        names |= {p.stem for p in TOKENS.glob("*.json")}
    return sorted(names)


@mcp.tool()
def channel_info(account: str = "main") -> dict:
    """Show channel name, subscribers and video count for an account."""
    try:
        items = youtube(account).channels().list(part="snippet,statistics", mine=True).execute()["items"]
        c = items[0]
        return {"ok": True, "title": c["snippet"]["title"],
                "subscribers": c["statistics"].get("subscriberCount"),
                "videos": c["statistics"].get("videoCount")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------- web server (cloud)

def run_http() -> None:
    """Serve MCP over HTTP at /mcp. Every request must carry the API_KEY."""
    import uvicorn
    from starlette.responses import JSONResponse

    api_key = os.environ.get("API_KEY")
    if not api_key:
        sys.exit("Set the API_KEY environment variable first (any long secret text).")

    app = mcp.streamable_http_app(stateless_http=True, host="0.0.0.0")

    async def check_key(scope, receive, send):
        """Allow the request only if it has  ?key=API_KEY  or header  Authorization: Bearer API_KEY."""
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            query = scope.get("query_string", b"").decode()
            ok = headers.get(b"authorization", b"").decode() == f"Bearer {api_key}" \
                or f"key={api_key}" in query.split("&")
            if not ok:
                return await JSONResponse({"error": "wrong or missing API key"}, 401)(scope, receive, send)
        await app(scope, receive, send)

    port = int(os.environ.get("PORT", 8080))   # Cloud Run gives PORT
    uvicorn.run(check_key, host="0.0.0.0", port=port)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "auth":
        login(sys.argv[2] if len(sys.argv) > 2 else "main")
    elif command == "http":
        run_http()
    else:
        mcp.run()  # stdio MCP server (local Claude)
