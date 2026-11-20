# 📘 Poori Guide (Detailed): Video Upload MCP Server

Yeh guide **shuru se aakhir tak** sab kuch batati hai. Jaldi wali chhoti guide [README.md](README.md) mein hai.

**Fehrist (Contents)**
1. [Yeh kya hai](#1-yeh-kya-hai)
2. [Files aur unka kaam](#2-files-aur-unka-kaam)
3. [Ek video ka safar](#3-ek-video-ka-safar-andar-kya-hota-hai)
4. [Zero se setup](#4-zero-se-setup-naya-server-banana)
5. [Environment variables (saare dabbe)](#5-environment-variables-saare-dabbe)
6. [MCP tools (AI ke liye)](#6-mcp-tools-ai-ke-liye)
7. [Web endpoints (curl ke liye)](#7-web-endpoints-curl-ke-liye)
8. [PC commands](#8-pc-commands)
9. [Accounts jodna / hatana](#9-accounts-jodna--hatana)
10. [Keys / tokens badalna](#10-keys--tokens-badalna)
11. [Code badalna (developer guide)](#11-code-badalna-developer-guide)
12. [Limits (seemayen)](#12-limits-seemayen)
13. [Security (suraksha)](#13-security-suraksha)
14. [Problems aur hal](#14-problems-aur-hal)
15. [Maintenance calendar](#15-maintenance-calendar)

---

## 1. Yeh kya hai

Ek chhota **Python web server** jo:
- 🎬 video ko **YouTube**, **Instagram** (Reel) aur **Facebook Page** (Reel / video post) par upload karta hai,
- 🖼️ har video ka **thumbnail (cover)** lagata hai,
- 🗣️ **Hindi voice-over** banata hai (Sarvam AI, Bulbul V4 Flash),
- 🤖 yeh sab **MCP tools** ke roop mein deta hai, taaki koi bhi AI (Claude, Cursor, …) ise chala sake.

```
                       ┌──────────────── Server ───────────────┐
  AI (MCP tool)  ───▶  │ youtube_mcp.py  (MCP + web routes)    │ ──▶ YouTube Data API
  PC (render_client) ▶ │ social.py       (Instagram/Facebook)  │ ──▶ Meta Graph API (Instagram, Facebook)
  curl           ───▶  │ sarvam_voice.py (aawaz)               │ ──▶ Sarvam AI
                       └───────────────────────────────────────┘
```

Server **do jagah** chalta hai, aur dono mein code same hai (GitHub `main` branch):

| | 🟣 Render | 🔵 Google Cloud Run |
|---|---|---|
| Address | `https://youtube-mcp-5wk1.onrender.com` | `https://autimate-mcp-559325411060.asia-south1.run.app` |
| Kaun chala sakta hai | jiske paas API key | sirf aapka Google login **+** API key |
| AI connector (claude.ai) | ✅ chalta hai | ❌ (private) |
| Instagram cover | ✅ | ❌ (Instagram private server se image nahi le sakta) |
| Badi video (>32 MB) | ✅ | ✅ (HTTP/2) |
| Sota hai? | haan, 15 min idle ke baad (~1 min jaagne mein) | 0 par scale hota hai (~10-20 s jaagne mein) |
| Naya code kaise aata hai | GitHub push → auto deploy | GitHub push → Cloud Build → auto deploy |

**Accounts abhi:** `pixelkatha3d`, `riddlespixo`, `scielifeindia`. Teeno YouTube, Instagram aur Facebook par hain.

---

## 2. Files aur unka kaam

| File | Kaam | Andar ke khaas hisse |
|---|---|---|
| [`youtube_mcp.py`](youtube_mcp.py) | 🧠 server ka dimaag | `upload_file()` YouTube upload · `@mcp.tool()` functions · `social_tool()` har account ka tool banata hai · `run_http()` saare web routes + API key check (`check_key`) |
| [`social.py`](social.py) | 📸👍 Instagram + Facebook | `accounts()` / `account()` env se accounts · `make_caption()` · `video_seconds()` MP4 ki lambai · `instagram_upload()` · `facebook_upload()` · `check()` |
| [`sarvam_voice.py`](sarvam_voice.py) | 🗣️ aawaz | `speak(text, speaker, pace)` → WAV · lamba text tukdon mein |
| [`render_client.py`](render_client.py) | 💻 PC → server | `voice`, `upload`, `social`, `channels` commands · Cloud Run ke liye gcloud login khud lagata hai |
| [`instagram_upload.py`](instagram_upload.py) | PC → seedha Instagram (bina server) | `instagram.json` padhta hai |
| [`Dockerfile`](Dockerfile) | 🔵 Cloud Run image | sirf 3 code files copy, `HTTP2=1` |
| [`.dockerignore`](.dockerignore) | image mein secrets/videos na jaayein | |
| [`render.yaml`](render.yaml) | 🟣 Render settings | env var ke naam |
| [`requirements.txt`](requirements.txt) | Python packages | `mcp`, `uvicorn`, `hypercorn`, `httpx`, Google API |
| [`.gitignore`](.gitignore) | GitHub par kya **nahi** jaata | `apikey.txt`, `*.json`, `*.env`, `*.mp4` … |
| [`README.md`](README.md) | chhoti aasaan guide | |
| [`INSTAGRAM_SETUP.md`](INSTAGRAM_SETUP.md) | Instagram ka pehla setup | |

**PC par (GitHub par nahi):**

| File | Kya hai |
|---|---|
| `apikey.txt` | server ki API key |
| `instagram.json` | Instagram tokens (`instagram_upload.py` ke liye) |
| `facebook.json` | Facebook Page tokens |
| `instagram.env`, `youtube.env` | Render "Add from .env" ke liye taiyaar lines |
| `C:\Users\<aap>\.youtube-mcp\client_secret.json` | Google OAuth app (YouTube login ke liye) |
| `C:\Users\<aap>\.youtube-mcp\tokens\<channel>.json` | har YouTube channel ka token |
| `C:\Users\<aap>\.youtube-mcp\api_key.txt`, `sarvam_key.txt`, `connector_url.txt` | keys / connector address |

---

## 3. Ek video ka safar (andar kya hota hai)

### 3.1 AI se (MCP tool)
1. AI tool chalata hai, jaise `instagram_riddlespixo(title, description, hashtags)`.
2. Server ek **random one-time link** banata hai: `<server>/u/<token>` (1 ghanta, 1 baar). Title/description wagaira link ke saath memory mein yaad rehte hain.
3. (Optional) AI JPG thumbnail bhejta hai: `POST <link>/cover`. Server use 1 ghante ke liye rakh leta hai.
4. AI video bhejta hai: `POST <link>` (body = MP4).
5. Server video ko temp file mein likhta hai, upload karta hai, **file delete** karta hai aur jawab mein post ka link deta hai.

> Link ek baar mein khatam ho jaata hai. Agar video khali pahunche (galat path), to link dobara chal sakta hai.

### 3.2 YouTube ke andar
`upload_file()` → YouTube `videos.insert` (4 MB tukdon mein, resumable) → (cover ho to) `thumbnails.set`.
Privacy default **private**. Category default 22 (People & Blogs).

### 3.3 Instagram ke andar (`instagram_upload()`)
1. `POST /{user_id}/media` → `media_type=REELS`, `upload_type=resumable`, `share_to_feed=true`, caption, (cover_url). Jawab mein **container** milta hai.
2. Video bytes `rupload.facebook.com` par bheji jaati hain (3 baar try).
3. Har 10 second `status_code` check: `FINISHED` hone tak (max ~15 min).
4. `POST /{user_id}/media_publish` (3 baar try) → post live.
5. `permalink` = Reel ka link.

Instagram par **har video Reel** banti hai. Lambi video bhi profile grid par dikhti hai.

### 3.4 Facebook ke andar (`facebook_upload()`)
- **Short (≤ 90 s)** → Reels: `video_reels` `start` → video bhejna → `finish` (PUBLISHED) → cover ho to `/{video_id}/thumbnails`.
- **Long (> 90 s)** → normal video post: `graph-video.facebook.com/{page_id}/videos` (video + `thumb` ek saath).
- `video_type`: `auto` (MP4 ki lambai khud naapi jaati hai), `short`, ya `long`.

### 3.5 Caption kaise banta hai (`make_caption()`)
```
<title>

<description>

#tag1 #tag2 ...
```
- `#` khud lagta hai, spaces hat jaate hain, repeat tags hat jaate hain, **max 30** tags.
- Kul **2200** characters se zyada ho to description chhota hota hai (hashtags bache rehte hain).

---

## 4. Zero se setup (naya server banana)

> Aapka setup pehle se bana hua hai. Yeh section tab ke liye hai jab sab dobara banana pade (naya account, naya computer).

### 4.1 PC
1. Python 3.11+ install karo.
2. Repo clone karo:
   ```bash
   git clone https://github.com/Kumar-Munna-dev/video_upload_mcp.git
   ```
3. Packages:
   ```bash
   pip install -r requirements.txt
   ```
4. API key banao aur `apikey.txt` mein rakho:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

### 4.2 YouTube (Google OAuth)
1. [console.cloud.google.com](https://console.cloud.google.com) → project → **APIs & Services → Library** → **YouTube Data API v3** → Enable.
2. **Google Auth Platform → Branding**: app name, support email, developer email.
3. **Audience**: External. Test users mein har channel ka Gmail jodo.
4. **Clients → Create client → Desktop app** → JSON download → `C:\Users\<aap>\.youtube-mcp\client_secret.json` naam se rakho.
5. Har channel ke liye:
   ```bash
   python youtube_mcp.py auth riddlespixo
   ```
   Browser → sahi account → **sahi channel** → Allow → `tokens\riddlespixo.json` banta hai.
   Permissions: sirf `youtube.upload` + `youtube.readonly`.

### 4.3 Instagram + Facebook (Meta)
Poori detail: [INSTAGRAM_SETUP.md](INSTAGRAM_SETUP.md). Chhote mein:
1. Har Instagram account **Professional** aur ek **Facebook Page** se juda ho.
2. [developers.facebook.com](https://developers.facebook.com) → app banao (use case: *Manage messaging & content on Instagram*). Aapka app: **automate-mcp**.
3. **Instagram token:** Use cases → Instagram API → **API setup with Unified login** → Add account → Generate token → `user_id` + token.
4. **Facebook Page token:** Graph API Explorer → permissions `pages_show_list, pages_read_engagement, pages_manage_posts, business_management` → Generate → Extend → `me/accounts` → har Page ka `id` + `access_token`.

### 4.4 Sarvam (aawaz)
[dashboard.sarvam.ai](https://dashboard.sarvam.ai) → API key → `SARVAM_API_KEY` dabba (aur PC par `sarvam_key.txt`).

### 4.5 Render par chalana
1. [render.com](https://render.com) → **New → Blueprint** → GitHub repo chuno (woh `render.yaml` padhta hai).
2. **Environment** mein saare dabbe daalo (section 5). `instagram.env` / `youtube.env` ke liye **Add from .env**.
3. Deploy → `https://<naam>.onrender.com/health` → `"ok": true`.

### 4.6 Google Cloud Run par chalana
1. Cloud Console → **Cloud Run → Deploy container → Continuously deploy from a repository** → GitHub → repo → branch `main` → Build type **Dockerfile**.
2. Region `asia-south1`, Authentication **Require authentication** (private).
3. Phir PC se settings:
   ```bash
   gcloud run services update autimate-mcp --region asia-south1 --use-http2 --timeout 3600 --max-instances 1 --memory 1Gi --env-vars-file cloudrun-env.yaml
   ```
   `cloudrun-env.yaml` (PC par hi rakho, commit mat karo) mein saare dabbe `NAAM: "value"` format mein, plus:
   `HTTP2: "1"`, `COVER_LINKS: "off"`, `PUBLIC_URL: "<service url>"`.
4. Check (aapke login se):
   ```bash
   set YT_SERVER=https://autimate-mcp-559325411060.asia-south1.run.app
   ```
   ```bash
   python render_client.py social
   ```

**Kyun yeh settings?**
- `--use-http2` + `HTTP2=1`: Cloud Run HTTP/1 mein 32 MB se badi request nahi leta. HTTP/2 se koi seema nahi.
- `--timeout 3600`: Instagram processing mein kai minute lag sakte hain.
- `--max-instances 1`: one-time links memory mein rehte hain. Doosre instance ko unka pata nahi hota.

---

## 5. Environment variables (saare dabbe)

| Dabba | Zaroori? | Value | Kaam |
|---|---|---|---|
| `API_KEY` | ✅ | lamba random text | server ki chaabi |
| `SARVAM_API_KEY` | aawaz ke liye | Sarvam key | `make_voice`, `/voice` |
| `YOUTUBE_TOKEN_<NAAM>` | har channel | `tokens\<naam>.json` ka poora text | tool `upload_link(account="<naam>")` |
| `INSTAGRAM_ACCOUNT_<NAAM>` | har IG account | `{"user_id": "...", "access_token": "..."}` | tool `instagram_<naam>` |
| `FACEBOOK_PAGE_<NAAM>` | har Page | `{"page_id": "...", "access_token": "..."}` | tool `facebook_<naam>` |
| `META_API_VERSION` | nahi | default `v27.0` | Meta purana version band kare to badlo |
| `PUBLIC_URL` | Cloud Run / doosra host | server ka address | Instagram cover link isi se banta hai (Render khud deta hai) |
| `HTTP2` | Cloud Run | `1` | hypercorn (HTTP/2) chalata hai |
| `COVER_LINKS` | private server | `off` | Instagram cover chhod do |
| `PORT` | host khud deta hai | | |

- `<NAAM>` hamesha **CAPITAL** mein. Tool ka naam **chhote** aksharon mein ban jaata hai: `INSTAGRAM_ACCOUNT_RIDDLESPIXO` → `instagram_riddlespixo`.
- Value `'...'` quotes mein lipti ho tab bhi chalega (Render "Add from .env" quotes rakh leta hai).
- Dabba badalne ke baad server **restart** hota hai. Naye tools tabhi dikhte hain.

---

## 6. MCP tools (AI ke liye)

| Tool | Zaroori | Optional | Kya deta hai |
|---|---|---|---|
| `instagram_<naam>` | `title`, `description`, `hashtags` (list) | `video_type` (auto/short/long) | one-time `upload_url` + `cover_first` + `then_video` commands |
| `facebook_<naam>` | `title`, `description`, `hashtags` | `video_type` | same |
| `upload_link` (YouTube) | `title`, `account` | `description`, `tags`, `privacy` (public/unlisted/private), `category` | one-time `upload_url` |
| `upload_video` (YouTube) | `video_url` (public link), `title`, `account` | `description`, `tags`, `privacy` | seedha upload (server khud download karta hai) |
| `make_voice` | `text` | `speaker` (male/female/voice naam), `pace` (0.5-2) | WAV `download_url` (1 ghanta) |
| `social_accounts` | – | – | har Instagram/Facebook account + token chal raha ya nahi |
| `channel_info` | – | – | har YouTube channel: naam, subscribers, videos |

**AI ke liye example baat-cheet:**
> "riddlespixo ke Instagram aur Facebook par `video.mp4` daalo, cover `cover.jpg`, title 'Aaj ki paheli', 8 hashtags."

AI karega: `instagram_riddlespixo(...)` → cover POST → video POST → phir `facebook_riddlespixo(...)` → cover → video.

---

## 7. Web endpoints (curl ke liye)

Key teen tarah se bhej sakte ho: `Authorization: Bearer <KEY>`, `X-API-Key: <KEY>`, ya `?key=<KEY>`. Ya address mein: `<server>/<KEY>/mcp`.

| Method | Path | Key? | Body | Jawab |
|---|---|---|---|---|
| GET | `/health` | ❌ | – | jaag raha hai? kaunse accounts set hain (tokens nahi) |
| POST | `/voice` | ✅ | JSON `{"text", "speaker", "pace"}` | WAV |
| POST | `/upload?title=&description=&tags=a,b&privacy=&category=&account=&cover=` | ✅ | MP4 | YouTube link |
| POST | `/social/<instagram\|facebook>/<naam>?title=&description=&hashtags=a,b&video_type=&cover=` | ✅ | MP4 | post link |
| POST | `/cover` | ✅ | JPG | `{"cover_id"}` (1 ghanta) → `&cover=<id>` mein do |
| GET | `/channels` | ✅ | – | YouTube channels |
| GET | `/social` | ✅ | – | Instagram/Facebook accounts |
| * | `/mcp` | ✅ | MCP | AI connector |
| POST | `/u/<token>` | ❌ (link khud chaabi) | MP4 | upload result |
| POST | `/u/<token>/cover` | ❌ | JPG | cover is link ke liye |
| GET | `/v/<token>.wav`, `/c/<token>.jpg` | ❌ | – | aawaz / cover file (1 ghanta) |

**Example (Render):**
```bash
curl -X POST -H "Authorization: Bearer <KEY>" --data-binary @video.mp4 "https://youtube-mcp-5wk1.onrender.com/social/instagram/riddlespixo?title=Paheli&description=Jawab%20do&hashtags=paheli,riddle"
```

---

## 8. PC commands

| Command | Kaam |
|---|---|
| `python render_client.py social` | Instagram/Facebook accounts check |
| `python render_client.py channels` | YouTube channels check |
| `python render_client.py social instagram riddlespixo video.mp4 insta.json` | Instagram post |
| `python render_client.py social facebook riddlespixo video.mp4 insta.json` | Facebook post |
| `python render_client.py upload video.mp4 info.json` | YouTube upload |
| `python render_client.py voice "नमस्ते" out.wav male` | aawaz |
| `python youtube_mcp.py auth <channel>` | YouTube login / naya token |
| `python instagram_upload.py check` | `instagram.json` ke tokens check (bina server) |
| `python instagram_upload.py upload riddlespixo video.mp4 "caption"` | seedha Instagram (bina server) |

**`insta.json`** (Instagram/Facebook):
```json
{"title": "Aaj ki paheli!", "description": "Jawab comment karo", "hashtags": ["paheli", "riddle", "hindi"], "video_type": "auto", "cover": "cover.jpg"}
```
**`info.json`** (YouTube):
```json
{"title": "Aaj ki paheli #shorts", "description": "...", "tags": ["paheli", "shorts"], "privacy": "private", "category": "24", "account": "riddlespixo", "cover": "cover.jpg"}
```
- `"account": "all"` = har channel par; `"accounts": ["riddlespixo", "pixelkatha3d"]` = chune hue channels par.
- Category: 22 People & Blogs, 24 Entertainment, 27 Education, 23 Comedy.

**Kaunsa server?** Default Render. Cloud Run ke liye pehle:
```bash
set YT_SERVER=https://autimate-mcp-559325411060.asia-south1.run.app
```
(PowerShell: `$env:YT_SERVER="https://autimate-mcp-559325411060.asia-south1.run.app"`)

---

## 9. Accounts jodna / hatana

### Jodna
Token kaise lena hai, woh [README → Kahani 3](README.md#-kahani-3-naya-account-jodna) mein hai. Phir:

| Platform | Dabba | Naya tool |
|---|---|---|
| Instagram | `INSTAGRAM_ACCOUNT_<NAAM>` | `instagram_<naam>` |
| Facebook | `FACEBOOK_PAGE_<NAAM>` | `facebook_<naam>` |
| YouTube | `YOUTUBE_TOKEN_<NAAM>` | `upload_link(account="<naam>")` |

**Dono gharon mein daalo**: Render (Environment) **aur** Cloud Run:
```bash
gcloud run services update autimate-mcp --region asia-south1 --update-env-vars "^@^INSTAGRAM_ACCOUNT_NAYA={\"user_id\": \"1784...\", \"access_token\": \"EAA...\"}"
```
(`^@^` gcloud ko batata hai ki value mein comma ho sakta hai. JSON ke liye Cloud Console → **Edit & deploy new revision → Variables** zyada aasaan hai.)

Ek hi naam teeno platforms par rakho (jaise `riddlespixo`), taaki samajhna aasaan ho.

### Hatana
1. Render → Environment → us dabbe ka 🗑️ → Save.
2. Cloud Run:
   ```bash
   gcloud run services update autimate-mcp --region asia-south1 --remove-env-vars INSTAGRAM_ACCOUNT_NAAM
   ```
3. Token ko jad se band karne ke liye: Meta app mein account **Remove**, ya Google → [myaccount.google.com/permissions](https://myaccount.google.com/permissions) → Remove access.

---

## 10. Keys / tokens badalna
Step-by-step: [README → Kahani 5](README.md#-kahani-5-chaabi-api-key--token-badalna).

Yaad rakho: **ek key, kai jagah.**

| Key | Jagah |
|---|---|
| Server API key | Render `API_KEY`, Cloud Run `API_KEY`, `apikey.txt`, `~\.youtube-mcp\api_key.txt`, `connector_url.txt`, har AI connector |
| Instagram token | Render + Cloud Run `INSTAGRAM_ACCOUNT_*`, `instagram.json`, `instagram.env` |
| Facebook Page token | Render + Cloud Run `FACEBOOK_PAGE_*`, `facebook.json`, `instagram.env` |
| YouTube token | Render + Cloud Run `YOUTUBE_TOKEN_*`, `tokens\<naam>.json`, `youtube.env` |
| Sarvam key | Render + Cloud Run `SARVAM_API_KEY`, `sarvam_key.txt` |

---

## 11. Code badalna (developer guide)

### 11.1 PC par server chalana (test ke liye)
PowerShell:
```powershell
$env:API_KEY="test123"; $env:PORT="8099"; python youtube_mcp.py http
```
YouTube tokens `~\.youtube-mcp\tokens\` se khud milte hain. Instagram/Facebook ke liye pehle unke dabbe `$env:INSTAGRAM_ACCOUNT_RIDDLESPIXO='{"user_id": "...", "access_token": "..."}'` set karo.

Doosre terminal mein:
```bash
curl http://127.0.0.1:8099/health
```
```bash
curl -H "Authorization: Bearer test123" http://127.0.0.1:8099/social
```
MCP tools ki list:
```bash
curl -X POST http://127.0.0.1:8099/mcp -H "Authorization: Bearer test123" -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}"
```
Cloud Run jaisa (HTTP/2) chalana ho to `$env:HTTP2="1"` bhi set karo.

### 11.2 Naya MCP tool jodna (example)
`youtube_mcp.py` mein, baaki tools ke paas:
```python
@mcp.tool()
def say_hello(name: str) -> dict:
    """Kisi ko hello bolo. name: jiska naam."""      # yeh line AI padhta hai, saaf likho
    return {"ok": True, "message": f"Hello {name}!"}
```
- `"""..."""` hi AI ko batata hai ki tool kab aur kaise chalana hai.
- Parameters ke type (`str`, `int`, `list[str]`) zaroor likho.
- Hamesha `{"ok": True/False, ...}` lautao, aur error ho to `{"ok": False, "error": "..."}`.

### 11.3 Naya platform jodna (jaise Threads / LinkedIn)
1. `social.py` mein `PREFIX` mein jodo: `"threads": "THREADS_ACCOUNT_"`.
2. `threads_upload(name, path, title, description, hashtags, video_type="auto", cover=None, cover_url="")` likho.
   `{"ok": True, "platform": "threads", "account": name, "url": ...}` lautao.
3. `UPLOADERS` mein jodo: `"threads": threads_upload`.
4. `check()` mein us platform ka token check jodo.
5. `youtube_mcp.py` mein `for _platform in ("instagram", "facebook")` (do jagah) aur `social_accounts()` mein `"threads"` jodo.
   `social_tool()` ka `where` text bhi.
6. Dabba `THREADS_ACCOUNT_<NAAM>` → tool `threads_<naam>` apne aap.

### 11.4 Check aur deploy
```bash
python -m py_compile youtube_mcp.py social.py sarvam_voice.py render_client.py
```
```bash
git status
```
(dekho `apikey.txt`, `*.json`, `*.env` list mein **na** hon)
```bash
git add -A
```
```bash
git commit -m "kya badla"
```
```bash
git push origin main
```
Phir:
- 🟣 Render: dashboard → Events mein "Deploy live" (~2-4 min) → `/health`.
- 🔵 Cloud Run: Cloud Build → History mein ✅ (~1-2 min) → `python render_client.py social` (YT_SERVER set karke).
- Build ❌ ho to Cloud Build → us build → **Build log** padho.

### 11.5 Code ke niyam (taaki aage na toote)
- Secrets **kabhi** code mein nahi, hamesha dabbe (env vars) mein.
- Naya package → `requirements.txt` mein jodo (dono gharon ko chahiye).
- Nayi Python file server ke liye → `Dockerfile` ki `COPY` line mein bhi jodo.
- Meta ka URL likhte waqt `API_VERSION` use karo, version hard-code mat karo.
- Lamba kaam (upload) → `asyncio.to_thread(...)` mein, taaki server na ruke.

---

## 12. Limits (seemayen)

| Cheez | Seema |
|---|---|
| Instagram Reel | 3 s – 15 min, MP4 (H.264 + AAC), 9:16 best, max ~300 MB |
| Instagram caption | 2200 characters, 30 hashtags |
| Instagram posts | Meta ki daily publishing limit per account (docs: ~100 / 24 ghante). Error aaye to kal |
| Facebook Reel (short) | 3 – 90 s |
| Facebook video (long) | max 1 GB / 20 min (is server ke tarike se) |
| YouTube title | 100 characters (server khud kaat deta hai) |
| YouTube daily | channel ki limit (`uploadLimitExceeded`) |
| YouTube custom thumbnail | channel phone-verified hona chahiye |
| Cover (thumbnail) | JPG only, < 8 MB, 9:16 (1080×1920) |
| One-time link / voice / cover | 1 ghanta |
| Server memory (voices/covers) | 120 MB har store, purane apne aap hat jaate hain |
| Cloud Run timeout | 60 min / request |

---

## 13. Security (suraksha)

- 🔑 **API key** = poori taakat. Jiske paas key, woh teeno channels par post kar sakta hai. Leak ho → turant badlo (section 10).
- Connector address `.../<KEY>/mcp` mein key hai. Ise share mat karo.
- One-time links random hote hain aur 1 ghante / 1 baar chalte hain.
- `/health` sirf account ke **naam** dikhata hai, tokens nahi.
- YouTube token sirf **upload + readonly** (delete/edit nahi kar sakta).
- Videos server par nahi rukti. Upload ke turant baad delete hoti hain.
- Cloud Run **private** hai. Google login ke bina 403 aata hai.
- Cloud Run / Render mein tokens env vars mein hain. Project / dashboard ka access sirf bharose ke logon ko do.
- `.gitignore` + `.dockerignore` secrets ko GitHub aur image se bahar rakhte hain. `git status` hamesha dekho.

---

## 14. Problems aur hal

| Dikkat | Kyun | Hal |
|---|---|---|
| `wrong or missing API key` (401) | key galat / nahi bheji | `apikey.txt` se dobara copy karo |
| Cloud Run `403` | Google login nahi | `gcloud auth login` (sahi account), ya Render use karo |
| `invalid_grant: Token has been expired or revoked` | YouTube token expire (Testing mode = 7 din) | `python youtube_mcp.py auth <naam>` → dabba update |
| `Error validating access token` / `Session has expired` | Meta token band | naya token → dabba update |
| `Instagram rejected the video` | format galat | MP4, H.264 + AAC, 9:16, 3 s–15 min |
| `ProcessingFailedError` | Meta ki taraf se thodi der ki gadbad | server 3 baar try karta hai. Phir bhi aaye to 5 min baad dobara |
| `uploadLimitExceeded` | YouTube daily limit | 24 ghante baad |
| `no video received` (400) | `curl` mein file path galat | `@` ke baad sahi path |
| `cover must be a JPG …` | PNG ya bada image | JPG mein badlo, < 8 MB |
| `"cover": "not set: the server is private…"` | Cloud Run private | Instagram cover ke liye Render use karo |
| `"cover": "not set: …"` (YouTube) | channel verified nahi | YouTube Studio → phone verify |
| `link expired or already used` | 1 ghanta / 1 baar | tool dobara chalao |
| Render pe timeout / der | server so raha tha | 1 min ruko, dobara |
| Naya account ka tool nahi dikh raha | restart nahi hua / naam galat | dabba ka naam `INSTAGRAM_ACCOUNT_` se shuru, CAPITAL; restart |
| `must be JSON like {...}` | dabbe ki value galat | `{"user_id": "...", "access_token": "..."}` exact |
| Cloud Build ❌ | Dockerfile / requirements gadbad | Cloud Build → Build log |
| `x-ad-api-version-warning … deprecated` | Meta version purana | `META_API_VERSION` badhao |

**Jaldi jaanch (sab theek hai?):**
```bash
python render_client.py social
```
```bash
python render_client.py channels
```

---

## 15. Maintenance calendar

| Kab | Kya | Kyun |
|---|---|---|
| **Har 7 din** (jab tak Google app "Testing" mein hai) | YouTube tokens renew (`auth`) | Testing mode tokens 7 din mein band |
| Har mahine | `social` + `channels` check | koi token chupchaap band na ho |
| Har ~60 din | Instagram token check, zarurat ho to naya | user tokens kabhi-kabhi expire hote hain |
| Kabhi nahi (aam taur par) | Facebook Page token | long-lived user token se bane Page tokens expire nahi hote |
| Har saal | `META_API_VERSION` dekho | Meta ~2 saal mein purane versions band karta hai |
| Kuch mahine mein / shak ho | server API key badlo | suraksha |

**Hamesha ke liye YouTube fix:** Google Auth Platform → **Branding** mein *Application home page* + *Privacy policy link* (aapke domain par, jaise GitHub Pages) → **Audience → Publish app** ("In production"). Uske baad tokens har hafte expire nahi honge.
