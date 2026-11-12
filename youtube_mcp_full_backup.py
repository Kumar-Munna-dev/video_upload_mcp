#!/usr/bin/env python3
"""
YouTube Upload MCP Server
-------------------------
A small, Zapier-style MCP server that uploads videos to YouTube and supports
multiple Google/YouTube accounts (e.g. laptopuse18 + online93342).

Setup (one time):
  1. pip install mcp google-api-python-client google-auth-oauthlib
  2. Put your OAuth "Desktop app" client file at  ~/.youtube-mcp/client_secret.json
  3. Log in each account:
        python youtube_mcp.py auth main
        python youtube_mcp.py auth online93342
     (a browser opens -> pick the right Google account -> Allow)

Run as MCP server (stdio):
  python youtube_mcp.py
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# ---------------------------------------------------------------- config ----
BASE_DIR = Path(os.environ.get("YT_MCP_DIR", Path.home() / ".youtube-mcp"))
CLIENT_SECRET = BASE_DIR / "client_secret.json"
TOKENS_DIR = BASE_DIR / "tokens"
SETTINGS = BASE_DIR / "settings.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",  # thumbnails, playlists, listing
]
PRIVACY = {"public", "private", "unlisted"}
CHUNK = 8 * 1024 * 1024  # 8 MB resumable chunks


def log(*a):
    """Log to stderr only — stdout is reserved for the MCP protocol."""
    print(*a, file=sys.stderr, flush=True)


# -------------------------------------------------------------- accounts ----
def _settings() -> dict:
    if SETTINGS.exists():
        return json.loads(SETTINGS.read_text())
    return {}


def _save_settings(s: dict) -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(s, indent=2))


def _token_path(account: str) -> Path:
    safe = "".join(c for c in account if c.isalnum() or c in "-_.@")
    return TOKENS_DIR / f"{safe}.json"


def _accounts() -> list[str]:
    if not TOKENS_DIR.exists():
        return []
    return sorted(p.stem for p in TOKENS_DIR.glob("*.json"))


def _resolve_account(account: Optional[str]) -> str:
    if account:
        return account
    default = _settings().get("default_account")
    if default:
        return default
    accs = _accounts()
    if len(accs) == 1:
        return accs[0]
    if not accs:
        raise RuntimeError(
            "No YouTube account logged in. Run:  python youtube_mcp.py auth <name>"
        )
    raise RuntimeError(
        f"Several accounts found {accs}; pass `account` or call set_default_account."
    )


def login(account: str) -> str:
    """Interactive browser login; stores a refresh token for `account`."""
    if not CLIENT_SECRET.exists():
        raise RuntimeError(f"Missing OAuth client file: {CLIENT_SECRET}")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    # Keep any library prints off stdout (would corrupt MCP stdio).
    with contextlib.redirect_stdout(sys.stderr):
        creds = flow.run_local_server(
            port=0, prompt="consent select_account", access_type="offline"
        )
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    _token_path(account).write_text(creds.to_json())
    s = _settings()
    s.setdefault("default_account", account)
    _save_settings(s)
    return account


def _youtube(account: Optional[str] = None):
    acc = _resolve_account(account)
    path = _token_path(acc)
    if not path.exists():
        raise RuntimeError(
            f"Account '{acc}' is not logged in. Run:  python youtube_mcp.py auth {acc}"
        )
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            path.write_text(creds.to_json())
        else:
            raise RuntimeError(
                f"Login for '{acc}' expired. Run:  python youtube_mcp.py auth {acc}"
            )
    return build("youtube", "v3", credentials=creds, cache_discovery=False), acc


def _err(e: Exception) -> dict:
    if isinstance(e, HttpError):
        try:
            detail = json.loads(e.content.decode())["error"]["message"]
        except Exception:
            detail = str(e)
        return {"ok": False, "error": f"YouTube API {e.resp.status}: {detail}"}
    return {"ok": False, "error": str(e)}


# ------------------------------------------------------------- core ops -----
def upload_video_impl(
    file_path: str,
    title: str,
    description: str = "",
    tags: Optional[list[str]] = None,
    privacy: str = "public",
    category_id: str = "24",
    made_for_kids: bool = False,
    publish_at: Optional[str] = None,
    thumbnail_path: Optional[str] = None,
    playlist_id: Optional[str] = None,
    account: Optional[str] = None,
) -> dict:
    fp = Path(file_path).expanduser()
    if not fp.is_file():
        return {"ok": False, "error": f"File not found: {fp}"}
    if privacy not in PRIVACY:
        return {"ok": False, "error": f"privacy must be one of {sorted(PRIVACY)}"}
    if len(title) > 100:
        return {"ok": False, "error": "Title is longer than 100 characters."}

    try:
        yt, acc = _youtube(account)
        status = {
            "privacyStatus": "private" if publish_at else privacy,
            "selfDeclaredMadeForKids": made_for_kids,
        }
        if publish_at:  # scheduled publish requires private + ISO 8601 time
            status["publishAt"] = publish_at
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": status,
        }
        media = MediaFileUpload(str(fp), chunksize=CHUNK, resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

        resp = None
        while resp is None:
            prog, resp = req.next_chunk(num_retries=5)
            if prog:
                log(f"[{acc}] upload {int(prog.progress() * 100)}%")

        vid = resp["id"]
        result = {
            "ok": True,
            "account": acc,
            "video_id": vid,
            "url": f"https://youtu.be/{vid}",
            "shorts_url": f"https://youtube.com/shorts/{vid}",
            "privacy": resp["status"]["privacyStatus"],
            "upload_status": resp["status"].get("uploadStatus"),
            "publish_at": resp["status"].get("publishAt"),
            "warnings": [],
        }

        if privacy == "public" and not publish_at and result["privacy"] != "public":
            result["warnings"].append(
                "YouTube kept this video private. Uploads from an unverified Google "
                "Cloud project are locked to private until the project passes "
                "YouTube's API audit."
            )

        if thumbnail_path:
            tp = Path(thumbnail_path).expanduser()
            try:
                yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(tp))).execute()
                result["thumbnail"] = "set"
            except Exception as e:  # thumbnail failure shouldn't fail the upload
                result["warnings"].append(f"Thumbnail not set: {_err(e)['error']}")

        if playlist_id:
            try:
                yt.playlistItems().insert(
                    part="snippet",
                    body={"snippet": {"playlistId": playlist_id,
                                      "resourceId": {"kind": "youtube#video", "videoId": vid}}},
                ).execute()
                result["playlist"] = playlist_id
            except Exception as e:
                result["warnings"].append(f"Not added to playlist: {_err(e)['error']}")

        return result
    except Exception as e:
        return _err(e)


def channel_info_impl(account: Optional[str] = None) -> dict:
    try:
        yt, acc = _youtube(account)
        r = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()
        if not r.get("items"):
            return {"ok": False, "account": acc, "error": "This Google account has no YouTube channel."}
        c = r["items"][0]
        return {
            "ok": True,
            "account": acc,
            "channel_id": c["id"],
            "title": c["snippet"]["title"].strip(),
            "handle": c["snippet"].get("customUrl"),
            "subscribers": c["statistics"].get("subscriberCount"),
            "views": c["statistics"].get("viewCount"),
            "videos": c["statistics"].get("videoCount"),
            "uploads_playlist": c["contentDetails"]["relatedPlaylists"]["uploads"],
        }
    except Exception as e:
        return _err(e)


def list_videos_impl(max_results: int = 10, account: Optional[str] = None) -> dict:
    try:
        info = channel_info_impl(account)
        if not info.get("ok"):
            return info
        yt, acc = _youtube(account)
        items = yt.playlistItems().list(
            part="snippet,status", playlistId=info["uploads_playlist"],
            maxResults=max(1, min(max_results, 50)),
        ).execute().get("items", [])
        return {
            "ok": True,
            "account": acc,
            "videos": [
                {
                    "video_id": i["snippet"]["resourceId"]["videoId"],
                    "title": i["snippet"]["title"],
                    "published_at": i["snippet"]["publishedAt"],
                    "privacy": i.get("status", {}).get("privacyStatus"),
                    "url": f"https://youtu.be/{i['snippet']['resourceId']['videoId']}",
                }
                for i in items
            ],
        }
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------ MCP server ----
def build_server():
    try:  # mcp SDK 2.x
        from mcp.server.mcpserver import MCPServer as _Server
    except ImportError:  # mcp SDK 1.x
        from mcp.server.fastmcp import FastMCP as _Server

    mcp = _Server("youtube-uploader")

    @mcp.tool()
    def upload_video(
        file_path: str,
        title: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        privacy: str = "public",
        category_id: str = "24",
        made_for_kids: bool = False,
        publish_at: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
        playlist_id: Optional[str] = None,
        account: Optional[str] = None,
    ) -> dict:
        """Upload a local video file to YouTube.

        file_path: absolute path to the .mp4 on this computer.
        title: max 100 chars. Add #shorts for Shorts (vertical, under 3 min).
        privacy: public | unlisted | private.
        category_id: 24=Entertainment, 22=People & Blogs, 27=Education, 1=Film & Animation.
        made_for_kids: True only if the video is directed at children.
        publish_at: optional ISO 8601 UTC time (e.g. 2026-11-12T12:30:00Z) to schedule.
        account: which logged-in account to use (see list_accounts); default if omitted.
        """
        return upload_video_impl(file_path, title, description, tags, privacy,
                                 category_id, made_for_kids, publish_at,
                                 thumbnail_path, playlist_id, account)

    @mcp.tool()
    def list_accounts() -> dict:
        """List YouTube accounts logged in to this server and the default one."""
        return {"accounts": _accounts(), "default": _settings().get("default_account")}

    @mcp.tool()
    def set_default_account(account: str) -> dict:
        """Make `account` the default for uploads."""
        if account not in _accounts():
            return {"ok": False, "error": f"Unknown account. Logged in: {_accounts()}"}
        s = _settings()
        s["default_account"] = account
        _save_settings(s)
        return {"ok": True, "default": account}

    @mcp.tool()
    def login_account(account: str) -> dict:
        """Log in a new YouTube account (opens a browser on this computer)."""
        try:
            return {"ok": True, "account": login(account),
                    "channel": channel_info_impl(account)}
        except Exception as e:
            return _err(e)

    @mcp.tool()
    def remove_account(account: str) -> dict:
        """Forget a logged-in account (deletes its saved token on this computer)."""
        p = _token_path(account)
        if not p.exists():
            return {"ok": False, "error": f"Unknown account. Logged in: {_accounts()}"}
        p.unlink()
        s = _settings()
        if s.get("default_account") == account:
            rest = _accounts()
            s["default_account"] = rest[0] if rest else None
            _save_settings(s)
        return {"ok": True, "removed": account, "default": s.get("default_account")}

    @mcp.tool()
    def channel_info(account: Optional[str] = None) -> dict:
        """Channel name, handle, subscribers, views and video count."""
        return channel_info_impl(account)

    @mcp.tool()
    def list_my_videos(max_results: int = 10, account: Optional[str] = None) -> dict:
        """Latest uploads on the channel, newest first."""
        return list_videos_impl(max_results, account)

    return mcp


# ------------------------------------------------------------------- CLI ----
def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "auth":
        acc = argv[2] if len(argv) > 2 else "main"
        login(acc)
        info = channel_info_impl(acc)
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return 0
    if len(argv) >= 2 and argv[1] == "accounts":
        print(json.dumps({"accounts": _accounts(), "default": _settings().get("default_account")}, indent=2))
        return 0
    if len(argv) >= 2 and argv[1] == "upload":
        import argparse
        p = argparse.ArgumentParser(prog="youtube_mcp.py upload")
        p.add_argument("file"); p.add_argument("--title", required=True)
        p.add_argument("--description", default=""); p.add_argument("--tags", default="")
        p.add_argument("--privacy", default="public"); p.add_argument("--account")
        p.add_argument("--thumbnail"); p.add_argument("--publish-at")
        a = p.parse_args(argv[2:])
        tags = [t.strip() for t in a.tags.split(",") if t.strip()]
        r = upload_video_impl(a.file, a.title, a.description, tags, a.privacy,
                              publish_at=a.publish_at, thumbnail_path=a.thumbnail,
                              account=a.account)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if r.get("ok") else 1
    build_server().run()  # stdio
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
