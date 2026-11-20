"""
YouTube + Instagram + Facebook + voice server. Runs on Render; your PC makes the videos and calls it.

Instagram / Facebook: ONE MCP tool PER ACCOUNT, made from the Render environment variables
  INSTAGRAM_ACCOUNT_<NAME> = {"user_id": "...", "access_token": "..."}   -> tool  instagram_<name>
  FACEBOOK_PAGE_<NAME>     = {"page_id": "...", "access_token": "..."}   -> tool  facebook_<name>
New account = add one variable on Render. Details in social.py.
  POST /social/<instagram|facebook>/<name>?title=..&description=..&hashtags=a,b&video_type=auto&cover=<id>   body = MP4
  POST /cover   body = JPG -> {cover_id}   (the video's cover / thumbnail; add &cover=<cover_id> to /social or /upload)

  python youtube_mcp.py auth main   one-time login on your PC -> ~/.youtube-mcp/tokens/main.json
                                   (one per channel: auth pixelkatha3d / auth riddlespixo / auth scielifeindia)
  python youtube_mcp.py http        the web server (Render runs this)

Web endpoints (each needs the API key: header "Authorization: Bearer <API_KEY>" or ?key=<API_KEY>):
  POST /voice    JSON {"text", "speaker": "male", "pace": 1.0}            -> WAV audio (Sarvam AI)
  POST /upload?title=..&description=..&tags=a,b&privacy=private&account=main   body = MP4 bytes -> JSON {ok, url}
  GET  /channels  every channel the server has a token for -> JSON {account: {title, subscribers, videos}}
  /mcp           MCP tools for Claude (add as a connector, so ANY chat can use it):
                 make_voice -> voice download link · upload_link -> one-time link to POST the MP4 to
                 upload_video (from a public link) · channel_info
Links made by make_voice / upload_link need no key, are random, work for 1 hour and only once (upload).

Render environment variables: API_KEY, SARVAM_API_KEY, and one YOUTUBE_TOKEN_<ACCOUNT> per channel
(YOUTUBE_TOKEN_MAIN = whole main.json, YOUTUBE_TOKEN_PIXELKATHA3D = whole pixelkatha3d.json, ...)
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
import social

BASE = Path.home() / ".youtube-mcp"
SCOPES = ["https://www.googleapis.com/auth/youtube"]
PUBLIC_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:8080").rstrip("/")   # Render sets this
LINK_LIFE = 3600                     # seconds a voice / upload link stays valid
VOICES: dict[str, dict] = {}         # token -> {"wav", "expires"}   (in memory, max 20)
UPLOADS: dict[str, dict] = {}        # token -> {"meta", "expires"}  (one-time upload links)
COVERS: dict[str, dict] = {}         # token -> {"jpg", "expires"}   (cover images; Instagram downloads them from /c/)

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
        raise RuntimeError(f"The YouTube token must be the WHOLE {account}.json text, from {{ to }}.") from None
    if not creds.valid:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def accounts() -> list[str]:
    """Every account with a token: env YOUTUBE_TOKEN_<NAME> or ~/.youtube-mcp/tokens/<name>.json."""
    names = {k[len("YOUTUBE_TOKEN_"):].lower() for k in os.environ if k.startswith("YOUTUBE_TOKEN_")}
    if (BASE / "tokens").exists():
        names |= {f.stem.lower() for f in (BASE / "tokens").glob("*.json")}
    return sorted(names)


def channel(account: str = "main") -> dict:
    """Name, subscribers and video count of one account's channel."""
    try:
        c = youtube(account).channels().list(part="snippet,statistics", mine=True).execute()["items"][0]
        return {"ok": True, "account": account, "title": c["snippet"]["title"],
                "subscribers": c["statistics"].get("subscriberCount"), "videos": c["statistics"].get("videoCount")}
    except Exception as e:
        return {"ok": False, "account": account, "error": str(e)}


