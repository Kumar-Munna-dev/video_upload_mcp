# YouTube + Instagram + Facebook + Voice server

Videos are made **on your PC**. This small server on **Render** does only two jobs:

| job | endpoint | what it does |
|---|---|---|
| voice | `POST /voice` | Hindi voice-over with Sarvam AI (Bulbul V4 Flash) → WAV |
| upload | `POST /upload` | uploads your MP4 to YouTube, then deletes it from the server |

Claude can also use it as an MCP **connector** at `/mcp`, so **any chat** (Code tab, Cowork, claude.ai) can use it:
- `make_voice(text, speaker)` → a WAV download link (1 hour)
- `upload_link(title, description, tags, privacy)` → a one-time link; the chat sends the MP4 with
  `curl -X POST --data-binary @video.mp4 "<link>"`. The server uploads it to YouTube and deletes it.
- `upload_video(video_url, ...)`, `channel_info()`
- **Instagram / Facebook: one tool per account**, e.g. `instagram_riddlespixo(title, description, hashtags, video_type)`
  → a one-time link; send the MP4 with the same `curl` command. `social_accounts()` lists them all.
  - Instagram: every video is a Reel (short or long; long ones also show on the profile grid).
  - Facebook Page: short (≤ 90 s) → Reels section, long → normal video post. `video_type`: auto | short | long.
  - Caption = title + description + #hashtags (all three are required).
  - Cover (thumbnail): send a JPG (9:16) to `<upload_url>/cover` BEFORE the video. Works for YouTube too.

### Add an Instagram account / Facebook Page (any time)
On Render → Environment, add ONE variable, then the server restarts and the new tool appears:
- `INSTAGRAM_ACCOUNT_<NAME>` = `{"user_id": "1784...", "access_token": "EAA..."}` → tool `instagram_<name>`
- `FACEBOOK_PAGE_<NAME>` = `{"page_id": "...", "access_token": "<Page token>"}` → tool `facebook_<name>`

The Instagram user ID and token come from the Meta app: Use cases → Instagram API → API setup with Unified login →
Generate access tokens (see `INSTAGRAM_SETUP.md`).

To add it on claude.ai, go to Settings → Connectors → Add custom connector and use the URL
`https://youtube-mcp-5wk1.onrender.com/mcp?key=<API_KEY>`.
All secrets live on Render. The PC only needs the API key.

## Files
- `youtube_mcp.py`: the server (YouTube upload, MCP, web endpoints)
- `sarvam_voice.py`: Sarvam AI text-to-speech (used by the server)
- `social.py`: Instagram + Facebook uploads (used by the server)
- `instagram_upload.py`: upload straight from the PC to Instagram, without the server (uses `instagram.json`)
- `render_client.py`: used on the PC to call the server
- `render.yaml`: Render settings

## Use it from the PC
```bash
python render_client.py voice "नमस्ते दोस्तों!" hello.wav male
```
```bash
python render_client.py upload video.mp4 info.json
```
`info.json`: `{"title": "... #shorts", "description": "...", "tags": ["shorts"], "privacy": "private"}`
```bash
python render_client.py social instagram riddlespixo video.mp4 insta.json
```
`insta.json`: `{"title": "...", "description": "...", "hashtags": ["paheli", "riddle"], "video_type": "auto", "cover": "cover.jpg"}`
The API key goes in `apikey.txt` next to `render_client.py`.

## Render setup (once)
1. New → Blueprint → this repo (reads `render.yaml`).
2. Set the environment variables:
   - `API_KEY`: any long password
   - `YOUTUBE_TOKEN_MAIN`: the whole `main.json` text
   - `SARVAM_API_KEY`: your Sarvam key
3. Get the YouTube token on your PC once: `python youtube_mcp.py auth main`. This needs `~/.youtube-mcp/client_secret.json`, the Google OAuth "Desktop app" JSON.

The free plan sleeps after 15 minutes idle; the first request then takes ~50 s.
`GET /health` (no key) shows if the server is awake and which accounts are set (no tokens).

### Keeping it working in the future
- **Meta API version**: Meta retires old versions after ~2 years. The server uses `v27.0`; to move to a newer one,
  set `META_API_VERSION` (e.g. `v28.0`) on Render. No code change.
- **Token stopped working?** `social_accounts` (MCP) or `python render_client.py social` shows which one. Make a new
  token (see `INSTAGRAM_SETUP.md`) and replace that one variable on Render.
- **Moving off Render?** Set `PUBLIC_URL` to the server's public address (Instagram downloads covers from it).
If the Google consent screen is in "Testing" mode, the token expires every 7 days. Publish it ("In production") to stop that.
