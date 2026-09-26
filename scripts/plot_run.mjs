#!/usr/bin/env node
// Draw run records (scripts/record_run.py) as views: pure functions, record in, SVG out.
//
// The views are the ones agreed in the design bake-off (docs/vision/VISUAL-LANGUAGE.md):
//   logic     timing diagram with value lanes (transient values shaded) + the linked event
//             log; for level inputs, the trace with each reader's thresholds and outputs, and
//             a hysteresis reader's transfer loop
//   optimize  value heatmap with labelled contours near the top, limits drawn where their
//             slack is zero, whole-unit plans with local optima ringed, climbs coloured by the
//             optimum they reach, and the ranked table; the branch-and-bound outline and tree,
//             both coloured by how close each bound is to the incumbent, dead branches drawn
//             dead
//   simulate  worker timeline with a progress-against-target strip, and the labor split
//   pack      the gate glyph sheet
//
// Nothing here computes a number the record does not hold, apart from layout. Output is
// deterministic: the same record gives byte-identical SVG. Colours are tokens on the SVG root,
// light by default and dark under prefers-color-scheme or [data-theme="dark"], so a file works
// standalone and inside a page. Hover text uses SVG <title>, which works in both.
//
//   node scripts/plot_run.mjs run.json [more.json ...] --out DIR        one SVG per view
//   node scripts/plot_run.mjs run.json [...] --page run.html            one page, views linked
//   node scripts/plot_run.mjs --glyphs --out DIR                        the pack's glyph sheet

import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));

// --------------------------------------------------------------------------- primitives

const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const r2 = v => Math.round(v * 100) / 100;
const PAINT = new Set(['fill', 'stroke']);

// One element. A paint that names a token goes in `style`, since presentation attributes
// cannot read custom properties.
function tag(name, attrs = {}, inner = '') {
  let style = '';
  const parts = [];
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (PAINT.has(k) && String(v).startsWith('--')) { style += `${k}:var(${v});`; continue; }
    parts.push(`${k}="${esc(typeof v === 'number' ? r2(v) : v)}"`);
  }
  if (style) parts.push(`style="${style}"`);
  return `<${name}${parts.length ? ' ' + parts.join(' ') : ''}${inner === null ? '/>' : `>${inner}</${name}>`}`;
}
const el = (name, attrs) => tag(name, attrs, null);
const text = (x, y, s, cls = 'lbl', attrs = {}) => tag('text', {x, y, class: cls, ...attrs}, esc(s));
const title = s => tag('title', {}, esc(s));
const lin = (d0, d1, r0, r1) => { const f = v => r0 + (v - d0) / (d1 - d0 || 1) * (r1 - r0); f.inv = p => d0 + (p - r0) / (r1 - r0) * (d1 - d0); return f; };

const TOKENS_LIGHT = '--v-canvas:#FEFEFC;--v-panel:#FFFFFF;--v-ink:#42423E;--v-muted:#6C6C65;--v-line:#D8D8D1;--v-hi:#2a78d6;--v-s2:#eb6834;--v-s3:#1baf7a;--v-hatch:#C9C9C1;--v-soft:rgba(42,120,214,.16)';
const TOKENS_DARK = '--v-canvas:#17191B;--v-panel:#1C1F21;--v-ink:#E7E8E3;--v-muted:#A8AAA4;--v-line:#3B3F42;--v-hi:#3987e5;--v-s2:#d95926;--v-s3:#199e70;--v-hatch:#44484C;--v-soft:rgba(57,135,229,.22)';
const STYLE = `.sov-view{${TOKENS_LIGHT};font-family:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace}` +
  `@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .sov-view,.sov-view.standalone{${TOKENS_DARK}}}` +
  `:root[data-theme="dark"] .sov-view{${TOKENS_DARK}}` +
  `.sov-view .lbl{font-size:11px;fill:var(--v-muted)}.sov-view .ink{font-size:11px;font-weight:600;fill:var(--v-ink)}` +
  `.sov-view .lane{font-size:11px;font-weight:600;fill:var(--v-ink)}.sov-view .bad{fill:var(--v-s2);font-weight:600}` +
  `.sov-view [data-link].hl{outline:none;filter:drop-shadow(0 0 3px var(--v-hi))}`;

function svg(w, h, label, body, kind) {
  return tag('svg', {xmlns: 'http://www.w3.org/2000/svg', viewBox: `0 0 ${w} ${h}`, class: 'sov-view', role: 'img',
    'aria-label': label, 'data-view': kind},
    tag('style', {}, STYLE) + el('rect', {x: 0, y: 0, width: w, height: h, fill: '--v-canvas'}) + body);
}
let hatchCount = 0;
const hatchDef = () => { const id = `hatch${hatchCount++}`;
  return [id, tag('defs', {}, tag('pattern', {id, width: 7, height: 7, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)'},
    el('path', {d: 'M0 0V7', stroke: '--v-hatch', 'stroke-width': 2})))]; };

// --------------------------------------------------------------------------- logic

function valueAt(changes, t) { let v = 0; for (const [tt, vv] of changes) { if (tt <= t) v = vv; else break; } return v; }
function busAt(rec, bus, t) { return rec.buses[bus].reduce((acc, bit, i) => acc + (valueAt(rec.signals[bit] || [], t) << i), 0); }

// Bus segments: the value between consecutive changes of any bit. A value that lasts under
// two gate delays while the bus is between two settled values is transient.
function busSegments(rec, bus, t0, t1) {
  const ts = new Set([t0, t1]);
  for (const bit of rec.buses[bus]) for (const [t] of rec.signals[bit] || []) if (t > t0 && t < t1) ts.add(t);
  const pts = [...ts].sort((a, b) => a - b);
  const segs = [];
  for (let i = 0; i + 1 < pts.length; i++) {
    const a = pts[i], b = pts[i + 1];
    segs.push({t0: a, t1: b, value: busAt(rec, bus, a), transient: b - a < 2 && b < t1 && a > t0});
  }
  return segs;
}

