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

Cover (thumbnail): optional JPG image (9:16, e.g. 1080x1920, under 8 MB).
  Instagram downloads it from a public link (cover_url, the server makes one); Facebook gets the bytes.
"""
import json
import os
import struct
import time

import httpx

# Meta retires old API versions after ~2 years. Newer version = change META_API_VERSION on Render (no code change).
API_VERSION = os.environ.get("META_API_VERSION", "v27.0")
SHORT_MAX_SECONDS = 90
CAPTION_MAX = 2200        # Instagram: max caption length
HASHTAGS_MAX = 30         # Instagram: max hashtags in one caption
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
    """Title, description and #hashtags joined into one caption (max 30 hashtags, 2200 characters)."""
    if isinstance(hashtags, str):                      # "a, b c" also works
        hashtags = hashtags.replace(",", " ").split()
    tags, seen = [], set()
    for h in hashtags or []:
        tag = h.strip().lstrip("#").replace(" ", "")
        if tag and tag.lower() not in seen:            # no empty or repeated tags
            seen.add(tag.lower())
            tags.append("#" + tag)
    tag_text = " ".join(tags[:HASHTAGS_MAX])
    room = CAPTION_MAX - len(tag_text) - 4             # keep the hashtags, shorten the description if needed
    text = "\n\n".join(part for part in (title.strip(), description.strip()) if part)[:max(room, 0)]
    return "\n\n".join(part for part in (text, tag_text) if part)


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


def check_cover(cover: bytes | None) -> None:
    """A cover must be a JPG (Instagram accepts only JPG) under 8 MB."""
    if cover is not None and (not cover.startswith(bytes([0xFF, 0xD8])) or len(cover) > 8_000_000):
        raise RuntimeError("cover must be a JPG image under 8 MB (9:16, e.g. 1080x1920)")


def is_short(path: str, video_type: str = "auto") -> bool:
    """video_type "short" / "long" decides; "auto" = up to 90 seconds is short."""
    video_type = (video_type or "auto").strip().lower()
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
    """Send the whole MP4 to Meta's upload server (rupload.facebook.com). Tries 3 times: it sometimes
    fails for a moment ("ProcessingFailedError") and works on the next try."""
    size = os.path.getsize(path)
    for attempt in range(3):
        try:
            with open(path, "rb") as f:
                return _answer(httpx.post(url, content=f, timeout=900, headers={
                    "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)}))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(15)


# ---------------------------------------------------------------- Instagram

def instagram_upload(name: str, path: str, title: str, description: str, hashtags: list[str],
                     video_type: str = "auto", cover: bytes | None = None, cover_url: str = "") -> dict:
    """Post an MP4 as a Reel on one Instagram account. Returns {ok, url, posted_as}."""
    try:
        acc = account("instagram", name)
        token, user = acc["access_token"], acc["user_id"]
        # Facebook-login tokens (EAA...) use graph.facebook.com, Instagram-login tokens (IG...) graph.instagram.com
        host = acc.get("host") or ("graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com")
        api = f"https://{host}/{API_VERSION}"
        short = is_short(path, video_type)
        check_cover(cover)

        # 1. make an empty Reel ("container"); Instagram fetches the cover from cover_url itself
        details = {"media_type": "REELS", "upload_type": "resumable", "share_to_feed": "true",
                   "caption": make_caption(title, description, hashtags), "access_token": token}
        if cover_url:
            details["cover_url"] = cover_url
        box = _answer(httpx.post(f"{api}/{user}/media", timeout=60, data=details))
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
        # 4. publish (try 3 times: right after processing Instagram sometimes says "not ready yet")
        for attempt in range(3):
            try:
                post = _answer(httpx.post(f"{api}/{user}/media_publish", timeout=60, data={
                    "creation_id": box["id"], "access_token": token}))
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(15)
        try:     # the post is live now; a missing link is not an error
            link = _answer(httpx.get(f"{api}/{post['id']}", timeout=60, params={
                "fields": "permalink", "access_token": token})).get("permalink", "")
        except Exception:
            link = ""
        return {"ok": True, "platform": "instagram", "account": name, "url": link, "media_id": post["id"],
                "posted_as": "reel (short)" if short else "reel (long, also on profile grid)",
                "cover": "set" if cover_url else ("not set: the server is private, Instagram cannot download it"
                                                  if cover else "first frame (no cover sent)")}
    except Exception as e:
        return {"ok": False, "platform": "instagram", "account": name, "error": str(e)}


# ---------------------------------------------------------------- Facebook Page

def facebook_upload(name: str, path: str, title: str, description: str, hashtags: list[str],
                    video_type: str = "auto", cover: bytes | None = None, cover_url: str = "") -> dict:
    """Post an MP4 on one Facebook Page: short -> Reels, long -> Videos. Returns {ok, url, posted_as}."""
    try:
        acc = account("facebook", name)
        token, page = acc["access_token"], acc["page_id"]
        api = f"https://graph.facebook.com/{API_VERSION}"
        caption = make_caption(title, description, hashtags)
        check_cover(cover)
        cover_note = "set" if cover else "chosen by Facebook (no cover sent)"

        if is_short(path, video_type):
            # Reel: start -> send file -> finish (publish)
            start = _answer(httpx.post(f"{api}/{page}/video_reels", timeout=60, data={
                "upload_phase": "start", "access_token": token}))
            _send_file(start["upload_url"], token, path)
            _answer(httpx.post(f"{api}/{page}/video_reels", timeout=60, data={
                "upload_phase": "finish", "video_id": start["video_id"], "video_state": "PUBLISHED",
                "title": title[:255], "description": caption, "access_token": token}))
            if cover:   # the Reel's cover (thumbnail)
                try:
                    _answer(httpx.post(f"{api}/{start['video_id']}/thumbnails", timeout=120,
                                       files={"source": ("cover.jpg", cover, "image/jpeg")},
                                       data={"is_preferred": "true", "access_token": token}))
                except Exception as e:
                    cover_note = f"not set: {e}"
            return {"ok": True, "platform": "facebook", "account": name, "posted_as": "reel (short)",
                    "url": f"https://www.facebook.com/reel/{start['video_id']}", "cover": cover_note}

        # Long video: one normal video post on the Page
        with open(path, "rb") as f:
            files = {"source": ("video.mp4", f, "video/mp4")}
            if cover:   # the video's cover (thumbnail) goes with it
                files["thumb"] = ("cover.jpg", cover, "image/jpeg")
            video = _answer(httpx.post(f"https://graph-video.facebook.com/{API_VERSION}/{page}/videos", timeout=1800,
                                       files=files,
                                       data={"title": title[:255], "description": caption, "access_token": token}))
        return {"ok": True, "platform": "facebook", "account": name, "posted_as": "video post (long)",
                "url": f"https://www.facebook.com/{page}/videos/{video['id']}", "cover": cover_note}
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
