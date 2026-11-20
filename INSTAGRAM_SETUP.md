# Instagram upload – beginner setup

`instagram_upload.py` aapke PC se seedha Instagram par Reel post karta hai (Instagram ka official API).
Kuch install nahi karna. Bas ek baar token lena hai.

## 1. Instagram account ko Professional banao (2 min)
Instagram app → Settings → **Account type and tools** → **Switch to professional account** → *Creator* ya *Business*.
(Normal/personal account par API kaam nahi karta.)

## 2. Meta developer app banao (5 min, ek hi baar)
1. https://developers.facebook.com par login karo → **My Apps → Create App**.
2. Use case mein **"Manage messaging & content on Instagram"** chuno → app ka naam do → Create.
3. App dashboard mein **Instagram → API setup with Instagram login** kholo.
4. **Generate access tokens** section mein **Add account** dabao aur apna Instagram account login karo.
5. Account ke saamne **Generate token** dabao → lamba token copy karo (`IGAA...` se shuru hota hai).
   Wahin aapka **Instagram user ID** bhi dikhta hai (number, jaise `1784...`).
6. Permissions mein `instagram_business_basic` aur `instagram_business_content_publish` on hone chahiye.

> App "Development" mode mein bhi chalegi – sirf apne khud ke account par post karna hai, to app review ki zaroorat nahi.

## 3. `instagram.json` banao
Is folder (`D:\PYTHON\youtube-mcp`) mein `instagram.json` naam ki file banao:

```json
{
  "riddlespixo":   {"access_token": "IGAA...", "user_id": "17841413164146859"},
  "pixelkatha3d":  {"access_token": "IGAA...", "user_id": "17841464893308549"},
  "scielifeindia": {"access_token": "IGAA...", "user_id": "17841428387764461"}
}
```
(Naye Meta apps mein yeh "Instagram API → API setup with Unified login → 2. Generate access tokens" mein milta hai.
Har account ke saamne **Generate token** dabao, us account se login karo, token copy karke yahan daalo.)

Yeh file `.gitignore` mein hai (`*.json`), to galti se GitHub par nahi jaayegi. Token kisi ko mat dikhana.

## 4. Chalao

Token check karo:
```bash
python instagram_upload.py check
```

Video upload karo:
```bash
python instagram_upload.py upload riddlespixo shorts/meri-video.mp4 "Aaj ki paheli! #riddle #reels"
```

Output kuch aisa aayega:
```
Video: meri-video.mp4 (8.4 MB)
1/4  Instagram par jagah bana rahe hain...
2/4  Video bhej rahe hain...
3/4  Instagram video process kar raha hai...
4/4  Publish kar rahe hain...
Ho gaya! Reel live hai: https://www.instagram.com/reel/...
```

## Video kaisi honi chahiye
- MP4, H.264 video + AAC audio (aapke YouTube Shorts already aise hi hain)
- 9:16 vertical (1080×1920 best)
- 3 second se 15 minute, 300 MB se kam

## Problem aaye to
| Error | Matlab / kya karein |
|---|---|
| `instagram.json nahi mili` | Step 3 dobara karo, file isi folder mein honi chahiye |
| `Instagram error 400 ... access token` / `Session has expired` | Token purana ho gaya (~60 din chalta hai). Step 2.5 se naya token lo |
| `Instagram error 403` / permission | App mein `instagram_business_content_publish` permission on karo |
| `Instagram ne video reject kar di` | Video format galat hai – upar wali list dekho |
| `Application request limit reached` | Ek account par 24 ghante mein max ~50 posts. Kal try karo |

Agar aapka token `EAA...` se shuru hota hai (Facebook Login wala), to `instagram.json` mein yeh line bhi jodo:
`"host": "graph.facebook.com"`