export function timing(rec, opts = {}) {
  const t0 = opts.window ? opts.window[0] : 0, t1 = opts.window ? opts.window[1] : rec.end;
  const lanes = opts.lanes || [...(rec.clock ? [rec.clock] : []),
    ...Object.values(rec.buses).flat(), ...Object.keys(rec.signals).filter(s => s !== rec.clock && !Object.values(rec.buses).flat().includes(s) && !rec.levels.includes(s))];
  const W = 760, lh = 30, top = 12, left = 64;
  const X = lin(t0, t1, left, W - 10);
  let body = '';
  lanes.forEach((name, i) => {
    const y = top + i * lh; body += text(0, y + 15, name, 'lane');
    const ch = rec.signals[name] || [];
    let d = `M${r2(X(t0))} ${y + (valueAt(ch, t0) ? 3 : 21)}`;
    ch.forEach(([t, v], k) => { if (t > t0 && t <= t1) d += `H${r2(X(t))}V${y + (v ? 3 : 21)}`; });
    d += `H${r2(X(t1))}`;
    body += el('path', {d, fill: 'none', stroke: name === rec.clock ? '--v-muted' : '--v-hi', 'stroke-width': 1.8, 'stroke-linejoin': 'round'});
    ch.forEach(([t, v]) => { if (t > t0 && t <= t1)
      body += tag('rect', {x: X(t) - 3, y, width: 6, height: 24, fill: 'transparent', 'data-link': `ev:${name}:${t}`}, title(`t=${t}  ${name} ${v ? '0→1' : '1→0'}`)); });
  });
  let y = top + lanes.length * lh + 6;
  for (const bus of Object.keys(rec.buses)) {
    body += text(0, y + 15, bus, 'lane');
    for (const s of busSegments(rec, bus, t0, t1)) {
      const xa = X(s.t0), xb = X(s.t1);
      const pts = `${r2(xa + 3)},${y + 2} ${r2(xb - 3)},${y + 2} ${r2(xb)},${y + 11} ${r2(xb - 3)},${y + 20} ${r2(xa + 3)},${y + 20} ${r2(xa)},${y + 11}`;
      body += tag('g', {'data-bus': bus, 'data-t0': s.t0, 'data-t1': s.t1, 'data-value': s.value, 'data-transient': s.transient ? 1 : 0},
        el('polygon', {points: pts, fill: s.transient ? '--v-s2' : '--v-panel', 'fill-opacity': s.transient ? 0.3 : 1,
          stroke: s.transient ? '--v-s2' : '--v-ink', 'stroke-width': 1.2}) +
        (xb - xa > 13 ? text((xa + xb) / 2, y + 15, String(s.value), s.transient ? 'ink' : 'lbl', {'text-anchor': 'middle'}) : '') +
        title(`${bus} = ${s.value} from t=${s.t0} to t=${s.t1}${s.transient ? ' (transient)' : ''}`));
    }
    y += 30;
  }
  const ay = y + 8; body += el('path', {d: `M${left} ${ay}H${W - 10}`, stroke: '--v-line'});
  const span = t1 - t0, step = span <= 30 ? 4 : span <= 120 ? 12 : 48;
  for (let t = Math.ceil(t0 / step) * step; t <= t1; t += step) body += text(X(t), ay + 15, String(t), 'lbl', {'text-anchor': 'middle'});
  body += text(W - 10, ay + 30, 'time (gate delays)', 'lbl', {'text-anchor': 'end'});
  return svg(W, ay + 38, `Timing diagram of ${rec.document.path}`, body, 'timing');
}

export function eventLog(rec, opts = {}) {
  const t0 = opts.window ? opts.window[0] : 0, t1 = opts.window ? opts.window[1] : rec.end;
  const rows = rec.events.filter(e => e.t >= t0 && e.t <= t1);
  const buses = Object.keys(rec.buses);
  const transient = new Set();
  for (const b of buses) for (const s of busSegments(rec, b, t0, t1)) if (s.transient) transient.add(s.t0);
  const head = `<tr><th>t</th><th>signal</th><th>change</th>${buses.map(b => `<th>${esc(b)} after</th>`).join('')}</tr>`;
  const body = rows.map(e => {
    const bad = transient.has(e.t) && !(rec.clock && e.signal === rec.clock);
    return `<tr data-link="ev:${esc(e.signal)}:${e.t}"${bad ? ' class="bad"' : ''}><td class="num">${e.t}</td><td>${esc(e.signal)}</td>` +
      `<td>${e.value ? '0→1' : '1→0'}</td>${buses.map(b => `<td class="num">${busAt(rec, b, e.t)}</td>`).join('')}</tr>`;
  }).join('');
  return `<table class="sov-log"><thead>${head}</thead><tbody>${body}</tbody></table>`;
}

export function levelTrace(rec) {
  const level = rec.levels[0]; const samples = rec.signals[level] || [];
  const W = 780, left = 44, right = 660; const X = lin(0, rec.end, left, right), Y = lin(0, 1.05, 160, 12);
  let body = '';
  for (const r of rec.readers) {
    if (r.kind === 'hysteresis') {
      body += tag('rect', {x: left, y: Y(r.params.high), width: right - left, height: Y(r.params.low) - Y(r.params.high), fill: '--v-soft'}, title(`${r.gate}: on at ${r.params.high}, off at ${r.params.low}`));
      body += text(right + 6, Y(r.params.high) + 4, `high ${r.params.high}`) + text(right + 6, Y(r.params.low) + 4, `low ${r.params.low}`);
    } else {
      body += el('path', {d: `M${left} ${r2(Y(r.params.theta))}H${right}`, stroke: '--v-s2', 'stroke-width': 1.3, 'stroke-dasharray': '5 4'});
      body += text(right + 6, Y(r.params.theta) + 4, `θ ${r.params.theta}`);
    }
  }
  body += el('path', {d: samples.map(([t, v], i) => `${i ? 'L' : 'M'}${r2(X(t))} ${r2(Y(v))}`).join(''), fill: 'none', stroke: '--v-ink', 'stroke-width': 1.2});
  body += text(0, 20, level, 'lane') + text(left - 6, Y(0) + 4, '0', 'lbl', {'text-anchor': 'end'}) + text(left - 6, Y(1) + 4, '1', 'lbl', {'text-anchor': 'end'});
  let y = 180;
  for (const r of rec.readers) for (const out of r.outputs) {
    const ch = rec.signals[out] || []; let d = `M${left} ${y + (valueAt(ch, 0) ? 3 : 21)}`;
    ch.forEach(([t, v]) => { d += `H${r2(X(t))}V${y + (v ? 3 : 21)}`; }); d += `H${right}`;
    const switches = ch.filter(([t]) => t > 0).length;
    body += text(0, y + 15, out, 'lane') + el('path', {d, fill: 'none', stroke: r.kind === 'hysteresis' ? '--v-hi' : '--v-s2', 'stroke-width': 1.7});
    body += tag('text', {x: right + 6, y: y + 15, class: 'ink', 'data-switches': switches}, `${switches} switches`);
    y += 34;
  }
  body += el('path', {d: `M${left} ${y + 4}H${right}`, stroke: '--v-line'});
  [0, Math.round(rec.end / 2), rec.end].forEach(t => { body += text(X(t), y + 19, String(t), 'lbl', {'text-anchor': 'middle'}); });
  body += text(right, y + 34, 'sample', 'lbl', {'text-anchor': 'end'});
  return svg(W, y + 42, `Level ${level} with its readers`, body, 'level');
}

