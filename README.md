# 🎬 Video Upload Server: aasaan bhasha mein

Yeh ek **robot dakiya** 📮 hai.
Aap (ya koi AI) ise ek video dete ho, aur yeh use **YouTube, Instagram aur Facebook** par daal deta hai.
Yeh **Hindi aawaz** (voice-over) bhi bana deta hai.

```
  Aapka PC / AI  ──video──▶  🤖 Server  ──▶  YouTube 📺
                                       ──▶  Instagram 📸
                                       ──▶  Facebook 👍
```

Server **do ghar** mein rehta hai (dono mein same code):

| Ghar | Address | Kaun use kar sakta hai |
|---|---|---|
| 🟣 **Render** | `https://youtube-mcp-5wk1.onrender.com` | jiske paas **API key** ho (koi bhi AI) |
| 🔵 **Google Cloud Run** | `https://autimate-mcp-559325411060.asia-south1.run.app` | sirf aapka **Google login** + API key (private) |

> 📘 **Poori detail chahiye?** [GUIDE.md](GUIDE.md) padho: setup zero se, saare tools/endpoints, code badalna, limits, problems.

> 🔑 **API key = server ka darwaze ki chaabi.** Yeh [`apikey.txt`](apikey.txt) mein hai (sirf aapke PC par).
> Ise kabhi GitHub, chat ya screenshot mein mat daalna. Jiske paas chaabi, woh aapke channels par post kar sakta hai.

---

## 📚 Kahani 1: AI ko server se kaise jodein (connect)

AI ko bas **ek address** chahiye. Address mein chaabi chhupi hoti hai.

### Step 1: chaabi lo
[`apikey.txt`](apikey.txt) kholo. Usme ek hi line hai. Wahi **API_KEY** hai.

### Step 2: address banao
```
https://youtube-mcp-5wk1.onrender.com/<API_KEY>/mcp
```
`<API_KEY>` hata kar apni chaabi chipka do. Bas! 🎉

### Step 3: AI mein daalo
- **claude.ai** → Settings → Connectors → **Add custom connector** → upar wala address paste karo.
- **Cursor / VS Code / koi bhi `mcp.json` wala AI:**
  ```json
  {
    "mcpServers": {
      "video-uploader": {
        "url": "https://youtube-mcp-5wk1.onrender.com/mcp",
        "headers": { "Authorization": "Bearer <API_KEY>" }
      }
    }
  }
  ```

### Step 4: check karo
AI se bolo: **"social_accounts chalao"**. Saare accounts ✅ dikhne chahiye.

> 😴 Render ka free server so jaata hai. Pehli baar ~1 minute lagta hai. "Timeout" aaye to dobara try karo.
> 🔵 Google Cloud Run **private** hai, isliye claude.ai jaise AI usse nahi jud sakte. Unke liye Render use karo.

### AI ko kaunse khilone (tools) milte hain?

| Tool | Kya karta hai |
|---|---|
| `instagram_riddlespixo`, `instagram_pixelkatha3d`, `instagram_scielifeindia` | us Instagram par Reel |
| `facebook_riddlespixo`, `facebook_pixelkatha3d`, `facebook_scielifeindia` | us Facebook Page par video |
| `upload_link` | YouTube par video (`account` mein channel ka naam) |
| `make_voice` | Hindi aawaz (WAV) |
| `social_accounts`, `channel_info` | kaun-kaun se accounts jude hain |

### Video bhejne ke 3 kadam (AI khud karta hai)
1. Tool chalao, jaise `instagram_riddlespixo(title, description, hashtags)`. Ek **ek-baar wala link** milta hai.
2. 🖼️ (Chaho to) thumbnail pehle bhejo:
   `curl -X POST --data-binary @cover.jpg -H "Content-Type: image/jpeg" "<link>/cover"`
3. 🎬 Video bhejo:
   `curl -X POST --data-binary @video.mp4 -H "Content-Type: video/mp4" "<link>"`
   Jawab mein post ka link aata hai. ✅

Yaad rakho:
- **Title, description, hashtags**: teeno zaroori (Instagram/Facebook).
- **Short** = 90 second tak → Facebook **Reels**. **Long** = usse lamba → Facebook **video post**.
  Instagram par sab **Reel** banta hai.
- Instagram/Facebook post **turant public** hoti hai. YouTube default **private**.

---

## 💻 Kahani 2: PC se seedha chalana

```bash
python render_client.py social
```
(sab accounts check)

```bash
python render_client.py social instagram riddlespixo video.mp4 insta.json
```
`insta.json`:
```json
{"title": "Aaj ki paheli!", "description": "Jawab comment karo", "hashtags": ["paheli", "riddle"], "cover": "cover.jpg"}
```