def upload_file(path: str, title: str, description: str = "", tags: list[str] | None = None,
                privacy: str = "private", account: str = "main", category: str = "22",
                cover: bytes | None = None) -> dict:
    """Upload a video file to YouTube. category: 22 People & Blogs, 27 Education, 24 Entertainment, 23 Comedy."""
    try:
        body = {"snippet": {"title": title[:100], "description": description, "tags": tags or [], "categoryId": str(category or "22")},
                "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
        media = MediaFileUpload(path, chunksize=4 * 1024 * 1024, resumable=True)
        request = youtube(account).videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()
        vid = response["id"]
        cover_note = "none sent"
        if cover:   # custom thumbnail (needs a phone-verified channel; Shorts may ignore it)
            try:
                from googleapiclient.http import MediaInMemoryUpload
                youtube(account).thumbnails().set(videoId=vid, media_body=MediaInMemoryUpload(cover, "image/jpeg")).execute()
                cover_note = "set"
            except Exception as e:
                cover_note = f"not set: {e}"
        return {"ok": True, "video_id": vid, "url": f"https://youtu.be/{vid}",
                "privacy": response["status"]["privacyStatus"], "cover": cover_note}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------- MCP tools (for Claude)

@mcp.tool()
def upload_video(video_url: str, title: str, description: str = "", tags: list[str] | None = None,
                 privacy: str = "private", account: str = "main") -> dict:
    """Upload a video to YouTube from a public download link (https://...mp4).
    title: max 100 characters (add #shorts for a Short). privacy: public | unlisted | private
    account: which channel (see channel_info), default "main" """
    fd, tmp = tempfile.mkstemp(suffix=".mp4")
    try:
        with open(fd, "wb") as f, urllib.request.urlopen(video_url) as r:
            while chunk := r.read(1024 * 1024):
                f.write(chunk)
        return upload_file(tmp, title, description, tags, privacy, account)
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
def upload_link(title: str, description: str = "", tags: list[str] | None = None, privacy: str = "private",
                category: str = "22", account: str = "main") -> dict:
    """Get a one-time link to upload a finished MP4 to YouTube. Works for 1 hour.
    account: which channel ("main" = Pixel Katha 3D; channel_info lists them all). One link = one channel.
    Optional cover (thumbnail) first:  curl -X POST --data-binary @cover.jpg -H "Content-Type: image/jpeg" "<upload_url>/cover"
    Then send the file:  curl -X POST --data-binary @video.mp4 -H "Content-Type: video/mp4" "<upload_url>"
    The server uploads it to YouTube, deletes it, and answers with the YouTube link.
    title: max 100 characters (add #shorts for a Short). privacy: public | unlisted | private
    category: 22 People & Blogs (default), 27 Education, 24 Entertainment, 23 Comedy"""
    token = _new_token(UPLOADS, meta={"title": title, "description": description, "tags": tags or [], "privacy": privacy,
                                      "category": category, "account": account})
    url = f"{PUBLIC_URL}/u/{token}"
    return {"ok": True, "upload_url": url,
            "cover_first": f'curl -X POST --data-binary @cover.jpg -H "Content-Type: image/jpeg" "{url}/cover"',
            "how": f'curl -X POST --data-binary @video.mp4 -H "Content-Type: video/mp4" "{url}"'}


@mcp.tool()
def channel_info() -> dict:
    """Every connected channel: account name -> channel name, subscribers, video count."""
    return {"ok": True, "channels": [channel(a) for a in accounts()]}


# ---------------------------------------------------------------- Instagram + Facebook: one tool per account

@mcp.tool()
def social_accounts() -> dict:
    """Every connected Instagram account and Facebook Page, and whether its token works.
    Each one has its own upload tool: instagram_<name> or facebook_<name>."""
    return {"ok": True, "accounts": [social.check(p, a) for p in ("instagram", "facebook") for a in social.accounts(p)]}


def social_tool(platform: str, name: str):
    """Make the upload tool of one account (e.g. instagram_riddlespixo)."""
    def upload(title: str, description: str, hashtags: list[str], video_type: str = "auto") -> dict:
        token = _new_token(UPLOADS, meta={"platform": platform, "account": name, "title": title,
                                          "description": description, "hashtags": hashtags, "video_type": video_type})
        url = f"{PUBLIC_URL}/u/{token}"
        return {"ok": True, "upload_url": url,
                "cover_first": f'curl -X POST --data-binary @cover.jpg -H "Content-Type: image/jpeg" "{url}/cover"',
                "then_video": f'curl -X POST --data-binary @video.mp4 -H "Content-Type: video/mp4" "{url}"'}

    where = ("Instagram account @" + name + ". Every video becomes a Reel (also shown on the profile grid)."
             if platform == "instagram" else
             "Facebook Page '" + name + "'. Short video -> the Page's Reels section, long video -> a normal video post.")
    upload.__doc__ = f"""Upload a video to the {where}
    Step 1: call this tool -> you get a one-time upload_url (works 1 hour, once).
    Step 2: send the cover (thumbnail) FIRST, a JPG 9:16 like 1080x1920 (recommended, skip = first frame):
            curl -X POST --data-binary @cover.jpg -H "Content-Type: image/jpeg" "<upload_url>/cover"
    Step 3: send the MP4:  curl -X POST --data-binary @video.mp4 -H "Content-Type: video/mp4" "<upload_url>"
            The answer is the link of the post.
    title: a catchy title (first line of the caption). description: 1-3 lines about the video.
    hashtags: 5-15 tags that fit the video, e.g. ["paheli", "riddle", "reels"] (# is added for you).
    video_type: "auto" (up to 90 seconds = short, longer = long), or "short" / "long"."""
    return upload


for _platform in ("instagram", "facebook"):
    for _name in social.accounts(_platform):
        mcp.add_tool(social_tool(_platform, _name), name=f"{_platform}_{_name}")


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
            platform = meta.get("platform", "youtube")
            cover_item = _take(COVERS, meta["cover"]) if meta.get("cover") else None
            cover = cover_item["jpg"] if cover_item else None
            cover_url = f"{PUBLIC_URL}/c/{meta['cover']}.jpg" if cover_item else ""
            if platform in social.UPLOADERS:      # Instagram / Facebook
                result = await asyncio.to_thread(social.UPLOADERS[platform], meta["account"], tmp, meta.get("title", ""),
                                                 meta.get("description", ""), meta.get("hashtags", []),
                                                 meta.get("video_type", "auto"), cover, cover_url)
            else:                                 # YouTube
                result = await asyncio.to_thread(upload_file, tmp, meta.get("title", ""), meta.get("description", ""),
                                                 meta.get("tags", []), meta.get("privacy", "private"),
                                                 meta.get("account", "main"), meta.get("category", "22"), cover)
        finally:
            Path(tmp).unlink(missing_ok=True)
        return JSONResponse(result, 200 if result["ok"] else 500)

    async def upload(request):
        """Body = MP4 bytes, details in the query string."""
        q = request.query_params
        tags = [t.strip() for t in q.get("tags", "").split(",") if t.strip()]
        return await receive_and_upload(request, {"title": q.get("title", ""), "description": q.get("description", ""),
                                                  "tags": tags, "privacy": q.get("privacy", "private"),
                                                  "account": q.get("account", "main"), "category": q.get("category", "22"),
                                                  "cover": q.get("cover", "")})

    async def social_upload(request):
        """POST /social/<platform>/<name>?title=..&description=..&hashtags=a,b&video_type=auto  body = MP4."""
        platform, name, q = request.path_params["platform"], request.path_params["name"], request.query_params
        if platform not in social.UPLOADERS or name not in social.accounts(platform):
            return JSONResponse({"ok": False, "error": f"unknown {platform} account '{name}'"}, 404)
        hashtags = [h.strip() for h in q.get("hashtags", "").split(",") if h.strip()]
        return await receive_and_upload(request, {"platform": platform, "account": name, "title": q.get("title", ""),
                                                  "description": q.get("description", ""), "hashtags": hashtags,
                                                  "video_type": q.get("video_type", "auto"), "cover": q.get("cover", "")})

    async def save_cover(request):
        """Read a JPG body, keep it 1 hour. Returns (token, None) or (None, error answer)."""
        jpg = await request.body()
        try:
            social.check_cover(jpg)
        except RuntimeError as e:
            return None, JSONResponse({"ok": False, "error": str(e)}, 400)
        return _new_token(COVERS, jpg=jpg), None

    async def cover(request):
        """POST /cover  body = JPG  -> {cover_id}; then add &cover=<cover_id> to /upload or /social/..."""
        token, error = await save_cover(request)
        return error or JSONResponse({"ok": True, "cover_id": token})

    async def cover_by_link(request):
        """POST /u/<token>/cover  body = JPG: the cover for that one-time upload link (send it BEFORE the video)."""
        item = _take(UPLOADS, request.path_params["token"])
        if not item:
            return JSONResponse({"ok": False, "error": "link expired or already used: call the tool again"}, 404)
        token, error = await save_cover(request)
        if error:
            return error
        item["meta"]["cover"] = token
        return JSONResponse({"ok": True, "cover": "saved, now send the video to the upload_url"})

    async def cover_file(request):
        """The cover image, public for 1 hour (Instagram downloads it from here)."""
        item = _take(COVERS, request.path_params["token"])
        if not item:
            return JSONResponse({"ok": False, "error": "cover expired"}, 404)
        return Response(item["jpg"], media_type="image/jpeg")

    async def social_list(request):
        """Every Instagram / Facebook account and whether its token works."""
        return JSONResponse(await asyncio.to_thread(social_accounts))

    async def upload_by_link(request):
        """One-time link from the upload_link tool: no key needed."""
        item = _take(UPLOADS, request.path_params["token"], once=True)
        if not item:
            return JSONResponse({"ok": False, "error": "link expired or already used: call upload_link again"}, 404)
        return await receive_and_upload(request, item["meta"])

    async def channels(request):
        """Every account with a token, and its channel."""
        return JSONResponse({a: await asyncio.to_thread(channel, a) for a in accounts()})

    async def voice_file(request):
        """Voice made by the make_voice tool (link works for 1 hour)."""
        item = _take(VOICES, request.path_params["token"])
        if not item:
            return JSONResponse({"ok": False, "error": "voice link expired: call make_voice again"}, 404)
        return Response(item["wav"], media_type="audio/wav")

    app = mcp.streamable_http_app(stateless_http=True, host="0.0.0.0")
    app.router.routes += [Route("/voice", voice, methods=["POST"]), Route("/upload", upload, methods=["POST"]),
                          Route("/u/{token}", upload_by_link, methods=["POST"]),
                          Route("/u/{token}/cover", cover_by_link, methods=["POST"]),
                          Route("/cover", cover, methods=["POST"]),
                          Route("/c/{token}.jpg", cover_file, methods=["GET"]),
                          Route("/channels", channels, methods=["GET"]),
                          Route("/social", social_list, methods=["GET"]),
                          Route("/social/{platform}/{name}", social_upload, methods=["POST"]),
                          Route("/v/{token}.wav", voice_file, methods=["GET"])]

    async def check_key(scope, receive, send):
        """Allow only requests with  ?key=API_KEY  or  Authorization: Bearer API_KEY.
        The random one-time links (/u/..., /v/..., /c/...) are their own key. /.well-known/ is left open so that
        claude.ai's connector check gets a plain 404 = "no OAuth login needed" (the key is in the URL)."""
        if scope["type"] == "http" and scope["path"].startswith(f"/{api_key}/"):
            # key inside the path: https://.../<API_KEY>/mcp  (for connectors that drop ?key=)
            scope = {**scope, "path": scope["path"][len(api_key) + 1:], "raw_path": None}
            return await app(scope, receive, send)
        if scope["type"] == "http" and not scope["path"].startswith(("/u/", "/v/", "/c/", "/.well-known/")):
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
