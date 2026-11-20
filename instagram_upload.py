"""
Instagram par video (Reel) upload karne ka simple script.
Sirf Python ki standard library use hoti hai - kuch bhi pip install nahi karna.

Kaise chalayein:
    python instagram_upload.py check                     # teeno accounts ke token check karo
    python instagram_upload.py check riddlespixo         # sirf ek account check karo
    python instagram_upload.py upload riddlespixo video.mp4 "Mera caption #reels"

Pehle instagram.json file banao (isi folder mein) - har account ka apna token aur user_id:
    {
      "riddlespixo":   {"access_token": "IGAA...", "user_id": "1784..."},
      "pixelkatha3d":  {"access_token": "IGAA...", "user_id": "1784..."},
      "scielifeindia": {"access_token": "IGAA...", "user_id": "1784..."}
    }
Token kaise milega -> INSTAGRAM_SETUP.md padho.

Upload 4 steps mein hota hai (Instagram ka official tarika, "resumable upload"):
    1. Instagram ko batao: "main ek Reel bhejne wala hoon"  -> woh ek container ID deta hai
    2. Video file us container mein bhej do
    3. Intezaar karo jab tak Instagram video process kar le
    4. "Publish" bolo -> Reel aapke profile par aa jaati hai
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Instagram API ka address aur version.
# Agar aapka token "Facebook Login" wala hai (EAA... se shuru), to host "graph.facebook.com" kar do
# (instagram.json mein "host": "graph.facebook.com" likh kar).
DEFAULT_HOST = "graph.instagram.com"
API_VERSION = "v27.0"     # Meta retires old versions after ~2 years; v21.0 is already retired

CONFIG_FILE = Path(__file__).with_name("instagram.json")


# ---------------------------------------------------------------------------
# Chhote helper functions
# ---------------------------------------------------------------------------

def all_accounts() -> dict:
    """instagram.json padho -> {account_naam: {access_token, user_id}}"""
    if not CONFIG_FILE.exists():
        sys.exit(f"'{CONFIG_FILE.name}' nahi mili. INSTAGRAM_SETUP.md dekh kar banao.")
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def load_config(account: str) -> dict:
    """Ek account (jaise "riddlespixo") ka token aur user_id lauta do."""
    accounts = all_accounts()
    if account not in accounts:
        sys.exit(f"'{account}' instagram.json mein nahi hai. Ye accounts hain: {', '.join(accounts)}")
    config = accounts[account]
    for key in ("access_token", "user_id"):
        if not config.get(key):
            sys.exit(f"instagram.json mein '{account}' ka '{key}' khali hai.")
    config.setdefault("host", DEFAULT_HOST)
    return config


def call_api(method: str, url: str, params: dict | None = None,
             headers: dict | None = None, body: bytes | None = None) -> dict:
    """
    Instagram API ko ek request bhejo aur jawab (JSON) lauta do.
    method = "GET" ya "POST", params = URL ke ?a=b&c=d wale parameters.
    """
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        # Instagram galti ka kaaran JSON mein bhejta hai - use saaf dikhao
        details = error.read().decode(errors="replace")
        try:
            details = json.loads(details)["error"]["message"]
        except (ValueError, KeyError):
            pass
        sys.exit(f"Instagram error {error.code}: {details}")


def api_url(config: dict, path: str) -> str:
    """Example: api_url(config, "me") -> https://graph.instagram.com/v21.0/me"""
    return f"https://{config['host']}/{API_VERSION}/{path}"


# ---------------------------------------------------------------------------
# Command 1: check  -> token sahi hai ya nahi
# ---------------------------------------------------------------------------

def check(account: str) -> None:
    config = load_config(account)
    info = call_api("GET", api_url(config, config["user_id"]), {
        "fields": "username",
        "access_token": config["access_token"],
    })
    print(f"{account}: token sahi hai -> @{info.get('username')}")


# ---------------------------------------------------------------------------
# Command 2: upload -> video ko Reel bana kar post karo
# ---------------------------------------------------------------------------

def upload(account: str, video_path: str, caption: str) -> None:
    config = load_config(account)
    print(f"Account: {account}")
    token = config["access_token"]
    video = Path(video_path)
    if not video.exists():
        sys.exit(f"Video file nahi mili: {video}")
    size = video.stat().st_size
    print(f"Video: {video.name} ({size / 1_000_000:.1f} MB)")

    # --- Step 1: container banao -------------------------------------------
    print("1/4  Instagram par jagah bana rahe hain...")
    container = call_api("POST", api_url(config, f"{config['user_id']}/media"), {
        "media_type": "REELS",
        "upload_type": "resumable",   # matlab: file hum khud bhejenge (koi public link nahi chahiye)
        "caption": caption,
        "share_to_feed": "true",      # Reel profile grid mein bhi dikhe
        "access_token": token,
    })
    container_id = container["id"]
    upload_url = container["uri"]     # Instagram batata hai video kahan bhejni hai

    # --- Step 2: video file bhejo ------------------------------------------
    print("2/4  Video bhej rahe hain (badi file mein thoda time lagega)...")
    result = call_api("POST", upload_url, headers={
        "Authorization": f"OAuth {token}",
        "offset": "0",                # shuru se bhej rahe hain
        "file_size": str(size),
    }, body=video.read_bytes())
    if not result.get("success"):
        sys.exit(f"Video upload fail hua: {result}")

    # --- Step 3: processing ka intezaar ------------------------------------
    print("3/4  Instagram video process kar raha hai...")
    for _ in range(60):               # zyada se zyada ~10 minute (60 x 10 second)
        status = call_api("GET", api_url(config, container_id), {
            "fields": "status_code,status",
            "access_token": token,
        })
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            sys.exit(f"Instagram ne video reject kar di: {status.get('status')}\n"
                     "Video MP4 (H.264 + AAC), 9:16, 3 sec se 15 min ki honi chahiye.")
        print(f"     ...abhi {code}, 10 second ruk rahe hain")
        time.sleep(10)
    else:
        sys.exit("Processing mein bahut time lag gaya. Thodi der baad dobara try karo.")

    # --- Step 4: publish ---------------------------------------------------
    print("4/4  Publish kar rahe hain...")
    post = call_api("POST", api_url(config, f"{config['user_id']}/media_publish"), {
        "creation_id": container_id,
        "access_token": token,
    })
    link = call_api("GET", api_url(config, post["id"]), {
        "fields": "permalink",
        "access_token": token,
    }).get("permalink", "")
    print(f"Ho gaya! Reel live hai: {link or post['id']}")


# ---------------------------------------------------------------------------
# Program yahan se shuru hota hai
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["check"]:
        for name in (args[1:] or all_accounts()):   # naam diya to wahi, warna sab accounts
            check(name)
    elif args[:1] == ["upload"] and len(args) >= 3:
        upload(args[1], args[2], args[3] if len(args) > 3 else "")
    else:
        print(__doc__)
