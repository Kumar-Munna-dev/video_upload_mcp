#!/bin/bash
# Setup for a fresh Linux cloud machine (Claude cloud agent). Safe to run again.
#   bash shorts/setup_cloud.sh      then:  source shorts/.cloud_env
set -e
cd "$(dirname "$0")/.."
have() { command -v "$1" >/dev/null 2>&1; }
SUDO=""; [ "$(id -u)" != 0 ] && have sudo && SUDO="sudo"

echo "== ffmpeg =="
have ffmpeg || { $SUDO apt-get update -qq && $SUDO apt-get install -y -qq ffmpeg; }
ffmpeg -version | head -1

echo "== Node 22+ =="
NODE_MAJOR=$(node -v 2>/dev/null | sed 's/v\([0-9]*\).*/\1/' || echo 0)
if [ "${NODE_MAJOR:-0}" -lt 22 ]; then npm install -g n >/dev/null 2>&1 && $SUDO n 22 >/dev/null && hash -r; fi
node -v

echo "== Python packages =="
# --ignore-installed: cloud images have Debian-installed packages (e.g. PyJWT) that pip can't uninstall
python3 -m pip install -q numpy scipy -r requirements.txt 2>/dev/null \
  || python3 -m pip install -q --break-system-packages --ignore-installed numpy scipy -r requirements.txt

echo "== Chrome (headless) =="
find_playwright_chrome() { ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome ~/.cache/ms-playwright/chromium-*/chrome-linux/chrome 2>/dev/null | tail -1; }
CHROME=$(find_playwright_chrome)                       # Claude cloud images ship Chromium in /opt/pw-browsers
if [ -z "$CHROME" ]; then
  for c in google-chrome google-chrome-stable chromium chromium-browser; do
    p=$(command -v $c || true); [ -n "$p" ] && "$p" --version >/dev/null 2>&1 && CHROME="$p" && break
  done
fi
if [ -z "$CHROME" ]; then
  npx -y playwright@1.49.1 install --with-deps chromium >/dev/null 2>&1 || npx -y playwright@1.49.1 install chromium
  CHROME=$(find_playwright_chrome)
fi
[ -n "$CHROME" ] || { echo "NO CHROME FOUND"; exit 1; }
echo "export CHROME='$CHROME'" > shorts/.cloud_env
"$CHROME" --version || true

echo "== secrets present? (values not shown) =="
for v in SARVAM_API_KEY YOUTUBE_TOKEN_MAIN; do [ -n "${!v}" ] && echo "$v: set" || echo "$v: MISSING"; done
echo "SETUP OK  ->  source shorts/.cloud_env"
