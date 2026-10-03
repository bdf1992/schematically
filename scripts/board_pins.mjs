#!/usr/bin/env node
// Board pins: put live sessions and pinned notes on a Work Engine mission document.
//
//   node scripts/board_pins.mjs <mission.sov> <sessions.json> [--out <file>] [--neutral]
//
// <mission.sov> is what `ws schematically project <mission> --out <file>` writes: one card per
// task (config.status from the Work Engine notation, config.waitsOn when the task waits on
// someone), one reading-only group per case, and a "depends on" Wire per dependency.
// <sessions.json> is `ws session list --json`.
//
// The script adds, without moving any card the projection placed:
//   - one session piece per live session (not ended, not stale) bound to a task that is a card
//     in the document, placed in a column left of the board, level with its task, and wired from
//     its out port to the task's in port ("works on");
//   - one pinned note per Component whose config.waitsOn is not empty: a Point in a column right
//     of the board, a little above the Component, its label the waiting text, wired to the
//     Component's top (control) port with the caption "waits on".
// Dev has no reference kind for anchored text (references carry `notation` and `scenario`
// only, and nothing draws a reference with a target), so the note is a captioned Point and a
// Wire, as docs/workengine/BOARD-STUDY.md records.
//
// --neutral replaces every task id with t01, t02, ... (in the projection's component order),
// every session id with s01, s02, ..., and drops what names a machine: the projection's
// per-field basis paths become tasks/<tNN>.json#<field>, and a session piece carries only its
// seat. Titles are kept. The result is written as canonical JSON (indent 1, LF), the same shape
// the projection writes.
import fs from 'node:fs';

function usage(message) {
  if (message) process.stderr.write(`board_pins: ${message}\n`);
  process.stderr.write('usage: node scripts/board_pins.mjs <mission.sov> <sessions.json> [--out <file>] [--neutral]\n');
  process.exit(2);
}

function parseArgs(argv) {
  const out = {positional: [], out: null, neutral: false};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') { out.out = argv[++i]; if (!out.out) usage('--out needs a file'); }
    else if (a === '--neutral') out.neutral = true;
    else if (a.startsWith('--')) usage(`unknown flag ${a}`);
    else out.positional.push(a);
  }
  if (out.positional.length !== 2) usage('two inputs are required');
  return out;
}

const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^﻿/, ''));
const clone = value => JSON.parse(JSON.stringify(value));

const CARD_W = 112, COLUMN_GAP = 258, NOTE_LIFT = 70;

function cardPorts() {
  const port = flow => ({face: 'external', label: '', connectionCount: 1, activeConnection: 0,
    connections: [{id: 'connection-1', colorSlot: 0, flow, access: 'read-write'}]});
  return {in: port('in'), out: port('out'), control: port('control')};
}

const SURFACE_FORM = {body: {kind: 'surface', material: 'generic', thickness: 0}, dimension: 2,
  frame: {mode: 'none', thickness: 0, depth: 0}, regions: {interior: {state: 'closed'}}};
const POINT_FORM = {dimension: 0, body: {kind: 'point', material: 'generic', thickness: 0},
  frame: {mode: 'none', thickness: 0, depth: 0}, regions: {interior: {state: 'closed'}}};
const PATH_FORM = {dimension: 1, body: {kind: 'path', material: 'generic', thickness: 0}};

function wire(id, a, aSide, aPoint, b, bSide, bPoint, label) {
  return {a, aSide, b, bSide, config: {label, forwardOperation: 'none', reverseOperation: 'none'}, id,
    aAttachment: {kind: 'attachment-ref', componentId: a, pointId: aPoint},
    bAttachment: {kind: 'attachment-ref', componentId: b, pointId: bPoint},
    form: clone(PATH_FORM), role: 'carrier', canvasId: 'canvas:global'};
}

// A session is live while it has not ended and is not stale. A subagent session has no process
// of its own (`process: absent`), so the process field alone would drop every contract engineer.
const isLive = s => s && !s.ended && !s.stale && typeof s.task === 'string' && s.task;

function waitingText(entry) {
  const label = String(entry?.label || '').trim();
  return label || `${entry?.kind || 'someone'} ${entry?.id || ''}`.trim();
}