export function transferLoop(rec, reader) {
  const level = rec.levels[0]; const W = 420, H = 280; const lx = lin(0, 1, 50, 400), ly = lin(0, 1, 220, 40);
  const {low, high} = reader.params; const out = reader.outputs[0]; const samples = rec.signals[level] || [];
  let body = el('path', {d: `M50 230H400M50 230V30`, stroke: '--v-line'});
  samples.forEach(([t, x]) => { body += el('circle', {cx: lx(x), cy: ly(valueAt(rec.signals[out] || [], t)), r: 2, fill: '--v-hi', opacity: 0.3}); });
  body += el('path', {d: `M${lx(0)} ${ly(0)}H${lx(high)}V${ly(1)}H${lx(1)}`, fill: 'none', stroke: '--v-hi', 'stroke-width': 2.2});
  body += el('path', {d: `M${lx(1)} ${ly(1)}H${lx(low)}V${ly(0)}`, fill: 'none', stroke: '--v-hi', 'stroke-width': 2.2});
  body += el('path', {d: `M${r2(lx(high) - 5)} ${r2(ly(0.5) + 6)}L${r2(lx(high))} ${r2(ly(0.5) - 2)}L${r2(lx(high) + 5)} ${r2(ly(0.5) + 6)}`, fill: 'none', stroke: '--v-hi', 'stroke-width': 1.6});
  body += el('path', {d: `M${r2(lx(low) - 5)} ${r2(ly(0.5) - 6)}L${r2(lx(low))} ${r2(ly(0.5) + 2)}L${r2(lx(low) + 5)} ${r2(ly(0.5) - 6)}`, fill: 'none', stroke: '--v-hi', 'stroke-width': 1.6});
  body += text(lx(high) + 8, ly(0.5), 'rising') + text(lx(low) - 8, ly(0.5), 'falling', 'lbl', {'text-anchor': 'end'});
  [0, low, high, 1].forEach(v => { body += text(lx(v), 246, String(v), 'lbl', {'text-anchor': 'middle'}); });
  body += text(400, 264, `level ${level}`, 'lbl', {'text-anchor': 'end'}) + text(44, ly(1) + 4, '1', 'lbl', {'text-anchor': 'end'}) + text(44, ly(0) + 4, '0', 'lbl', {'text-anchor': 'end'});
  body += text(50, 20, `${reader.gate}: ${out} against ${level}`, 'ink');
  return svg(W, H, `Transfer loop of ${reader.gate}`, body, 'loop');
}

// --------------------------------------------------------------------------- optimize

// Line segments where a grid crosses a level (marching squares, with interpolation).
function contour(xs, ys, grid, level) {
  const segs = [];
  for (let i = 0; i + 1 < xs.length; i++) for (let j = 0; j + 1 < ys.length; j++) {
    const a = grid[i][j], b = grid[i + 1][j], c = grid[i + 1][j + 1], d = grid[i][j + 1];
    if ([a, b, c, d].some(v => v === null || v === undefined)) continue;
    const pts = [];
    const edge = (v1, v2, x1, y1, x2, y2) => { if ((v1 < level) !== (v2 < level)) { const t = (level - v1) / (v2 - v1); pts.push([x1 + (x2 - x1) * t, y1 + (y2 - y1) * t]); } };
    edge(a, b, xs[i], ys[j], xs[i + 1], ys[j]); edge(b, c, xs[i + 1], ys[j], xs[i + 1], ys[j + 1]);
    edge(c, d, xs[i + 1], ys[j + 1], xs[i], ys[j + 1]); edge(d, a, xs[i], ys[j + 1], xs[i], ys[j]);
    for (let k = 0; k + 1 < pts.length; k += 2) segs.push([pts[k], pts[k + 1]]);
  }
  return segs;
}
// Contour levels near the top: round figures just under the best value, where shades alone
// cannot tell plans apart.
function topLevels(vmax) {
  const step = Math.pow(10, Math.floor(Math.log10(vmax)) - 1);
  return [0.95, 0.985].map(f => Math.floor(vmax * f / step) * step);
}

// A landscape is the whole problem for two decisions, or a slice for more: the other decisions
// are held (L.held), and anything whose held coordinates differ is drawn projected, dashed and
// said so, because it is not a plan in this picture.
const heldKey = held => Object.entries(held).map(([k, v]) => `${k}=${r2(v)}`).join(',');
const inSlice = (at, held) => Object.entries(held).every(([k, v]) => Math.abs(at[k] - v) < 1e-6);

