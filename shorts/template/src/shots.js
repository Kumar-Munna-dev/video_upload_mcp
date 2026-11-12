// पहेली: 3 स्विच, 1 बल्ब : the shot list (Stick Story).
// One picture per clause. A shot: { id, at, cam: [cx, cy], zoom, note, draw(lt, d, t) }. cut(i) = just before line i,
// Wd('word', i) = when the word is said. Sound: cue(t, type, { gain, dur }).
import { ctx, W, H, clamp, lerp, seg, eo, eio, eob, rr, circle, ell, line } from './core/lib.js';
import { L, Le, Wd, T } from './core/timing.js';
import * as K from './core/kit.js';
const { P, GROUND, FLOOR } = K;

// ───────── set pieces for this story ─────────
/** a plain room shell (wall + floor), night or day */
function shellRoom(night) {
  ctx.fillStyle = night ? P.nWall : P.wall; ctx.fillRect(-300, -300, W + 600, FLOOR + 300);
  ctx.fillStyle = night ? P.nWallShade : P.wallShade; ctx.fillRect(-300, FLOOR - 70, W + 600, 70);
  ctx.fillStyle = night ? P.nFloor : P.floor; ctx.fillRect(-300, FLOOR, W + 600, H - FLOOR + 300);
  ctx.strokeStyle = night ? P.nFloorDark : P.floorDark; ctx.lineWidth = 6;
  for (let y = FLOOR + 90; y < H + 300; y += 110) { ctx.beginPath(); ctx.moveTo(-300, y); ctx.lineTo(W + 300, y); ctx.stroke(); }
}
/** three wall switches. up = [0..1, 0..1, 0..1] (1 = ON). Numbers under each. */
function switchPanel(x, y, s, up = [0, 0, 0]) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  rr(-170, -90, 340, 180, 22); ctx.fillStyle = '#F7F1E6'; ctx.fill(); ctx.strokeStyle = '#C9BFA9'; ctx.lineWidth = 6; ctx.stroke();
  for (let k = 0; k < 3; k++) {
    const cx = -105 + k * 105;
    rr(cx - 34, -62, 68, 124, 14); ctx.fillStyle = '#E2D8C4'; ctx.fill();
    const u = up[k]; rr(cx - 24, lerp(4, -54, u), 48, 52, 10); ctx.fillStyle = u > 0.5 ? P.gold : '#9AA0AC'; ctx.fill();
    ctx.font = '900 46px Inter'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = P.white; ctx.fillText(String(k + 1), cx, 128);
  }
  ctx.restore();
}
/** an old filament bulb hanging at (x, y). mode: 'on' | 'off' | 'hot' | 'cold' */
function bulb(x, y, s, mode = 'off', t = 0, cord = true) {
  if (cord) line([[x, -300], [x, y - 110 * s]], P.ink, 8 * s);
  if (mode === 'on') { const g = ctx.createRadialGradient(x, y, 10, x, y, 520 * s); g.addColorStop(0, 'rgba(255,217,138,0.75)'); g.addColorStop(1, 'rgba(255,217,138,0)'); ctx.fillStyle = g; ctx.fillRect(x - 600 * s, y - 600 * s, 1200 * s, 1200 * s); }
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  rr(-30, -112, 60, 50, 8); ctx.fillStyle = '#8E95A3'; ctx.fill();
  for (let k = 0; k < 3; k++) line([[-30, -100 + k * 14], [30, -94 + k * 14]], '#6B7280', 4);
  const glass = mode === 'on' ? '#FFE9A8' : mode === 'hot' ? '#F6C3B5' : mode === 'cold' ? '#BFD9F2' : '#D9DDE4';
  circle(0, 0, 78, glass); ell(-26, -24, 14, 26, 'rgba(255,255,255,0.6)', -0.5);
  line([[-18, -62], [-18, -10], [-6, 6], [6, -10], [18, 6], [18, -62]], mode === 'on' ? '#F2B23E' : mode === 'hot' ? P.red : '#8E95A3', 5);
  ctx.restore();
  if (mode === 'hot') heatWaves(x, y - 150 * s, s, t);
  if (mode === 'cold') for (let k = 0; k < 3; k++) { ctx.beginPath(); ctx.arc(x, y, (100 + k * 34) * s, 0, Math.PI * 2); ctx.strokeStyle = `rgba(120,180,235,${0.5 - k * 0.14})`; ctx.lineWidth = 6 * s; ctx.stroke(); }
}
function heatWaves(x, y, s, t) {
  for (const dx of [-60, 0, 60]) {
    const pts = []; for (let k = 0; k <= 8; k++) pts.push([x + dx * s + Math.sin(k * 1.3 + t * 8 + dx) * 12 * s, y - k * 16 * s]);
    line(pts, P.red, 8 * s);
  }
}
/** night corridor: switch panel on the wall, the room's door on the right (open 0..1) */
const PANEL = [520, 880], DOOR_X = 840;
function corridor(up, open = 0) {
  shellRoom(true); K.door(DOOR_X, FLOOR + 40, '', open, true);
  switchPanel(PANEL[0], PANEL[1], 1, up);
}
/** dark room with the bulb */
function room(mode, t) { shellRoom(true); if (mode !== 'on') { ctx.fillStyle = 'rgba(5,8,18,0.35)'; ctx.fillRect(-300, -300, W + 600, H + 600); } bulb(600, 620, 1.5, mode, t); }
function qmark(x, y, size, sc = 1) { if (sc <= 0) return; ctx.save(); ctx.translate(x, y); ctx.scale(sc, sc); ctx.font = `900 ${size}px Inter`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineWidth = size * 0.12; ctx.strokeStyle = P.ink; ctx.strokeText('?', 0, 0); ctx.fillStyle = P.gold; ctx.fillText('?', 0, 0); ctx.restore(); }

