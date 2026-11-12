"""Real-sounding Hindi narration with Sarvam AI (uses ../sarvam_voice.py; key: SARVAM_API_KEY or ~/.youtube-mcp/sarvam_key.txt).
usage: SKILL/scripts/py ~/.faceless-shorts/voice_sarvam.py <project>
  -> data/narration.wav + data/lines.json   (then run: SKILL/scripts/py <project>/tools/hi/words.py <project>)
script.json: "voice": "sarvam:male" | "sarvam:female" | "sarvam:<any Bulbul V4 Flash voice>"; optional "pace": 1.0
Sarvam gives no word times, so each sentence is spoken in one pass and its lines are split by length;
words.py (Whisper) then times every word."""
import io, json, re, sys, wave
from pathlib import Path
import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # repo root: sarvam_voice.py
import sarvam_voice  # noqa: E402

SR = 24000
P = Path(sys.argv[1]); S = json.loads((P / 'script.json').read_text(encoding='utf-8'))
SPEAKER = str(S.get('voice', 'sarvam:male')).split(':')[-1]
PACE = float(S.get('pace', 1.0))


def say(text):
    with wave.open(io.BytesIO(sarvam_voice.speak(text, SPEAKER, PACE))) as r:
        sr, x = r.getframerate(), np.frombuffer(r.readframes(r.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    if sr != SR: x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x)
    idx = np.where(np.abs(x) > 0.01 * max(1e-9, np.abs(x).max()))[0]      # trim silence at both ends
    return x[max(0, idx[0] - int(0.02 * SR)):min(len(x), idx[-1] + int(0.06 * SR))] if len(idx) else x


groups, cur = [], []
for i, ln in enumerate(S['lines']):
    cur.append(i)
    if re.search(r'[.?!।]["\')]*$', ln['text'].strip()) or ln.get('break') or i == len(S['lines']) - 1: groups.append(cur); cur = []
out = [np.zeros(int(S.get('lead', 0.4) * SR))]; t0 = len(out[0]) / SR; lines = [None] * len(S['lines'])
for g in groups:
    x = say(' '.join(S['lines'][i]['text'] for i in g)); n = len(x) / SR
    w = [len(S['lines'][i]['text']) + 6 for i in g]; c = t0                   # split the sentence's time by line length
    for i, wi in zip(g, w):
        d = n * wi / sum(w); lines[i] = {'i': i, 'text': S['lines'][i]['text'], 'start': round(c, 3), 'end': round(c + d, 3)}; c += d
        print(f'{i:2d} {lines[i]["start"]:6.2f}-{lines[i]["end"]:6.2f}  {S["lines"][i]["text"]}', flush=True)
    gap = np.zeros(int(float(S['lines'][g[-1]].get('gap', S.get('gap', 0.28))) * SR))
    out += [x, gap]; t0 += (len(x) + len(gap)) / SR
out.append(np.zeros(int(float(S.get('outro', 0.9)) * SR)))
y = np.concatenate(out); y = y / (np.abs(y).max() + 1e-9) * 0.9; dur = len(y) / SR
(P / 'data').mkdir(exist_ok=True)
wavfile.write(P / 'data/narration.wav', SR, (y * 32767).astype(np.int16))
(P / 'data/lines.json').write_text(json.dumps({'duration': round(dur, 3), 'voice': f'sarvam:{SPEAKER}', 'lines': lines}, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'data/narration.wav ({dur:.2f} s, Sarvam {SPEAKER}) + lines.json. Next: tools/hi/words.py {P}')