export function landscape(rec, L) {
  const [dx, dy] = L.decisions; const W = 760, H = 520, left = 56, right = 640, top = 24, bottom = 470;
  const ia = rec.decisions.indexOf(dx), ib = rec.decisions.indexOf(dy);
  const sliced = Object.keys(L.held).length > 0;
  const X = lin(L.x[0], L.x[L.x.length - 1], left, right), Y = lin(L.y[0], L.y[L.y.length - 1], bottom, top);
  const [hid, hdef] = hatchDef();
  let vmax = 0; L.value.forEach(r => r.forEach(v => { if (v !== null && v > vmax) vmax = v; }));
  let body = hdef + el('rect', {x: left, y: top, width: right - left, height: bottom - top, fill: `url(#${hid})`});
  const cw = (X(L.x[1]) - X(L.x[0])), ch = (Y(L.y[0]) - Y(L.y[1]));
  const shade = v => r2(0.05 + 0.85 * Math.pow(v / vmax, 3));
  L.value.forEach((row, i) => row.forEach((v, j) => { if (v === null) return;
    body += el('rect', {x: X(L.x[i]) - cw / 2, y: Y(L.y[j]) - ch / 2, width: cw + 0.4, height: ch + 0.4, fill: '--v-hi', 'fill-opacity': shade(v)}); }));
  for (const [name, grid] of Object.entries(L.slack)) {
    const segs = contour(L.x, L.y, grid, 0);
    if (!segs.length) continue;
    body += tag('g', {'data-limit': name}, el('path', {d: segs.map(([p, q]) => `M${r2(X(p[0]))} ${r2(Y(p[1]))}L${r2(X(q[0]))} ${r2(Y(q[1]))}`).join(''),
      fill: 'none', stroke: '--v-ink', 'stroke-width': 1.7, 'stroke-dasharray': name.includes('supply') ? '6 4' : null}) + title(`limit: ${name}`));
    const mid = segs[Math.floor(segs.length * 0.3)][0];
    body += text(X(mid[0]) + 6, Y(mid[1]) - 6, name, 'ink');
  }
  for (const lv of topLevels(vmax)) {
    const segs = contour(L.x, L.y, L.value, lv);
    if (!segs.length) continue;
    body += tag('g', {'data-contour': lv}, el('path', {d: segs.map(([p, q]) => `M${r2(X(p[0]))} ${r2(Y(p[1]))}L${r2(X(q[0]))} ${r2(Y(q[1]))}`).join(''),
      fill: 'none', stroke: '--v-panel', 'stroke-width': 1.4}));
    // label at the contour's left end, clear of the plans that crowd the top
    const at = segs.reduce((best, s) => s[0][0] < best[0] ? s[0] : best, segs[0][0]);
    body += text(X(at[0]) - 6, Y(at[1]) + 14, `${rec.unit === 'USD' ? '$' : ''}${lv}`, 'ink', {'text-anchor': 'end'});
  }
  // climbs, projected onto this pair when the model has more decisions
  rec.climbs.forEach((c, k) => { const col = c.optimum === 0 ? '--v-hi' : '--v-s2';
    const pts = c.path.map(p => [p[ia], p[ib]]);
    body += tag('g', {'data-climb': k, 'data-optimum': c.optimum, 'data-projected': sliced ? 1 : 0},
      el('path', {d: pts.map((p, i) => `${i ? 'L' : 'M'}${r2(X(p[0]))} ${r2(Y(p[1]))}`).join(''), fill: 'none', stroke: col, 'stroke-width': 1.3, opacity: sliced ? 0.45 : 0.85, 'stroke-dasharray': sliced ? '4 3' : null}) +
      el('rect', {x: X(pts[0][0]) - 3, y: Y(pts[0][1]) - 3, width: 6, height: 6, fill: '--v-canvas', stroke: col, 'stroke-width': 1.3}) +
      (sliced ? title('climb, projected onto this slice') : '')); });
  const provenWhole = rec.plans.find(p => p.name === 'whole-unit optimum');
  const hk = heldKey(L.held);
  L.whole.forEach(w => { const [a, b] = w.at;
    const best = provenWhole && inSlice(provenWhole.at, L.held) && provenWhole.at[dx] === a && provenWhole.at[dy] === b;
    body += tag('g', {'data-whole': `${a},${b}`, 'data-local': w.local ? 1 : 0, 'data-link': w.local ? `plan:${dx}=${a},${dy}=${b}${hk ? ',' + hk : ''}` : null},
      el('circle', {cx: X(a), cy: Y(b), r: 1.9, fill: '--v-ink'}) +
      (w.local ? el('circle', {cx: X(a), cy: Y(b), r: 5.5, fill: best ? '--v-ink' : 'none', stroke: '--v-ink', 'stroke-width': 1.7}) : '') +
      el('circle', {cx: X(a), cy: Y(b), r: 7, fill: 'transparent'}) +
      title(`${a} ${dx}, ${b} ${dy}${hk ? ` (${hk})` : ''}: ${w.value.toFixed(2)}${w.local ? (best ? ' (proven whole-unit optimum)' : sliced ? ' (local optimum in this slice)' : ' (local optimum)') : ''}`)); });
  const where = at => sliced && !inSlice(at, L.held) ? ' (outside this slice; projected)' : '';
  rec.optima.forEach((o, k) => { const out = sliced && !inSlice(o.at, L.held);
    body += tag('g', {'data-link': `optimum:${k}`, 'data-in-slice': out ? 0 : 1}, el('circle', {cx: X(o.at[dx]), cy: Y(o.at[dy]), r: 6.5, fill: '--v-canvas', stroke: k === 0 ? '--v-hi' : '--v-s2', 'stroke-width': 2.2, 'stroke-dasharray': out ? '3 2' : null}) +
      title(`climb optimum (local): ${rec.decisions.map(n => `${r2(o.at[n])} ${n}`).join(', ')}, ${o.value.toFixed(2)}, ${o.starts} starts${where(o.at)}`)); });
  for (const p of rec.plans) {
    const a = p.at[dx], b = p.at[dy], x = X(a), y = Y(b), out = sliced && !inSlice(p.at, L.held), dash = out ? '3 2' : null;
    let mark;
    if (!p.feasible) mark = el('circle', {cx: x, cy: y, r: 8, fill: 'none', stroke: '--v-s2', 'stroke-width': 2.4, 'stroke-dasharray': dash});
    else if (p.certificate === 'naive') mark = el('path', {d: `M${r2(x - 6)} ${r2(y - 6)}l12 12m0-12l-12 12`, stroke: '--v-ink', 'stroke-width': 2.4, opacity: out ? 0.5 : null});
    else if (p.name === 'fractional optimum') mark = el('path', {d: `M${r2(x)} ${r2(y - 8)}l8 8l-8 8l-8-8Z`, fill: out ? 'none' : '--v-ink', stroke: '--v-ink', 'stroke-width': 1.6, 'stroke-dasharray': dash});
    else mark = el('circle', {cx: x, cy: y, r: 6.5, fill: out ? 'none' : '--v-ink', stroke: '--v-ink', 'stroke-width': 1.6, 'stroke-dasharray': dash});
    body += tag('g', {'data-plan': p.name, 'data-link': `plan:${p.name}`, 'data-at': `${r2(a)},${r2(b)}`, 'data-certificate': p.certificate,
      'data-feasible': p.feasible ? 1 : 0, 'data-in-slice': out ? 0 : 1},
      mark + title(`${p.name} (${p.certificate}${p.feasible ? '' : ', breaks a limit'}): ${rec.decisions.map(n => `${r2(p.at[n])} ${n}`).join(', ')}, ${p.value.toFixed(2)}${where(p.at)}`));
  }
  body += el('path', {d: `M${left} ${bottom}H${right}M${left} ${top}V${bottom}`, stroke: '--v-line'});
  const xstep = (L.x[L.x.length - 1] - L.x[0]) > 12 ? 4 : 2, ystep = (L.y[L.y.length - 1] - L.y[0]) > 12 ? 4 : 2;
  for (let v = L.x[0]; v <= L.x[L.x.length - 1] + 1e-9; v += xstep) body += text(X(v), bottom + 16, String(r2(v)), 'lbl', {'text-anchor': 'middle'});
  for (let v = L.y[0]; v <= L.y[L.y.length - 1] + 1e-9; v += ystep) body += text(left - 6, Y(v) + 4, String(r2(v)), 'lbl', {'text-anchor': 'end'});
  body += text(right, bottom + 34, dx, 'lbl', {'text-anchor': 'end'}) + text(left, top - 8, dy, 'lbl');
  if (sliced) body += tag('text', {x: right, y: top - 8, class: 'ink', 'text-anchor': 'end', 'data-slice': hk}, esc(`slice: ${Object.entries(L.held).map(([k, v]) => `${k} held at ${r2(v)}`).join(', ')}`));
  const kx = 668; body += text(kx, 38, 'value', 'ink');
  for (let i = 0; i <= 20; i++) body += el('rect', {x: kx, y: 48 + (20 - i) * 9, width: 16, height: 9, fill: '--v-hi', 'fill-opacity': shade(i / 20 * vmax)});
  body += text(kx + 22, 56, `${Math.round(vmax)}`) + text(kx + 22, 236, '0');
  body += el('rect', {x: kx, y: 256, width: 16, height: 14, fill: `url(#${hid})`, stroke: '--v-line'}) + text(kx + 22, 267, 'breaks');
  body += text(kx + 22, 281, 'a limit');
  if (sliced) body += el('circle', {cx: kx + 8, cy: 306, r: 6, fill: 'none', stroke: '--v-ink', 'stroke-dasharray': '3 2'}) + text(kx + 22, 310, 'projected');
  return svg(W, H, `Landscape of ${rec.document.path}${sliced ? `, ${dx} by ${dy} slice` : ''}`, body, 'landscape');
}