export function buildShots() {
  const S = [], CUES = [], add = (o) => (S.push(o), o), cue = (t, type, o = {}) => CUES.push({ t: +t.toFixed(3), type, ...o });
  const cut = (i) => (i === 0 ? 0 : L(i) - 0.08);
  const blink = (t) => ((t % 3.1) < 0.12 ? 1 : 0);
  const HERO = { glow: true, y: GROUND, h: 840 };

  // 0 · three switches outside
  { const sw = Wd('स्विच', 0);
    add({ id: 'S00', at: 0, cam: [520, 1050], zoom: 0.08, note: 'night corridor, hero looks at 3 switches', draw(lt, d, t) {
      corridor([0, 0, 0]);
      K.person({ ...HERO, x: 230, mood: lt > sw ? 'worried' : 'calm', look: [1, -0.4], blink: blink(t), arms: { L: [-6, 14], R: [lt > sw ? 60 : 10, 16] } });
      if (lt > sw) K.counterPill('3 स्विच', 520, 640, eob(seg(lt, sw, sw + 0.25)) * 1.3);
    } });
    cue(0.15, 'whoosh', { gain: 0.6 }); cue(sw, 'pop'); }

  // 1 · closed room, one old bulb
  { const st = cut(1), b = Wd('बल्ब', 1) - st;
    add({ id: 'S01', at: st, cam: [700, 1000], zoom: 0.1, note: 'closed door, thought bubble with the bulb', draw(lt, d, t) {
      corridor([0, 0, 0]);
      K.thought(560, 480, eob(seg(lt, 0.1, 0.4)), () => bulb(560, 490, 0.85, 'off', t, false), 760, 760);
      K.counterPill('बंद कमरा', 760, 320, eob(seg(lt, 0.2, 0.45)) * 1.3);
    } });
    cue(st, 'whoosh'); cue(st + 0.1, 'pop', { gain: 0.5 }); cue(st + b, 'plop'); }

  // 2 · you can open the door only once
  { const st = cut(2), one = Wd('एक', 2) - st;
    add({ id: 'S02', at: st, cam: [700, 1100], note: 'hero at the door, "सिर्फ 1 बार" pops', draw(lt, d, t) {
      corridor([0, 0, 0]);
      K.person({ ...HERO, x: 560, mood: lt > one ? 'determined' : 'calm', look: [1, 0], blink: blink(t) });
      K.counterPill('सिर्फ 1 बार', 760, 420, lt > one ? eob(seg(lt, one, one + 0.25)) * 1.3 : 0);
    } });
    cue(st, 'whoosh'); cue(st + one, 'boing', { gain: 0.5 }); }

  // 3 · which switch is the bulb's?
  { const st = cut(3), q = Wd('कौन', 3) - st;
    add({ id: 'S03', at: st, cam: [540, 900], zoom: 0.1, note: 'close-up confused face, ? over each switch', draw(lt, d, t) {
      shellRoom(true);
      K.bigHead(540, 1180, 330, { mood: 'worried', look: [Math.sin(lt * 3), -0.9] });
      switchPanel(540, 480, 1.3, [0, 0, 0]);
      for (let k = 0; k < 3; k++) qmark(540 + (-105 + k * 105) * 1.3, 260, 110, lt > q + k * 0.2 ? eob(seg(lt, q + k * 0.2, q + k * 0.2 + 0.25)) : 0);
    } });
    cue(st, 'whoosh'); for (let k = 0; k < 3; k++) cue(st + q + k * 0.2, 'pop', { gain: 0.45 }); }

  // 4 · five seconds, think! (countdown in the silence after the line)
  { const st = cut(4), c0 = Le(4) - st + 0.05;
    add({ id: 'S04', at: st, cam: [540, 960], zoom: 0.04, note: 'big countdown 5..1', draw(lt, d, t) {
      shellRoom(true);
      K.bigHead(540, 1180, 260, { mood: 'sleepy', look: [0.6, -1] });
      const k = Math.floor((lt - c0) / 1), n = lt < c0 ? 5 : Math.max(1, 5 - k), f = lt < c0 ? 0 : (lt - c0) % 1;
      K.counterPill(String(n), 540, 520, eob(seg(lt < c0 ? lt : f, 0, 0.25)) * 3.2);
      K.counterPill('सोचिए…', 540, 820, eob(seg(lt, 0.3, 0.55)));
    } });
    cue(st, 'whoosh');
    for (let k = 0; k < 5; k++) cue(st + c0 + k, 'tock', { gain: 0.6 }); }

  // 5 · now hear the answer
  { const st = cut(5), a = Wd('जवाब', 5) - st;
    add({ id: 'S05', at: st, cam: [540, 960], zoom: 0.08, note: 'happy face, bulb lights up above', draw(lt, d, t) {
      shellRoom(true);
      K.bigHead(540, 1180, 330, { mood: lt > a ? 'happy' : 'calm', look: [0, -1] });
      if (lt > a) { const p = eob(seg(lt, a, a + 0.3)); ctx.save(); ctx.translate(540, 560); ctx.scale(p, p); bulb(0, 0, 1.3, 'on', t, false); ctx.restore(); }
    } });
    cue(st, 'whoosh'); cue(st + a, 'sparkle', { dur: 0.7 }); }

  // 6 · step one: first switch ON for ten minutes
  { const st = cut(6), on = Wd('पहला', 6) - st, mn = Wd('मिनट', 6) - st;
    add({ id: 'S06', at: st, cam: [480, 1050], note: 'flip switch 1 up, clock runs to 10:00', draw(lt, d, t) {
      const u = eio(seg(lt, on, on + 0.25));
      corridor([u, 0, 0]);
      K.person({ ...HERO, x: 170, mood: 'determined', look: [1, -0.6], blink: blink(t), arms: { L: [-6, 14], R: [lerp(30, 118, eio(seg(lt, on - 0.4, on))), 0] } });
      K.stepCard(1, '10 मिनट ऑन', 540, 300, eob(seg(lt, 0.05, 0.3)));
      if (lt > mn) { const m = Math.min(10, Math.floor(seg(lt, mn, mn + 1.2) * 10)); K.counterPill(`${m}:00`, 760, 560, eob(seg(lt, mn, mn + 0.25))); }
    } });
    cue(st, 'whoosh'); cue(st + 0.05, 'pop'); cue(st + on + 0.2, 'tock'); }

  // 7 · step two: switch it OFF, turn the second ON
  { const st = cut(7), off = Wd('बंद', 7) - st, two = Wd('दूसरा', 7) - st;
    add({ id: 'S07', at: st, cam: [480, 1050], note: 'switch 1 down, then switch 2 up', draw(lt, d, t) {
      const u1 = 1 - eio(seg(lt, off, off + 0.25)), u2 = eio(seg(lt, two, two + 0.25));
      corridor([u1, u2, 0]);
      K.person({ ...HERO, x: lerp(170, 275, eio(seg(lt, off + 0.3, two - 0.05))), mood: 'determined', look: [1, -0.6], blink: blink(t), arms: { L: [-6, 14], R: [118, 0] } });
      K.stepCard(2, '1 बंद, 2 ऑन', 540, 300, eob(seg(lt, 0.05, 0.3)));
    } });
    cue(st, 'whoosh'); cue(st + 0.05, 'pop'); cue(st + off + 0.2, 'tock'); cue(st + two + 0.2, 'tock'); }

  // 8 · step three: go into the room
  { const st = cut(8), go = Wd('जाओ', 8) - st;
    add({ id: 'S08', at: st, cam: [600, 1050], note: 'hero walks to the door, door opens on "जाओ"', draw(lt, d, t) {
      corridor([0, 1, 0], eio(seg(lt, go, go + 0.4)));
      const p = eio(seg(lt, 0.1, go));
      K.person({ ...HERO, x: lerp(260, 620, p), walk: p < 1 ? lt * 9 : null, mood: 'determined', look: [1, 0], blink: blink(t) });
      K.stepCard(3, 'अंदर जाओ', 540, 300, eob(seg(lt, 0.05, 0.3)));
    } });
    cue(st, 'whoosh'); cue(st + 0.05, 'pop'); cue(st + go, 'slide', { dur: 0.5, gain: 0.5 }); }

  // 9 · bulb is ON → switch 2
  { const st = cut(9), two = Wd('दूसरा', 9) - st;
    add({ id: 'S09', at: st, cam: [540, 1000], zoom: 0.08, note: 'bulb glowing, check + "स्विच 2"', draw(lt, d, t) {
      room('on', t);
      K.person({ ...HERO, x: 300, mood: 'happy', look: [1, -1], blink: blink(t) });
      if (lt > two) { K.check(830, 1200, eob(seg(lt, two, two + 0.25))); K.counterPill('स्विच 2', 800, 1010, eob(seg(lt, two, two + 0.25)) * 1.3); }
    } });
    cue(st, 'whoosh'); cue(st + 0.1, 'sparkle', { dur: 0.6, gain: 0.6 }); cue(st + two, 'pop'); }

  // 10 · off but warm → switch 1 (hand only NEAR the bulb)
  { const st = cut(10), hot = Wd('गरम', 10) - st, one = Wd('पहला', 10) - st;
    add({ id: 'S10', at: st, cam: [540, 1000], zoom: 0.08, note: 'bulb off, hand near, heat waves, "स्विच 1"', draw(lt, d, t) {
      room(lt > hot ? 'hot' : 'off', t);
      K.person({ ...HERO, x: 300, mood: lt > hot ? 'scared' : 'calm', look: [1, -1], blink: 0, arms: { L: [-6, 14], R: [lerp(20, 108, eio(seg(lt, 0.2, hot))), 0] } });
      if (lt > one) K.counterPill('स्विच 1', 800, 1010, eob(seg(lt, one, one + 0.25)) * 1.3);
    } });
    cue(st, 'whoosh'); cue(st + hot, 'sizzle', { dur: 0.6, gain: 0.5 }); cue(st + one, 'pop'); }

  // 11 · off and cold → switch 3
  { const st = cut(11), cold = Wd('ठंडा', 11) - st, three = Wd('तीसरा', 11) - st;
    add({ id: 'S11', at: st, cam: [540, 1000], zoom: 0.08, note: 'bulb off and cold (blue), "स्विच 3"', draw(lt, d, t) {
      room(lt > cold ? 'cold' : 'off', t);
      K.person({ ...HERO, x: 300, mood: 'calm', look: [1, -1], blink: blink(t), arms: { L: [-6, 14], R: [140, 0] } });
      if (lt > three) K.counterPill('स्विच 3', 800, 1010, eob(seg(lt, three, three + 0.25)) * 1.3);
    } });
    cue(st, 'whoosh'); cue(st + cold, 'plop'); cue(st + three, 'pop'); }

  // 12 · did you get it right? comment!
  { const st = cut(12), cm = Wd('कमेंट', 12) - st;
    add({ id: 'S12', at: st, cam: [540, 1000], zoom: 0.1, note: 'daylight living room, hero waves, comment bubble', draw(lt, d, t) {
      K.livingRoom({});
      K.person({ x: 420, y: GROUND, h: 860, mood: 'happy', look: [0, 0], blink: blink(t), arms: { L: [-20, 30], R: [150 + Math.sin(lt * 8) * 15, 20] } });
      K.thought(760, 560, eob(seg(lt, cm - 0.2, cm + 0.1)), () => { ctx.font = '900 64px Inter'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = P.navy; ctx.fillText('कमेंट!', 760, 560); }, 560, 820);
    } });
    cue(st, 'whoosh'); cue(st + cm - 0.2, 'pop'); }

  return { shots: S, cues: CUES };
}