```bash
python render_client.py upload video.mp4 info.json
```
`info.json` (YouTube): `{"title": "...", "description": "...", "tags": ["shorts"], "privacy": "private", "account": "riddlespixo"}`

Google Cloud Run use karna ho to pehle (Windows):
```bash
set YT_SERVER=https://autimate-mcp-559325411060.asia-south1.run.app
```
`render_client.py` aapka `gcloud` login khud use kar leta hai.

---

## ➕ Kahani 3: naya account jodna

Har account = **ek dabba (environment variable)**. Naya dabba rakho → naya tool apne aap ban jaata hai. Code badalna **nahi** padta. 🎁

Dabba kahan rakhna hai:
- 🟣 **Render:** dashboard → youtube-mcp → **Environment** → Add → Save (server khud restart hota hai)
- 🔵 **Cloud Run:**
  ```bash
  gcloud run services update autimate-mcp --region asia-south1 --update-env-vars "NAAM=value"
  ```
  (JSON value ho to Cloud Console → Cloud Run → autimate-mcp → **Edit & deploy new revision** → Variables mein daalna aasaan hai)

### 📸 Naya Instagram account
1. Instagram app → account ko **Professional** (Creator/Business) banao.
2. [developers.facebook.com](https://developers.facebook.com) → app **automate-mcp** → Use cases → **Instagram API** →
   **API setup with Unified login** → **2. Generate access tokens** → **Add account** → naye account se login.
3. Account ke saamne **Generate token** → token copy. Wahin **user ID** (1784… wala number) bhi hai.
4. Naya dabba:
   ```
   INSTAGRAM_ACCOUNT_NAYANAAM = {"user_id": "1784...", "access_token": "EAA..."}
   ```
5. Restart ke baad tool **`instagram_nayanaam`** aa jaata hai. ✅

### 👍 Naya Facebook Page
1. [Graph API Explorer](https://developers.facebook.com/tools/explorer/) → app **automate-mcp** →
   permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `business_management` →
   **Generate Access Token** → naya Page tick karo.
2. ⓘ → **Open in Access Token Tool** → **Extend Access Token** (lamba token).
3. Graph API Explorer mein (lamba token ke saath) chalao: `me/accounts?fields=id,name,access_token`.
   Naye Page ka **id** aur **access_token** (Page token, kabhi expire nahi hota) lo.
4. Naya dabba:
   ```
   FACEBOOK_PAGE_NAYANAAM = {"page_id": "123...", "access_token": "EAA..."}
   ```
5. Tool **`facebook_nayanaam`** aa jaata hai. ✅

### 📺 Naya YouTube channel
1. Google Cloud → project **My First Project** → Google Auth Platform → **Audience** → **Test users** mein
   us channel ka Gmail jodo (jab tak app "Testing" mein hai).
2. PC par:
   ```bash
   python youtube_mcp.py auth nayanaam
   ```
   Browser khulega → sahi Google account → **sahi channel** chuno → Allow.
3. File bani: `C:\Users\<aap>\.youtube-mcp\tokens\nayanaam.json`. Uska **poora text** (`{` se `}` tak) copy.
4. Naya dabba:
   ```
   YOUTUBE_TOKEN_NAYANAAM = <poora json text>
   ```
5. Ab `upload_link(..., account="nayanaam")` chalega. ✅

> ⏰ Google app abhi **"Testing"** mode mein hai, isliye YouTube token **har 7 din** mein expire hota hai.
> Tab step 2 se 4 dobara karo. Hamesha ke liye fix: app ko "In production" karna (iske liye ek privacy policy page chahiye).

### 🔁 Token kharab ho gaya?
`social_accounts` / `channel_info` mein ❌ dikhega. Bas wahi account ka naya token lo (upar wale steps) aur **usi dabbe** ki value badal do.

---

## 🛠️ Kahani 4: code badalna (modify)

### Kaunsi file kya karti hai?

| File | Kaam |
|---|---|
| [`youtube_mcp.py`](youtube_mcp.py) | 🧠 server ka dimaag: MCP tools, web addresses, YouTube upload |
| [`social.py`](social.py) | 📸👍 Instagram + Facebook upload |
| [`sarvam_voice.py`](sarvam_voice.py) | 🗣️ Hindi aawaz (Sarvam AI) |
| [`render_client.py`](render_client.py) | 💻 PC se server ko bulana |
| [`instagram_upload.py`](instagram_upload.py) | PC se seedha Instagram (bina server ke, `instagram.json` se) |
| [`Dockerfile`](Dockerfile) | 🔵 Google Cloud Run ke liye dabba |
| [`render.yaml`](render.yaml) | 🟣 Render ki settings |
| [`requirements.txt`](requirements.txt) | zaroori Python packages |

### Badalne ke 4 kadam
1. **File kholo aur badlo.** Har function ke upar `"""..."""` mein likha hai woh kya karta hai.
2. **PC par check karo:**
   ```bash
   python -m py_compile youtube_mcp.py social.py render_client.py
   ```
   Kuch na dikhe = sab theek ✅
3. **GitHub par bhejo (push):**
   ```bash
   git add -A
   ```
   ```bash
   git commit -m "kya badla, ek line mein"
   ```
   ```bash
   git push origin main
   ```
4. **Bas!** 🎉 Render aur Google Cloud Run **dono khud** naya code utha lete hain (~2-5 minute).
   Check: `https://youtube-mcp-5wk1.onrender.com/health` kholo → `"ok": true`.

### Aam badlaav kahan karein?

| Mujhe chahiye… | Kahan badlo |
|---|---|
| Short/long ki seema (abhi 90 second) | `social.py` → `SHORT_MAX_SECONDS` |
| Max hashtags (abhi 30) | `social.py` → `HASHTAGS_MAX` |
| Tool ka description (AI ko kya samjhaye) | `youtube_mcp.py` → `social_tool()` ke andar `upload.__doc__` |
| Naya MCP tool | `youtube_mcp.py` mein naya function, upar `@mcp.tool()` likho |
| Default aawaz | `sarvam_voice.py` → `MALE`, `FEMALE` |
| Meta API version (jab Meta purana band kare) | code nahi! dabba `META_API_VERSION` = `v28.0` |

> ⚠️ **Kabhi commit mat karna:** `apikey.txt`, `*.json`, `*.env`, videos. `.gitignore` inhe pehle se rokta hai.
> Pakka karne ke liye `git status` dekho: yeh files list mein nahi aani chahiye.

---

## 🔑 Kahani 5: chaabi (API key / token) badalna

Chaabi **kab** badlein?
- 🕵️ shak ho ki kisi ne dekh li (screenshot, chat, GitHub mein chali gayi)
- ⏰ token expire ho gaya (`social_accounts` / `channel_info` mein ❌)
- 🙂 bas aise hi, har kuch mahine mein

Har chaabi ek **dabba** (environment variable) mein rehti hai. Badalna = **naya value daalna, dono gharon mein**:
- 🟣 **Render:** dashboard → youtube-mcp → **Environment** → dabbe ke saamne ✏️ edit → nayi value → **Save**
- 🔵 **Cloud Run:**
  ```bash
  gcloud run services update autimate-mcp --region asia-south1 --update-env-vars "DABBA_NAAM=nayi_value"
  ```
  JSON wali value (Instagram/Facebook/YouTube) ke liye aasaan: Cloud Console → Cloud Run → **autimate-mcp** →
  **Edit & deploy new revision** → **Variables & Secrets** → value badlo → **Deploy**.

> Purani chaabi nayi value save hote hi **turant bekaar** ho jaati hai. ✅

### 1️⃣ Apni server API key (darwaze ki chaabi)
1. Nayi lambi chaabi banao:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Yeh **4 jagah** daalo:

   | Kahan | Kaise |
   |---|---|
   | 🟣 Render | dabba `API_KEY` |
   | 🔵 Cloud Run | `gcloud run services update autimate-mcp --region asia-south1 --update-env-vars "API_KEY=<nayi>"` |
   | 💻 PC | [`apikey.txt`](apikey.txt) **aur** `C:\Users\<aap>\.youtube-mcp\api_key.txt` mein purani line hata kar nayi |
   | 🤖 Har AI connector | address `.../<nayi>/mcp` se badlo (claude.ai → Settings → Connectors → purana hatao, naya jodo). `C:\Users\<aap>\.youtube-mcp\connector_url.txt` bhi update karo |

3. Check:
   ```bash
   python render_client.py social
   ```
   Saare ✅ = ho gaya.

### 2️⃣ Instagram token
1. [developers.facebook.com](https://developers.facebook.com) → app **automate-mcp** → Use cases → **Instagram API** →
   **API setup with Unified login** → **2. Generate access tokens**.
2. Us account ke saamne **Generate token** → login → naya token copy.
   (Purana token band karna ho to wahin **Remove** karke dobara **Add account** karo.)
3. Dabba `INSTAGRAM_ACCOUNT_<NAAM>` ki value mein sirf `access_token` badlo:
   ```
   {"user_id": "1784... (wahi purana)", "access_token": "EAA... (naya)"}
   ```
4. Render + Cloud Run dono mein save → `python render_client.py social` → ✅

### 3️⃣ Facebook Page token
1. [Graph API Explorer](https://developers.facebook.com/tools/explorer/) → app **automate-mcp** → **Generate Access Token** →
   Pages tick karo → ⓘ → **Open in Access Token Tool** → **Extend Access Token**.
2. Explorer mein (lamba token ke saath) chalao: `me/accounts?fields=id,name,access_token` → us Page ka naya **access_token**.
3. Dabba `FACEBOOK_PAGE_<NAAM>`:
   ```
   {"page_id": "123... (wahi purana)", "access_token": "EAA... (naya)"}
   ```
4. Purane token band karne ka pakka tarika: Facebook → Settings → **Business integrations** → **automate-mcp** → Remove,
   phir step 1 se naya banao.
5. Dono gharon mein save → `python render_client.py social` → ✅

### 4️⃣ YouTube token
1. PC par (har channel ke liye):
   ```bash
   python youtube_mcp.py auth riddlespixo
   ```
   Browser → sahi Google account → **sahi channel** → Allow.
2. `C:\Users\<aap>\.youtube-mcp\tokens\riddlespixo.json` ka **poora text** copy.
3. Dabba `YOUTUBE_TOKEN_RIDDLESPIXO` = woh text. Dono gharon mein save.
4. Purana token band karna ho: [myaccount.google.com/permissions](https://myaccount.google.com/permissions) →
   app ka naam → **Remove access**, phir step 1.
5. Check:
   ```bash
   python render_client.py channels
   ```

### 5️⃣ Sarvam (aawaz) key
1. [dashboard.sarvam.ai](https://dashboard.sarvam.ai) → API keys → nayi key banao, purani delete karo.
2. Dabba `SARVAM_API_KEY` (dono gharon mein) + PC par `C:\Users\<aap>\.youtube-mcp\sarvam_key.txt`.
3. Check:
   ```bash
   python render_client.py voice "नमस्ते" test.wav male
   ```

> ⚠️ Nayi chaabi **kabhi** chat, GitHub, screenshot ya kisi file mein mat daalna jo commit hoti hai.
> PC ki local files (`apikey.txt`, `instagram.json`, `*.env`) `.gitignore` mein hain, GitHub par nahi jaati.

---

## 🧰 Kuch toot gaya? (help)

| Dikkat | Kya karein |
|---|---|
| `wrong or missing API key` | address/header mein chaabi galat. `apikey.txt` se dobara copy karo |
| `invalid_grant` / YouTube token expired | Kahani 3 → 📺 YouTube steps 2-4 |
| Instagram/Facebook `Session has expired` | us account ka naya token, wahi dabba badlo |
| `uploadLimitExceeded` (YouTube) | aaj ki limit khatam, 24 ghante baad |
| Server jawab nahi deta | Render so raha hai, 1 minute ruko; ya `/health` kholo |
| Cloud Run `403` | private hai: `gcloud auth login` karo, ya Render use karo |
| Instagram cover nahi laga (Cloud Run) | private server se Instagram cover nahi le sakta, Render use karo |
| `no video received` | `curl` mein `@` ke baad file ka path galat |

---

## 🔬 Technical details (badon ke liye)

- **Environment variables:** `API_KEY`, `SARVAM_API_KEY`, `YOUTUBE_TOKEN_<NAME>`, `INSTAGRAM_ACCOUNT_<NAME>`,
  `FACEBOOK_PAGE_<NAME>`, `META_API_VERSION` (default `v27.0`), `PUBLIC_URL` (Instagram covers download from it),
  `HTTP2=1` (Cloud Run: hypercorn h2c, needed for videos > 32 MB), `COVER_LINKS=off` (private server).
  A value may be wrapped in `'...'` (Render "Add from .env" keeps quotes; the server strips them).
- **Web endpoints** (API key as `Authorization: Bearer <key>`, `X-API-Key: <key>` or `?key=<key>`):
  `POST /voice`, `POST /upload`, `POST /social/<instagram|facebook>/<name>`, `POST /cover`, `GET /channels`,
  `GET /social`, `/mcp`. Without key: `GET /health`, one-time links `/u/…`, `/v/…`, `/c/…` (random, 1 hour).
- **YouTube permissions:** only `youtube.upload` + `youtube.readonly` (no delete/edit).
- **Memory:** voices/covers kept in RAM max 1 hour, max 120 MB per store. Videos are deleted right after upload.
- **Render:** Blueprint from `render.yaml`, free plan (sleeps after 15 min idle).
- **Google Cloud Run:** service `autimate-mcp`, project `project-5da1a3a3-b570-4755-8f1`, region `asia-south1`,
  Cloud Build trigger on push to `main`, HTTP/2 end-to-end, timeout 3600 s, max 1 instance (one-time links live in
  memory), 1 GiB, requires authentication.
- **Instagram setup from zero:** see [`INSTAGRAM_SETUP.md`](INSTAGRAM_SETUP.md).