export function landscapeTable(rec) {
  const names = rec.decisions, rows = [];
  for (const p of rec.plans) rows.push({key: `plan:${p.name}`, name: p.name, at: p.at, value: p.value, kind: p.certificate + (p.feasible ? '' : ', breaks a limit'), bad: !p.feasible});
  const best = rec.plans.find(p => p.name === 'whole-unit optimum');
  const same = (a, b) => names.every(n => Math.abs(a[n] - b[n]) < 1e-6);
  for (const L of rec.landscapes) {
    const [dx, dy] = L.decisions, hk = heldKey(L.held), sliced = hk !== '';
    L.whole.filter(w => w.local).map(w => ({...w, full: {...L.held, [dx]: w.at[0], [dy]: w.at[1]}}))
      .filter(w => !(best && same(best.at, w.full))).sort((a, b) => b.value - a.value)
      .forEach((w, i) => rows.push({key: `plan:${dx}=${w.at[0]},${dy}=${w.at[1]}${hk ? ',' + hk : ''}`,
        name: sliced ? `local in ${dx} × ${dy} slice ${i + 1}` : `local optimum ${i + 1}`, at: w.full, value: w.value, kind: 'local'}));
  }
  rec.optima.forEach((o, k) => rows.push({key: `optimum:${k}`, name: `climb end ${k + 1} (${o.starts} starts)`, at: o.at, value: o.value, kind: 'local', bad: k > 0}));
  const body = rows.map(r => `<tr data-link="${esc(r.key)}"${r.bad ? ' class="bad"' : ''}><td>${esc(r.name)}</td>${names.map(n => `<td class="num">${r2(r.at[n])}</td>`).join('')}<td class="num">${r.value.toFixed(2)}</td><td>${esc(r.kind)}</td></tr>`).join('');
  return `<table class="sov-log"><thead><tr><th>plan</th>${names.map(n => `<th>${esc(n)}</th>`).join('')}<th>${esc(rec.unit || 'value')}</th><th>kind</th></tr></thead><tbody>${body}</tbody></table>`;
}

// Search: every node coloured by how close its bound came to the final incumbent (the gradient
// map), dead branches (pruned, infeasible) drawn dead.
function searchModel(rec) {
  const S = rec.search; const by = {};
  S.nodes.forEach(n => { by[n.id] = {...n, kids: []}; });
  Object.values(by).forEach(n => { if (n.parent !== null && by[n.parent]) by[n.parent].kids.push(n); });
  Object.values(by).forEach(n => n.kids.sort((a, b) => a.id - b.id));
  const order = []; (function walk(n, d) { n.depth = d; order.push(n); n.kids.forEach(k => walk(k, d + 1)); })(by[0], 0);
  const span = Math.max(1e-9, S.relaxation - S.objective);
  for (const n of order) { n.dead = n.outcome === 'pruned' || n.outcome === 'infeasible'; n.gap = n.bound === null || n.bound === undefined ? null : Math.max(0, Math.min(1, (n.bound - S.objective) / span)); }
  return {order, by};
}
// Near the incumbent (gap 0) is strong signal blue; far (gap 1) is faint.
const gapOpacity = g => r2(1 - 0.8 * g);

function nodeMark(n, x, y) {
  if (n.outcome === 'infeasible') return el('path', {d: `M${r2(x - 4)} ${r2(y - 4)}l8 8m0-8l-8 8`, stroke: '--v-s2', 'stroke-width': 1.8});
  if (n.outcome === 'pruned') return el('circle', {cx: x, cy: y, r: 4.5, fill: '--v-canvas', stroke: '--v-muted', 'stroke-width': 1.3, 'stroke-dasharray': '2 2'});
  if (n.outcome === 'incumbent') return el('circle', {cx: x, cy: y, r: 6, fill: '--v-hi', stroke: '--v-ink', 'stroke-width': 1.5});
  return el('circle', {cx: x, cy: y, r: 5, fill: '--v-hi', 'fill-opacity': gapOpacity(n.gap ?? 1), stroke: '--v-ink', 'stroke-width': 1.3});
}
const nodeTitle = (n, rec) => title(`${n.label}: ${n.outcome}${n.bound != null ? `, bound ${n.bound.toFixed(2)}` : ''}${n.gap != null ? `, ${Math.round(n.gap * 100)}% of the way from the incumbent to the root bound` : ''}`);

