# Making a Hindi Short with this kit (for a cloud agent or a PC)

Style: **Stick Story** (black stick people with acting eyes, flat rooms, gold step cards). Full style rules: `STYLE.md`.
The template in `template/` is a finished example, the "3 स्विच, 1 बल्ब" riddle. Copy its patterns.

## Steps
1. `bash shorts/setup_cloud.sh && source shorts/.cloud_env` (cloud only, once per machine)
2. `python shorts/make.py new <name>` → `shorts/work/<name>/`
3. Write a NEW, original Hindi riddle or brain teaser in `script.json`:
   - 12-14 lines; each line is one cut (1.5-3.5 s). Everyday spoken Hindi in Devanagari, `।` or `?` at the end of
     each sentence, numbers written as spoken.
   - `caps`: 1-3 words per chunk, split with `|`, exactly ONE `*gold` word per chunk. The same word must not start two
     chunks of one line.
   - After the question line add `"gap": 5.2` for a 5-4-3-2-1 countdown, then the answer with steps.
   - Keep `"voice": "sarvam:male"` and `"pace": 1.0`. Put facts or the puzzle's origin in `"sources"`.
4. Rewrite `src/shots.js`: one shot per line, `cut(i)` for its start, `Wd('हिंदी-शब्द', i)` for moments on spoken
   words (the word must be in line i). Kit: `K.person, K.bigHead, K.livingRoom/kitchen/hallway, K.stepCard,
   K.counterPill, K.check, K.cross, K.thought` (see `src/core/kit.js`). New props go in shots.js (see switchPanel and
   bulb in the example). Night scenes: `glow: true` on people. Figures: h ≈ 840.
5. `python shorts/make.py auto shorts/work/<name>`. If it stops, fix what it names and run again.
6. **QA, never skip:** open `review/all.jpg` (Read tool) and full frames of key moments
   (`python shorts/make.py frames shorts/work/<name> 4.2,9.8`). Check:
   - the picture matches the spoken word
   - reveals land on their word
   - nothing collides with pills, cards or the caption bar
   - hands touch the right object
   - Devanagari renders (no boxes)
   - captions show exactly one gold word
   Fix and repeat.
7. `python shorts/make.py render shorts/work/<name>`
8. Fill `upload.json`:
   - a Hindi title of 100 characters or less, ending with `#shorts`
   - a Hindi description ending with `#shorts #पहेली #हिंदी`
   - 5-8 tags
   - privacy as instructed
   Then run `python shorts/make.py upload shorts/work/<name> --yes`.

Never print the values of SARVAM_API_KEY or YOUTUBE_TOKEN_MAIN. Never commit `shorts/work/`.
