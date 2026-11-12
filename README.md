# Simple YouTube Upload MCP Server

AI (Claude) is server se YouTube par video upload kar sakta hai.

**Tools:** `upload_video`, `list_accounts`, `channel_info`

## 1. Install

```bash
pip install -r requirements.txt
```

## 2. Google OAuth client banao (ek baar)

1. https://console.cloud.google.com → project select/create karo
2. **APIs & Services → Library** → "YouTube Data API v3" → **Enable**
3. **OAuth consent screen** → External → app name + email → **Test users** me apna Gmail add karo
4. **Credentials → Create Credentials → OAuth client ID → Desktop app** → **Download JSON**
5. File ko yahan rakho: `C:\Users\<aap>\.youtube-mcp\client_secret.json`

## 3. Login karo

```bash
python youtube_mcp.py auth main
```

Browser khulega → account chuno → Allow. Dusra account bhi chahiye toh: `python youtube_mcp.py auth second`

## 4. Claude se jodo

**Claude Code:**

```bash
claude mcp add youtube -- python D:\PYTHON\youtube-mcp\youtube_mcp.py
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "youtube": {
      "command": "python",
      "args": ["D:\\PYTHON\\youtube-mcp\\youtube_mcp.py"]
    }
  }
}
```

Phir Claude se bolo: *"D:\videos\clip.mp4 ko YouTube pe upload karo, title 'My Video #shorts', public"*

## Dhyan rakho

- Default privacy **private** hai — public chahiye toh bolna padega.
- Google Cloud project verify (audit) nahi hai toh YouTube video ko **private** hi rakhega, chahe public bhejo.
- Consent screen "Testing" mode me ho toh login har 7 din me dobara karna padega (`auth` dobara chalao).
- `client_secret.json` aur `tokens/` folder kisi ko share mat karo.
- Purana bada version backup me hai: `youtube_mcp_full_backup.py`

---

# Google Cloud par host karo (Cloud Run)

Server internet par chalega, PC band ho tab bhi. Address hoga: `https://<service>.run.app/mcp`

> Cloud par aapke PC ki files nahi hoti, isliye `upload_video` ko video ka **download link** do (https://...mp4), local path nahi.

## 1. Tools install karo (ek baar)

- Google Cloud CLI: https://cloud.google.com/sdk/docs/install
- Phir login:

```bash
gcloud auth login
```

```bash
gcloud config set project YOUR_PROJECT_ID
```

## 2. Pehle PC par login karke token banao

```bash
python youtube_mcp.py auth main
```

Ye `C:\Users\<aap>\.youtube-mcp\tokens\main.json` banata hai. Yahi token cloud ko denge.

## 3. Token aur password ko Secret Manager me rakho

```bash
gcloud services enable run.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com
```

```bash
gcloud secrets create youtube-token-main --data-file=%USERPROFILE%\.youtube-mcp\tokens\main.json
```

API key = koi bhi lamba password (khud banao). Use file me likho (`apikey.txt`, sirf password, koi newline nahi):

```bash
gcloud secrets create mcp-api-key --data-file=apikey.txt
```

Cloud Run ko secrets padhne ki permission do (`PROJECT_NUMBER` console ke home page par milega):

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member=serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor
```

## 4. Deploy (isi folder me chalao)

```bash
gcloud run deploy youtube-mcp --source . --region asia-south1 --allow-unauthenticated --memory 1Gi --timeout 3600 --set-secrets YOUTUBE_TOKEN_MAIN=youtube-token-main:latest,API_KEY=mcp-api-key:latest
```

Last me URL milega, jaise `https://youtube-mcp-xxxx.a.run.app`.
(`--allow-unauthenticated` ka matlab Google login nahi chahiye — security hamari API key karti hai.)

## 5. Claude se jodo

**Claude Code:**

```bash
claude mcp add --transport http youtube https://youtube-mcp-xxxx.a.run.app/mcp --header "Authorization: Bearer YOUR_API_KEY"
```

**Claude.ai / Desktop (Custom connector)** — header nahi de sakte, isliye key URL me daalo:

```
https://youtube-mcp-xxxx.a.run.app/mcp?key=YOUR_API_KEY
```

## Dusra account cloud par

```bash
python youtube_mcp.py auth second
```

```bash
gcloud secrets create youtube-token-second --data-file=%USERPROFILE%\.youtube-mcp\tokens\second.json
```

Phir deploy command me `,YOUTUBE_TOKEN_SECOND=youtube-token-second:latest` jodo.

## Code badla? Dobara deploy

Wahi step 4 wala command dobara chalao.

## Dhyan rakho (cloud)

- Consent screen "Testing" mode me token 7 din me expire hota hai → `auth` dobara chalao, phir: `gcloud secrets versions add youtube-token-main --data-file=...main.json` aur dobara deploy.
  Hamesha ke liye: OAuth consent screen ko **"In production"** par publish karo.
- Cloud Run me free tier hai; koi request na ho toh server khud band (0 cost) ho jata hai.
- API key kisi ko mat do — jiske paas key hai woh aapke channel par upload kar sakta hai.