export function searchOutline(rec) {
  const {order} = searchModel(rec); const S = rec.search; const rowH = 19, top = 24, W = 640, BX = 480;
  const bmin = Math.min(...order.filter(n => n.bound != null).map(n => n.bound)) - 1;
  const B = lin(bmin, S.relaxation, BX, W - 10);
  let body = text(0, 14, 'branch', 'ink') + text(BX, 14, 'LP bound', 'ink');
  body += el('path', {d: `M${r2(B(S.objective))} ${top - 6}V${top + order.length * rowH}`, stroke: '--v-hi', 'stroke-dasharray': '3 3'});
  order.forEach((n, i) => {
    const y = top + i * rowH + 8, x = 10 + n.depth * 13;
    let g = n.depth ? el('path', {d: `M${x - 8} ${y - rowH + 6}V${y}H${x - 3}`, fill: 'none', stroke: '--v-line', 'stroke-dasharray': n.dead ? '2 2' : null}) : '';
    g += nodeMark(n, x + 2, y) + text(x + 12, y + 4, n.label, n.dead ? 'lbl' : 'ink', n.dead ? {'text-decoration': n.outcome === 'pruned' ? 'line-through' : null} : {});
    if (n.bound != null) g += el('rect', {x: BX, y: y - 4, width: Math.max(1, B(n.bound) - BX), height: 8, rx: 2, fill: n.dead ? '--v-muted' : '--v-hi', 'fill-opacity': n.dead ? 0.3 : gapOpacity(n.gap)});
    body += tag('g', {'data-node': n.id, 'data-link': `node:${n.id}`, 'data-dead': n.dead ? 1 : 0, 'data-gap': n.gap === null ? '' : r2(n.gap), 'data-outcome': n.outcome},
      g + el('rect', {x: 0, y: y - 9, width: W, height: 18, fill: 'transparent'}) + nodeTitle(n, rec));
  });
  const yb = top + order.length * rowH + 8;
  body += text(B(S.objective) - 4, yb + 10, `incumbent ${S.objective.toFixed(0)}`, 'lbl', {'text-anchor': 'end'});
  return svg(W, yb + 18, `Search outline for ${rec.document.path}`, body, 'outline');
}

export function searchTree(rec) {
  const {order, by} = searchModel(rec);
  const leaves = []; (function lay(n) { if (!n.kids.length) { n.lx = leaves.length; leaves.push(n); } else { n.kids.forEach(lay); n.lx = n.kids.reduce((a, k) => a + k.lx, 0) / n.kids.length; } })(by[0]);
  const maxD = Math.max(...order.map(n => n.depth)); const W = 560, H = 60 + maxD * 42;
  const X = lin(0, Math.max(1, leaves.length - 1), 18, W - 18), Y = d => 22 + d * 42;
  let body = '';
  order.forEach(n => n.kids.forEach(k => { body += el('path', {d: `M${r2(X(n.lx))} ${Y(n.depth)}L${r2(X(k.lx))} ${Y(k.depth)}`, stroke: k.dead ? '--v-line' : '--v-ink', 'stroke-width': k.dead ? 1.1 : 1.6, 'stroke-dasharray': k.dead ? '3 3' : null, opacity: k.dead ? 1 : 0.8}); }));
  order.forEach(n => { body += tag('g', {'data-node': n.id, 'data-link': `node:${n.id}`, 'data-dead': n.dead ? 1 : 0, 'data-gap': n.gap === null ? '' : r2(n.gap)},
    nodeMark(n, X(n.lx), Y(n.depth)) + el('circle', {cx: X(n.lx), cy: Y(n.depth), r: 9, fill: 'transparent'}) + nodeTitle(n, rec)); });
  const inc = order.find(n => n.outcome === 'incumbent');
  if (inc) body += text(X(inc.lx) - 10, Y(inc.depth) + 4, `best ${rec.search.objective.toFixed(0)}`, 'ink', {'text-anchor': 'end'});
  body += text(X(by[0].lx) + 10, Y(0) + 4, `root ${rec.search.relaxation.toFixed(1)}`, 'lbl');
  // gradient key
  const gx = 18, gy = H - 22; body += text(gx, gy - 6, 'bound near the incumbent → far', 'lbl');
  for (let i = 0; i <= 10; i++) body += el('rect', {x: gx + i * 14, y: gy, width: 13, height: 8, fill: '--v-hi', 'fill-opacity': gapOpacity(i / 10)});
  body += el('circle', {cx: gx + 180, cy: gy + 4, r: 4.5, fill: '--v-canvas', stroke: '--v-muted', 'stroke-dasharray': '2 2'}) + text(gx + 188, gy + 8, 'pruned');
  body += el('path', {d: `M${gx + 244} ${gy}l8 8m0-8l-8 8`, stroke: '--v-s2', 'stroke-width': 1.8}) + text(gx + 258, gy + 8, 'infeasible');
  return svg(W, H, `Search tree for ${rec.document.path}`, body, 'tree');
}

// --------------------------------------------------------------------------- simulate

const STAGE_COLOURS = ['--v-hi', '--v-s2', '--v-s3'];
function stageColour(rec, stage) { const sellers = rec.stages; return STAGE_COLOURS[sellers.indexOf(stage) % 3]; }

