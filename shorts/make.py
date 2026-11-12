"""Make a Hindi YouTube Short from this repo. Works on a PC and in a cloud agent.

  python shorts/make.py new <name>              copy the Hindi Stick Story template  -> shorts/work/<name>
  python shorts/make.py auto <project>          Sarvam voice + word timing + check + sound + QA sheet (review/all.jpg)
  python shorts/make.py frames <project> 4.2,9  full-size frames to look at (review/f)
  python shorts/make.py render <project>        renders/<name>.mp4
  python shorts/make.py upload <project> [--yes]   YouTube upload from <project>/upload.json (without --yes: dry run)

Needs: Node 22+, Chrome/Chromium (or CHROME=path), ffmpeg, Python with numpy + scipy + the repo requirements.
Secrets come from env vars: SARVAM_API_KEY, YOUTUBE_TOKEN_MAIN (cloud) or ~/.youtube-mcp files (PC).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # shorts/
REPO = HERE.parent
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
_cloud_env = HERE / ".cloud_env"                  # written by setup_cloud.sh: export CHROME='...'
if "CHROME" not in ENV and _cloud_env.exists():
    ENV["CHROME"] = _cloud_env.read_text().split("=", 1)[1].strip().strip("'\"")
PY = sys.executable
sys.stdout.reconfigure(encoding="utf-8")


def run(cmd, cwd=None):
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    code = subprocess.run([str(c) for c in cmd], cwd=cwd, env=ENV).returncode
    if code:
        sys.exit(f"STOPPED: step failed (exit {code}). Fix it and run the same command again.")


def project(p):
    path = Path(p).resolve()
    if not (path / "script.json").exists():
        sys.exit(f"Not a video project (no script.json): {path}")
    return path


def new(name):
    dst = HERE / "work" / name
    if dst.exists():
        sys.exit(f"{dst} already exists: pick another name")
    shutil.copytree(HERE / "template", dst)
    for d in ("renders", "review"):
        (dst / d).mkdir(exist_ok=True)
    (dst / "upload.json").write_text(json.dumps({"title": "", "description": "", "tags": [], "privacy": "private"},
                                                ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PROJECT: {dst}\nThe template holds a finished example (3 switches riddle): rewrite script.json + src/shots.js.\n"
          f"Rules: {HERE / 'GUIDE.md'} and {HERE / 'STYLE.md'}")


def auto(p):
    proj = project(p)
    print("\n== voice (Sarvam AI) + word timing ==")
    run([PY, HERE / "voice_sarvam.py", proj])
    run([PY, proj / "tools/hi/words.py", proj])
    print("\n== check, sound, QA sheet ==")
    run(["node", "tools/capture.mjs", "check"], cwd=proj)
    run(["node", "tools/capture.mjs", "cues"], cwd=proj)
    run([PY, "tools/mix.py", "."], cwd=proj)
    run(["node", "tools/capture.mjs", "sheet", "review/all.jpg", "0.5", "10"], cwd=proj)
    print(f"BUILD OK. Now LOOK at {proj / 'review/all.jpg'} before rendering.")


def frames(p, times):
    proj = project(p)
    run(["node", "tools/capture.mjs", "frames", "review/f", times], cwd=proj)


def render(p):
    proj = project(p)
    run(["node", "tools/capture.mjs", "video", f"renders/{proj.name}.mp4"], cwd=proj)
    mb = (proj / f"renders/{proj.name}.mp4").stat().st_size / 1e6
    print(f"RENDER OK: {proj / f'renders/{proj.name}.mp4'} ({mb:.1f} MB)")


def upload(p, yes):
    proj = project(p)
    video, info = proj / f"renders/{proj.name}.mp4", json.loads((proj / "upload.json").read_text(encoding="utf-8"))
    if not video.exists():
        sys.exit(f"No video yet: run  python shorts/make.py render {proj}")
    if not info.get("title"):
        sys.exit(f"Fill in title, description, tags, privacy in {proj / 'upload.json'}")
    print(f"video: {video}\ntitle: {info['title']}\nprivacy: {info.get('privacy', 'private')}")
    if not yes:
        print("DRY RUN: nothing uploaded. Add --yes to upload.")
        return
    sys.path.insert(0, str(REPO))
    import youtube_mcp  # noqa: E402
    r = youtube_mcp.upload_video(video=str(video), title=info["title"], description=info.get("description", ""),
                                 tags=info.get("tags", []), privacy=info.get("privacy", "private"))
    (proj / "renders/upload_result.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False))
    if not r.get("ok"):
        sys.exit("UPLOAD FAILED")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "new": new(a[1])
    elif len(a) == 2 and a[0] == "auto": auto(a[1])
    elif len(a) == 3 and a[0] == "frames": frames(a[1], a[2])
    elif len(a) == 2 and a[0] == "render": render(a[1])
    elif len(a) >= 2 and a[0] == "upload": upload(a[1], "--yes" in a)
    else: print(__doc__); sys.exit(0 if not a else 2)
