"""
Instagram + Facebook uploads (Meta Graph API). Used by youtube_mcp.py.

Accounts come from Render environment variables, one per account (add more any time, then restart):
  INSTAGRAM_ACCOUNT_<NAME> = {"user_id": "1784...", "access_token": "EAA... or IGAA..."}
  FACEBOOK_PAGE_<NAME>     = {"page_id": "1234...", "access_token": "EAA... (Page token)"}
<NAME> becomes the account name (lowercase), e.g. INSTAGRAM_ACCOUNT_RIDDLESPIXO -> "riddlespixo".

Short or long video:
  short = up to 90 seconds, long = more than 90 seconds ("auto" measures the MP4).
  Instagram: every video is a Reel (the API has no other video type); it is also shown on the profile grid.
  Facebook:  short -> the Page's Reels section,  long -> the Page's Videos (normal post).
"""
import json
import os
import struct
import time

import httpx

API_VERSION = "v21.0"
SHORT_MAX_SECONDS = 90
PREFIX = {"instagram": "INSTAGRAM_ACCOUNT_", "facebook": "FACEBOOK_PAGE_"}


# ---------------------------------------------------------------- accounts

def accounts(platform: str) -> list[str]:
    """Names of every account of one platform ("instagram" or "facebook") set on the server."""
    prefix = PREFIX[platform]
    return sorted(k[len(prefix):].lower() for k in os.environ if k.startswith(prefix))


def account(platform: str, name: str) -> dict:
    """The settings of one account: {user_id or page_id, access_token}."""
    value = os.environ.get(PREFIX[platform] + name.upper())
    if not value:
        raise RuntimeError(f"No {platform} account '{name}'. Accounts: {', '.join(accounts(platform)) or 'none'}")
    text = value.strip()
    for attempt in (text, text[1:-1]):        # also accept the value wrapped in '...' or "..."
        try:
            data = json.loads(attempt)
            if isinstance(data, str):         # JSON saved as a quoted string
                data = json.loads(data)
            if isinstance(data, dict):
                return data
        except ValueError:
            pass
    id_key = "user_id" if platform == "instagram" else "page_id"
    raise RuntimeError(f'{PREFIX[platform]}{name.upper()} must be JSON like {{"{id_key}": "...", "access_token": "..."}}')


# ---------------------------------------------------------------- small helpers

def make_caption(title: str, description: str, hashtags: list[str]) -> str:
    """Title, description and #hashtags joined into one caption."""
    tags = " ".join("#" + h.strip().lstrip("#").replace(" ", "") for h in hashtags or [] if h.strip())
    return "\n\n".join(part for part in (title.strip(), description.strip(), tags) if part)


def video_seconds(path: str) -> float:
    """Length of an MP4 in seconds, read from its header (0 if unknown)."""
    with open(path, "rb") as f:
        def boxes(start, end):
            pos = start
            while pos + 8 <= end:
                f.seek(pos)
                size, kind = struct.unpack(">I4s", f.read(8))
                header = 8
                if size == 1:
                    size, header = struct.unpack(">Q", f.read(8))[0], 16
                elif size == 0:
                    size = end - pos
                if size < header:
                    return
                yield kind, pos + header, pos + size
                pos += size

        for kind, start, end in boxes(0, os.path.getsize(path)):
            if kind == b"moov":
                for kind2, start2, _ in boxes(start, end):
                    if kind2 == b"mvhd":
                        f.seek(start2)
                        version = f.read(4)[0]
                        f.read(16 if version == 1 else 8)
                        scale, length = struct.unpack(">IQ" if version == 1 else ">II", f.read(12 if version == 1 else 8))
                        return length / scale if scale else 0
    return 0


def is_short(path: str, video_type: str = "auto") -> bool:
    """video_type "short" / "long" decides; "auto" = up to 90 seconds is short."""
    if video_type in ("short", "long"):
        return video_type == "short"
    return video_seconds(path) <= SHORT_MAX_SECONDS


def _answer(response: httpx.Response) -> dict:
    """JSON answer of Meta, or a clear error."""
    try:
        data = response.json()
    except ValueError:
        data = {"error": {"message": response.text[:300]}}
    if response.status_code >= 400 or "error" in data:
        raise RuntimeError(data.get("error", {}).get("message", str(data))[:300])
    return data