export function timeline(rec) {
  const limit = Math.max(...Object.values(rec.limits)); const end = rec.clock;
  const W = 760, left = 90, right = 700; const X = lin(0, Math.max(limit, end), left, right);
  let body = '';
  // progress against target, one strip per stage above the timeline
  rec.stages.forEach((s, i) => {
    const y = 12 + i * 16, done = rec.spans.filter(p => p.stage === s).length, target = rec.targets[s] || 0;
    body += text(0, y + 9, s, 'lbl') + el('rect', {x: left, y, width: right - left, height: 10, rx: 2, fill: '--v-panel', stroke: '--v-line'});
    body += tag('g', {'data-progress': s, 'data-done': done, 'data-target': target},
      el('rect', {x: left, y, width: Math.max(0, (right - left) * Math.min(1, target ? done / target : 0)), height: 10, rx: 2, fill: stageColour(rec, s)}) +
      text(right + 4, y + 9, `${done}/${target}`, done < target ? 'bad' : 'ink') + title(`${s}: ${done} of ${target} this run`));
  });
  const base = 20 + rec.stages.length * 16;
  rec.stages.forEach((s, i) => {
    const y = base + 10 + i * 50; body += text(0, y + 20, s, 'lane') + el('path', {d: `M${left} ${y + 34}H${right}`, stroke: '--v-line'});
  });
  rec.spans.forEach(p => { const y = base + 10 + rec.stages.indexOf(p.stage) * 50;
    body += tag('rect', {x: X(p.start) + 0.4, y: y + 6, width: Math.max(0.7, X(p.end) - X(p.start) - 0.8), height: 24, rx: 2, fill: stageColour(rec, p.stage),
      'data-span': `${p.stage}:${p.unit}`, 'data-start': r2(p.start), 'data-end': r2(p.end)}, title(`${p.stage} unit ${p.unit}: ${p.start.toFixed(2)} to ${p.end.toFixed(2)} h`)); });
  const yb = base + 10 + rec.stages.length * 50;
  body += el('path', {d: `M${r2(X(limit))} ${base}V${yb}`, stroke: '--v-ink', 'stroke-width': 1.5}) + text(X(limit) - 4, base - 2, `limit ${limit} h`, 'ink', {'text-anchor': 'end'});
  for (const stop of rec.stops) if (stop.kind === 'stalled') {
    const why = Object.entries(stop.reasons).map(([s, r]) => `${s} ${r}`).join('; ');
    body += el('path', {d: `M${r2(X(stop.t))} ${base}V${yb}`, stroke: '--v-s2', 'stroke-width': 1.5, 'stroke-dasharray': '5 4'});
    body += tag('text', {x: X(stop.t) - 4, y: yb + 14, class: 'ink', 'text-anchor': 'end', 'data-stall': r2(stop.t)}, esc(`stalled at ${stop.t.toFixed(2)} h`)) + text(X(stop.t) - 4, yb + 28, why, 'lbl', {'text-anchor': 'end'});
  }
  const ay = yb + 38; body += el('path', {d: `M${left} ${ay}H${right}`, stroke: '--v-line'});
  for (let h = 0; h <= Math.max(limit, end); h += 5) body += text(X(h), ay + 15, String(h), 'lbl', {'text-anchor': 'middle'});
  body += text(right, ay + 30, 'work hours (one worker)', 'lbl', {'text-anchor': 'end'});
  return svg(W, ay + 38, `Worker timeline for ${rec.document.path}`, body, 'timeline');
}

export function laborSplit(rec) {
  const hours = {}; rec.spans.forEach(p => { hours[p.stage] = (hours[p.stage] || 0) + p.end - p.start; });
  const limit = Math.max(...Object.values(rec.limits));
  return {hours: Object.fromEntries(Object.entries(hours).map(([k, v]) => [k, r2(v)])), unused: r2(Math.max(0, limit - rec.clock)), limit};
}

// --------------------------------------------------------------------------- pack

export function glyphSheet(pack) {
  // Each card: the glyph at canvas size, its small-size fallback, the gate's name and family.
  const names = Object.keys(pack.gates).sort(); const cols = 6, cw = 124, chh = 134;
  let body = '';
  names.forEach((name, i) => {
    const g = pack.gates[name], x = 6 + (i % cols) * cw, y = 6 + Math.floor(i / cols) * chh;
    body += el('rect', {x, y, width: cw - 10, height: chh - 10, rx: 10, fill: '--v-panel', stroke: '--v-line'});
    body += tag('g', {transform: `translate(${x + 9} ${y + 6})`, fill: 'none', stroke: '--v-ink', 'stroke-width': 2, 'data-glyph': name}, g.glyph);
    body += text(x + 8, y + 88, name.toUpperCase(), 'ink');
    body += text(x + 8, y + 104, g.glyph_family === 'distinctive' ? 'shape' : 'IEC box', 'lbl');
    body += tag('g', {transform: `translate(${x + cw - 52} ${y + 90}) scale(0.4)`, fill: 'none', stroke: '--v-ink', 'stroke-width': 3}, g.glyph_small);
    body += text(x + cw - 32, y + 120, 'small', 'lbl', {'text-anchor': 'middle', 'font-size': 9});
  });
  const rows = Math.ceil(names.length / cols);
  // currentColor inside glyph markup follows the ink token
  return svg(cols * cw + 2, rows * chh + 8, 'Gate glyphs', tag('g', {style: 'color:var(--v-ink)'}, body), 'glyphs');
}

// --------------------------------------------------------------------------- views per record, page