export function pin(doc, sessions) {
  const out = clone(doc);
  const cards = out.components.filter(c => c.symbolId !== 'group');
  const byId = new Map(cards.map(c => [c.id, c]));
  const xs = cards.map(c => Number(c.x) || 0);
  const left = Math.min(0, ...xs) - COLUMN_GAP, right = Math.max(0, ...xs) + COLUMN_GAP;
  const added = {sessions: [], notes: []};

  const live = (Array.isArray(sessions) ? sessions : []).filter(isLive).filter(s => byId.has(s.task))
    .sort((p, q) => String(p.started || '').localeCompare(String(q.started || '')) || String(p.id).localeCompare(String(q.id)));
  const perTask = new Map();
  for (const s of live) {
    const task = byId.get(s.task), k = perTask.get(s.task) || 0;
    perTask.set(s.task, k + 1);
    const id = `session-${s.id}`;
    out.components.push({
      config: {label: `${s.seat || 'agent'} session`, subtitle: s.process === 'live' ? 'live · own process' : 'live · subagent',
        ports: cardPorts(), presentation: {size: {w: CARD_W, h: 84}}},
      id, symbolId: 'act', form: clone(SURFACE_FORM), x: left - k * 150, y: Number(task.y) || 0,
    });
    out.wires.push(wire(`works-${s.id}`, id, 'out', 'right', task.id, 'in', 'left', 'works on'));
    added.sessions.push({session: s.id, task: s.task});
  }

  for (const c of cards) {
    const waits = Array.isArray(c.config?.waitsOn) ? c.config.waitsOn : [];
    if (!waits.length) continue;
    const id = `note-${c.id}`, text = waits.map(waitingText).join('; ');
    out.components.push({
      id, symbolId: 'point', x: right, y: (Number(c.y) || 0) - NOTE_LIFT, form: clone(POINT_FORM),
      config: {label: `Waits on ${text}`, presentation: {graphic: {kind: 'none'}, labelMode: 'outside', backdrop: 'none'}},
    });
    out.wires.push(wire(`pin-${c.id}`, id, 'out', 'self', c.id, 'control', 'top', 'waits on'));
    added.notes.push({component: c.id, text});
  }
  return {doc: out, added};
}

export function neutralize(doc, sessions) {
  const taskIds = doc.components.filter(c => c.symbolId !== 'group' && !c.id.startsWith('session-') && !c.id.startsWith('note-')).map(c => c.id);
  const sessionIds = (Array.isArray(sessions) ? sessions : []).map(s => String(s.id || '')).filter(Boolean);
  const map = new Map();
  taskIds.forEach((id, i) => map.set(id, `t${String(i + 1).padStart(2, '0')}`));
  let n = 0;
  for (const id of sessionIds) if (doc.components.some(c => c.id === `session-${id}`)) map.set(id, `s${String(++n).padStart(2, '0')}`);
  const out = clone(doc);
  // The projection's per-field basis names each task's control file; keep the field and the
  // basis, point it at the neutral id.
  const basis = out.meta?.basis || {};
  for (const [key, fields] of Object.entries(basis)) {
    for (const field of Object.values(fields || {})) {
      if (!field || typeof field !== 'object') continue;
      const fix = from => String(from).replace(/^control\/tasks\//, 'tasks/');
      if (Array.isArray(field.from)) field.from = field.from.map(fix); else if (field.from) field.from = fix(field.from);
    }
    void key;
  }
  if (out.meta?.source) delete out.meta.source.revision;
  let text = JSON.stringify(out);
  // Longest first, so an id that is a prefix of another is not replaced inside it.
  for (const [from, to] of [...map.entries()].sort((p, q) => q[0].length - p[0].length)) text = text.split(from).join(to);
  return JSON.parse(text);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const [docFile, sessionsFile] = args.positional;
  const doc = readJson(docFile), sessions = readJson(sessionsFile);
  if (!Array.isArray(doc.components) || !Array.isArray(doc.wires)) usage(`${docFile} is not a document with components and wires`);
  let {doc: result, added} = pin(doc, sessions);
  if (args.neutral) result = neutralize(result, sessions);
  const text = JSON.stringify(result, null, 1) + '\n';
  if (args.out) fs.writeFileSync(args.out, text, 'utf8'); else process.stdout.write(text);
  process.stderr.write(`board_pins: ${added.sessions.length} session piece(s), ${added.notes.length} pinned note(s)${args.neutral ? ', neutral ids' : ''}\n`);
}

main();