def _send_file(url: str, token: str, path: str) -> dict:
    """Send the whole MP4 to Meta's upload server (rupload.facebook.com)."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        return _answer(httpx.post(url, content=f, timeout=900, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)}))


# ---------------------------------------------------------------- Instagram

def instagram_upload(name: str, path: str, title: str, description: str, hashtags: list[str],
                     video_type: str = "auto") -> dict:
    """Post an MP4 as a Reel on one Instagram account. Returns {ok, url, posted_as}."""
    try:
        acc = account("instagram", name)
        token, user = acc["access_token"], acc["user_id"]
        # Facebook-login tokens (EAA...) use graph.facebook.com, Instagram-login tokens (IG...) graph.instagram.com
        host = acc.get("host") or ("graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com")
        api = f"https://{host}/{API_VERSION}"
        short = is_short(path, video_type)

        # 1. make an empty Reel ("container")
        box = _answer(httpx.post(f"{api}/{user}/media", timeout=60, data={
            "media_type": "REELS", "upload_type": "resumable", "share_to_feed": "true",
            "caption": make_caption(title, description, hashtags), "access_token": token}))
        # 2. send the video into it
        _send_file(box["uri"], token, path)
        # 3. wait until Instagram has processed it (max ~15 minutes)
        for _ in range(90):
            status = _answer(httpx.get(f"{api}/{box['id']}", timeout=60, params={
                "fields": "status_code,status", "access_token": token}))
            if status.get("status_code") == "FINISHED":
                break
            if status.get("status_code") in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram rejected the video: {status.get('status')}")
            time.sleep(10)
        else:
            raise RuntimeError("Instagram took too long to process the video")
        # 4. publish
        post = _answer(httpx.post(f"{api}/{user}/media_publish", timeout=60, data={
            "creation_id": box["id"], "access_token": token}))
        link = _answer(httpx.get(f"{api}/{post['id']}", timeout=60, params={
            "fields": "permalink", "access_token": token})).get("permalink", "")
        return {"ok": True, "platform": "instagram", "account": name, "url": link, "media_id": post["id"],
                "posted_as": "reel (short)" if short else "reel (long, also on profile grid)"}
    except Exception as e:
        return {"ok": False, "platform": "instagram", "account": name, "error": str(e)}


# ---------------------------------------------------------------- Facebook Page

def facebook_upload(name: str, path: str, title: str, description: str, hashtags: list[str],
                    video_type: str = "auto") -> dict:
    """Post an MP4 on one Facebook Page: short -> Reels, long -> Videos. Returns {ok, url, posted_as}."""
    try:
        acc = account("facebook", name)
        token, page = acc["access_token"], acc["page_id"]
        api = f"https://graph.facebook.com/{API_VERSION}"
        caption = make_caption(title, description, hashtags)

        if is_short(path, video_type):
            # Reel: start -> send file -> finish (publish)
            start = _answer(httpx.post(f"{api}/{page}/video_reels", timeout=60, data={
                "upload_phase": "start", "access_token": token}))
            _send_file(start["upload_url"], token, path)
            _answer(httpx.post(f"{api}/{page}/video_reels", timeout=60, data={
                "upload_phase": "finish", "video_id": start["video_id"], "video_state": "PUBLISHED",
                "title": title[:255], "description": caption, "access_token": token}))
            return {"ok": True, "platform": "facebook", "account": name, "posted_as": "reel (short)",
                    "url": f"https://www.facebook.com/reel/{start['video_id']}"}

        # Long video: one normal video post on the Page
        with open(path, "rb") as f:
            video = _answer(httpx.post(f"https://graph-video.facebook.com/{API_VERSION}/{page}/videos", timeout=1800,
                                       files={"source": ("video.mp4", f, "video/mp4")},
                                       data={"title": title[:255], "description": caption, "access_token": token}))
        return {"ok": True, "platform": "facebook", "account": name, "posted_as": "video post (long)",
                "url": f"https://www.facebook.com/{page}/videos/{video['id']}"}
    except Exception as e:
        return {"ok": False, "platform": "facebook", "account": name, "error": str(e)}


UPLOADERS = {"instagram": instagram_upload, "facebook": facebook_upload}


def check(platform: str, name: str) -> dict:
    """Is the token working? -> {ok, username / page name}."""
    try:
        acc = account(platform, name)
        token = acc["access_token"]
        if platform == "instagram":
            host = acc.get("host") or ("graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com")
            info = _answer(httpx.get(f"https://{host}/{API_VERSION}/{acc['user_id']}", timeout=60,
                                     params={"fields": "username", "access_token": token}))
            return {"ok": True, "platform": platform, "account": name, "username": "@" + info.get("username", "")}
        info = _answer(httpx.get(f"https://graph.facebook.com/{API_VERSION}/{acc['page_id']}", timeout=60,
                                 params={"fields": "name", "access_token": token}))
        return {"ok": True, "platform": platform, "account": name, "page": info.get("name")}
    except Exception as e:
        return {"ok": False, "platform": platform, "account": name, "error": str(e)}