export function viewsFor(rec) {
  if (rec.kind === 'logic') {
    const out = [];
    if (rec.levels.length) {
      out.push({name: 'level', title: `Level ${rec.levels[0]} and its readers`, svg: levelTrace(rec)});
      for (const r of rec.readers.filter(r => r.kind === 'hysteresis')) out.push({name: `loop-${r.gate}`, title: `Transfer loop of ${r.gate}`, svg: transferLoop(rec, r)});
    } else {
      out.push({name: 'timing', title: 'Timing', svg: timing(rec), html: eventLog(rec)});
      if (Object.keys(rec.buses).length) {
        // zoom on the longest transient burst, where glitches are
        const bus = Object.keys(rec.buses)[0]; const segs = busSegments(rec, bus, 0, rec.end).filter(s => s.transient);
        if (segs.length) {
          let best = segs[0], run = [segs[0]], bestRun = [segs[0]];
          for (let i = 1; i < segs.length; i++) { if (segs[i].t0 <= run[run.length - 1].t1 + 1) run.push(segs[i]); else run = [segs[i]]; if (run.length > bestRun.length) bestRun = [...run]; }
          best = bestRun[0]; const w = [Math.max(0, best.t0 - 6), Math.min(rec.end, bestRun[bestRun.length - 1].t1 + 10)];
          out.push({name: 'timing-zoom', title: `Timing, zoomed on the longest glitch (t ${w[0]}–${w[1]})`, svg: timing(rec, {window: w}), html: eventLog(rec, {window: w})});
        }
      }
    }
    return out;
  }
  if (rec.kind === 'optimize') return [
    ...rec.landscapes.map((L, i) => {
      const sliced = Object.keys(L.held).length > 0;
      return {name: sliced ? `landscape-${L.decisions[0]}-${L.decisions[1]}` : 'landscape',
        title: sliced ? `Landscape slice: ${L.decisions[0]} by ${L.decisions[1]}, ${Object.entries(L.held).map(([k, v]) => `${k} held at ${r2(v)}`).join(', ')}` : 'Landscape',
        svg: landscape(rec, L), html: i === rec.landscapes.length - 1 ? landscapeTable(rec) : undefined};
    }),
    {name: 'search-outline', title: 'Search outline', svg: searchOutline(rec)},
    {name: 'search-tree', title: 'Search tree', svg: searchTree(rec)},
  ];
  if (rec.kind === 'simulate') {
    const split = laborSplit(rec);
    const html = `<table class="sov-log"><thead><tr><th>run</th>${Object.keys(split.hours).map(s => `<th>${esc(s)} h</th>`).join('')}<th>unused h</th></tr></thead>` +
      `<tbody><tr><td>${esc(rec.document.path)}</td>${Object.values(split.hours).map(v => `<td class="num">${v}</td>`).join('')}<td class="num">${split.unused}</td></tr></tbody></table>`;
    return [{name: 'timeline', title: 'Worker timeline', svg: timeline(rec), html}];
  }
  throw new Error(`unknown record kind ${rec.kind}`);
}

export function page(records, heading = 'Run views') {
  const sections = records.map(rec => {
    const views = viewsFor(rec).map(v => `<figure><figcaption>${esc(v.title)}</figcaption><div class="stage">${v.svg}</div>${v.html ? `<div class="detail">${v.html}</div>` : ''}</figure>`).join('');
    return `<section><h2>${esc(rec.document.path)} <span class="kind">${esc(rec.kind)}</span></h2><p class="fp">${esc(rec.document.fingerprint)}</p>${views}</section>`;
  }).join('');
  const css = `:root{--bg:#F4F4F1;--ink:#171715;--muted:#6C6C65;--line:#D8D8D1;--panel:#fff;--bad:#eb6834;--hl:rgba(42,120,214,.16)}` +
    `@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#111315;--ink:#EEEFEA;--muted:#A8AAA4;--line:#3B3F42;--panel:#1C1F21;--bad:#d95926;--hl:rgba(57,135,229,.22)}}` +
    `:root[data-theme="dark"]{color-scheme:dark;--bg:#111315;--ink:#EEEFEA;--muted:#A8AAA4;--line:#3B3F42;--panel:#1C1F21;--bad:#d95926;--hl:rgba(57,135,229,.22)}` +
    `body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "IBM Plex Sans",ui-sans-serif,system-ui,sans-serif}` +
    `main{max-width:1000px;margin:0 auto;padding:32px 16px 64px;display:grid;gap:40px}section{display:grid;gap:18px}` +
    `h1{font-size:30px;margin:0}h2{font-size:20px;margin:0}.kind,.fp{font:12px ui-monospace,Menlo,monospace;color:var(--muted)}` +
    `figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;display:grid;gap:10px}figcaption{font-weight:600}` +
    `.stage{overflow-x:auto}.stage svg{display:block;width:100%;height:auto;border-radius:6px}.detail{overflow-x:auto;max-height:340px}` +
    `.sov-log{border-collapse:collapse;font:12.5px/1.4 ui-monospace,Menlo,monospace;width:100%}.sov-log th,.sov-log td{text-align:left;padding:4px 8px;border-bottom:1px solid var(--line);white-space:nowrap}` +
    `.sov-log th{color:var(--muted)}.sov-log td.num{text-align:right}.sov-log tr.bad td{color:var(--bad)}.sov-log tr.hl td{background:var(--hl)}`;
  const js = `document.addEventListener('pointerover',e=>{const t=e.target.closest('[data-link]');document.querySelectorAll('.hl').forEach(x=>x.classList.remove('hl'));` +
    `if(!t)return;document.querySelectorAll('[data-link="'+CSS.escape(t.dataset.link)+'"]').forEach(x=>x.classList.add('hl'));});`;
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(heading)}</title><style>${css}</style></head>` +
    `<body><main><h1>${esc(heading)}</h1>${sections}</main><script>${js}</script></body></html>\n`;
}

// --------------------------------------------------------------------------- CLI

function main(argv) {
  const args = argv.slice(2); const flag = n => { const i = args.indexOf(n); if (i < 0) return null; const v = args[i + 1]; args.splice(i, 2); return v; };
  const glyphs = args.includes('--glyphs'); if (glyphs) args.splice(args.indexOf('--glyphs'), 1);
  const out = flag('--out'), pagePath = flag('--page'), heading = flag('--title');
  if (glyphs) {
    const pack = JSON.parse(fs.readFileSync(path.join(HERE, '../packs/logic/gates.json'), 'utf8'));
    const file = path.join(out || '.', 'glyphs.svg'); fs.mkdirSync(path.dirname(file), {recursive: true});
    fs.writeFileSync(file, glyphSheet(pack).replace('class="sov-view"', 'class="sov-view standalone"') + '\n'); console.log(`wrote ${file}`);
    return 0;
  }
  if (!args.length) { console.error('usage: node scripts/plot_run.mjs run.json [...] (--out DIR | --page FILE) | --glyphs --out DIR'); return 2; }
  const records = args.map(f => ({file: f, rec: JSON.parse(fs.readFileSync(f, 'utf8'))}));
  if (out) {
    fs.mkdirSync(out, {recursive: true});
    for (const {file, rec} of records) for (const v of viewsFor(rec)) {
      const target = path.join(out, `${path.basename(file, '.json')}.${v.name}.svg`);
      // A standalone file follows the viewer's colour scheme on its own.
      fs.writeFileSync(target, v.svg.replace('class="sov-view"', 'class="sov-view standalone"') + '\n'); console.log(`wrote ${target}`);
    }
  }
  if (pagePath) { fs.writeFileSync(pagePath, page(records.map(r => r.rec), heading || 'Run views')); console.log(`wrote ${pagePath}`); }
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exit(main(process.argv));
