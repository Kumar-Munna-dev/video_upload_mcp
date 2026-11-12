# YouTube + Voice server

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

To add it on claude.ai, go to Settings → Connectors → Add custom connector and use the URL
`https://youtube-mcp-5wk1.onrender.com/mcp?key=<API_KEY>`.
All secrets live on Render. The PC only needs the API key.

## Files
- `youtube_mcp.py`: the server (YouTube upload, MCP, web endpoints)
- `sarvam_voice.py`: Sarvam AI text-to-speech (used by the server)
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
The API key goes in `apikey.txt` next to `render_client.py`.

## Render setup (once)
1. New → Blueprint → this repo (reads `render.yaml`).
2. Set the environment variables:
   - `API_KEY`: any long password
   - `YOUTUBE_TOKEN_MAIN`: the whole `main.json` text
   - `SARVAM_API_KEY`: your Sarvam key
3. Get the YouTube token on your PC once: `python youtube_mcp.py auth main`. This needs `~/.youtube-mcp/client_secret.json`, the Google OAuth "Desktop app" JSON.

The free plan sleeps after 15 minutes idle; the first request then takes ~50 s.
If the Google consent screen is in "Testing" mode, the token expires every 7 days. Publish it ("In production") to stop that.
