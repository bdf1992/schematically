#!/usr/bin/env node
// Builds Schematically's front door: a landing page, a gallery of delivered diagrams, and a
// getting-started page per agent. Node 18+ and nothing else.
//
//   node site/build.mjs [--out DIR] [--stage] [--skill-source SOURCE]
//
// Every gallery diagram is delivered here with bin/schematically.mjs, the same command a newcomer's
// agent runs, so the gallery shows what the command makes today. --stage marks the build as a
// private preview: every page and file is served with noindex and robots.txt refuses crawlers.
// --skill-source changes the source in every install command (default bdf1992/schematically, which
// installs from the default branch; a branch is https://github.com/bdf1992/schematically/tree/dev).
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const SITE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(SITE, '..');
const REPO = 'https://github.com/bdf1992/schematically';

const args = process.argv.slice(2);
const opt = name => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : null; };
const OUT = path.resolve(opt('--out') || path.join(SITE, '_build'));
const STAGE = args.includes('--stage');
const SOURCE = opt('--skill-source') || 'bdf1992/schematically';

const AGENTS = [
  {id: 'claude-code', name: 'Claude Code', dir: '.claude/skills/schematically',
    ask: 'Ask in plain words, or type <code>/schematically</code> followed by what to draw.',
    host: 'Claude Code in a terminal, the desktop app or an IDE extension'},
  {id: 'codex', name: 'Codex', dir: '.agents/skills/schematically',
    ask: 'Ask in plain words and name Schematically, so Codex picks the skill.',
    host: 'the Codex CLI or IDE extension'},
  {id: 'cursor', name: 'Cursor', dir: '.agents/skills/schematically',
    ask: 'Ask the Cursor agent in plain words and name Schematically.',
    host: 'Cursor\u2019s agent mode, which can run terminal commands'},
  {id: 'opencode', name: 'OpenCode', dir: '.agents/skills/schematically',
    ask: 'Ask in plain words and name Schematically.',
    host: 'OpenCode in a terminal'},
];
const installCmd = (agent, global) =>
  `npx skills add ${SOURCE} --skill schematically --agent ${agent} ${global ? '-g ' : ''}-y`;
const FIRST_PROMPT = 'Use Schematically to diagram a web request: the browser calls the API, the API checks Redis, and a cache miss reads PostgreSQL and fills the cache.';

const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
const write = (rel, text) => { const p = path.join(OUT, rel); fs.mkdirSync(path.dirname(p), {recursive: true}); fs.writeFileSync(p, text); };
const copy = (from, rel) => { const p = path.join(OUT, rel); fs.mkdirSync(path.dirname(p), {recursive: true}); fs.copyFileSync(from, p); };

const LOGO = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="2.5" y="6.5" width="7" height="11" rx="2" stroke="currentColor" stroke-width="1.6"/><rect x="14.5" y="6.5" width="7" height="11" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M9.5 12h5" stroke="var(--accent)" stroke-width="1.8"/><circle cx="9.5" cy="12" r="1.4" fill="var(--accent)"/><circle cx="14.5" cy="12" r="1.4" fill="var(--accent)"/></svg>`;

function page({title, description, base, current, body}) {
  const nav = [['index.html', 'Home', 'home'], ['gallery.html', 'Gallery', 'gallery'], ['start/index.html', 'Get started', 'start']];
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(description)}">
${STAGE ? '<meta name="robots" content="noindex,nofollow">\n' : ''}<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(description)}">
<link rel="icon" href="data:image/svg+xml,${encodeURIComponent(LOGO.replace(/var\(--accent\)/g, '#e8833a').replace(/currentColor/g, '#8a877f'))}">
<link rel="stylesheet" href="${base}site.css">
<script src="${base}site.js"></script>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="${base}index.html">${LOGO}<span>Schematically</span></a>
  <nav class="nav">
    ${nav.map(([href, label, key]) => `<a href="${base}${href}"${key === current ? ' aria-current="page"' : ''}${key === 'home' ? ' class="hide-s"' : ''}>${label}</a>`).join('\n    ')}
    <a href="${REPO}" class="hide-s">GitHub</a>
    <button class="iconbtn" id="theme" type="button" title="Switch light and dark">Light</button>
  </nav>
</div></header>
<main>
${body}
</main>
<footer><div class="wrap">
  <span>Schematically: describe a system, get an interactive diagram.</span>
  <span class="grow"></span>
  <a href="${base}gallery.html">Gallery</a>
  <a href="${base}start/index.html">Get started</a>
  <a href="${REPO}">Source on GitHub</a>
</div></footer>
</body>
</html>
`;
}

const codebox = text => `<div class="codebox"><pre class="code"><code>${esc(text)}</code></pre><button class="copy ghost" type="button" data-copy="${esc(text)}">Copy</button></div>`;

function deliverGallery() {
  const manifest = JSON.parse(fs.readFileSync(path.join(SITE, 'gallery.json'), 'utf8'));
  const cli = path.join(ROOT, 'bin', 'schematically.mjs');
  return manifest.examples.map(ex => {
    const source = path.join(SITE, 'gallery', `${ex.id}.sov`);
    const target = path.join(OUT, 'examples', `${ex.id}.html`);
    fs.mkdirSync(path.dirname(target), {recursive: true});
    let result;
    try {
      result = JSON.parse(execFileSync(process.execPath, [cli, 'deliver', source, target, '--json'], {encoding: 'utf8'}));
    } catch (error) {
      const shown = error.stdout || error.message;
      throw new Error(`deliver refused ${ex.id}.sov: ${shown}`);
    }
    copy(source, `examples/${ex.id}.sov`);
    const doc = JSON.parse(fs.readFileSync(source, 'utf8'));
    const sha = crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex');
    return {...ex, title: doc.meta.title, cards: result.components, wires: result.wires, bytes: result.bytes, sha};
  });
}

function thumb(id, base) {
  const dir = path.join(SITE, 'static', 'assets', 'thumbs');
  const has = theme => fs.existsSync(path.join(dir, `${id}.${theme}.png`));
  if (!has('dark') || !has('light')) return `<span class="muted" style="display:grid;place-items:center;height:100%">${esc(id)}</span>`;
  return `<img class="t-dark" src="${base}assets/thumbs/${id}.dark.png" alt="" loading="lazy"><img class="t-light" src="${base}assets/thumbs/${id}.light.png" alt="" loading="lazy">`;
}

function galleryCard(ex, base) {
  const kb = Math.round(ex.bytes / 1024);
  return `<article class="card glass">
  <a class="thumb" href="${base}examples/${ex.id}.html" aria-label="Open ${esc(ex.title)}">${thumb(ex.id, base)}</a>
  <div class="body">
    <div class="kind">${esc(ex.kind)}</div>
    <h3>${esc(ex.title)}</h3>
    <p class="said">${esc(ex.prompt)}</p>
    <p>${esc(ex.blurb)}</p>
    <div class="meta">${ex.cards} cards · ${ex.wires} wires · ${kb} KB · checked and laid out by deliver · sha256 ${ex.sha.slice(0, 12)}</div>
    <div class="links">
      <a class="open" href="${base}examples/${ex.id}.html">Open the diagram</a>
      <a href="${base}examples/${ex.id}.sov" download>${esc(ex.id)}.sov</a>
    </div>
  </div>
</article>`;
}

function landing(gallery) {
  const hero = gallery.find(g => g.id === 'web-request') || gallery[0];
  const body = `
<div class="wrap hero">
  <div class="eyebrow">An agent skill for Claude Code, Codex, Cursor and OpenCode</div>
  <h1>Describe a system.<br><span class="accent">Get an interactive diagram.</span></h1>
  <p class="lead">Tell your coding agent what you want to see in one sentence. It writes a small, checked model of the cards and wires, and hands you one HTML file you can search, trace, route and share. It opens from disk, offline, in any browser.</p>
  <div class="cmd glass"><code>npx skills add ${esc(SOURCE)} --skill schematically</code><button class="copy" type="button" data-copy="npx skills add ${esc(SOURCE)} --skill schematically">Copy</button></div>
  <div class="ctas">
    <a class="btn primary" href="start/index.html">Get started</a>
    <a class="btn" href="#walkthrough">Watch the 35-second walkthrough</a>
    <a class="btn" href="gallery.html">See the gallery</a>
  </div>
  <div class="works">Works with <a href="start/claude-code.html">Claude Code</a> · <a href="start/codex.html">Codex</a> · <a href="start/cursor.html">Cursor</a> · <a href="start/opencode.html">OpenCode</a>. Needs Node 18 or newer, nothing else.</div>

  <div class="live glass">
    <div class="bar"><span class="dot"></span><span class="grow">${esc(hero.id)}.html, the real delivered file. Click a card, then press <kbd>d</kbd> to trace what it reaches.</span><a href="examples/${hero.id}.html">Open full screen ↗</a></div>
    <div class="prompt-line"><b>Asked:</b> ${esc(hero.prompt)}</div>
    <iframe data-viewer="examples/${hero.id}.html" src="examples/${hero.id}.html" title="${esc(hero.title)}" loading="eager"></iframe>
  </div>
</div>

<section id="walkthrough"><div class="wrap">
  <div class="eyebrow">35 seconds</div>
  <h2>One sentence in, one file out.</h2>
  <p class="lead">The agent writes the model, the command checks it and lays it out, and the reader explores it: what a card reaches, what reaches it, and the route between two cards.</p>
  <div class="film glass"><video src="assets/walkthrough.mp4" poster="assets/walkthrough-poster.png" controls muted loop playsinline preload="metadata"></video></div>
</div></section>

<section><div class="wrap">
  <div class="eyebrow">How it works</div>
  <h2>Three steps, and only the first is yours to type.</h2>
  <div class="steps">
    <div class="step glass"><div class="n">01 Install</div><p>Add the skill to your agent once. It brings the checker, the layout engine and the viewer; Node is the only requirement.</p><pre class="code">npx skills add ${esc(SOURCE)} \\
  --skill schematically</pre></div>
    <div class="step glass"><div class="n">02 Describe</div><p>Say what to draw. No repository needed: a request path, a pipeline, a process or a plan.</p><pre class="code">${esc(FIRST_PROMPT)}</pre></div>
    <div class="step glass"><div class="n">03 Open</div><p>The agent writes <code>web-request.sov</code>, runs one command, and opens the HTML it delivered.</p><pre class="code">node bin/schematically.mjs deliver \\
  web-request.sov --open --json
{"ok":true,"components":4,"wires":3,
 "laidOut":true}</pre></div>
  </div>
</div></section>

<section><div class="wrap">
  <div class="eyebrow">What the reader gets</div>
  <h2>A diagram you can question, not a picture.</h2>
  <div class="grid">
    <div class="feat glass"><h3>Downstream and upstream</h3><p>Click a card and press <kbd>d</kbd> to light everything it reaches, or <kbd>u</kbd> for everything that reaches it.</p></div>
    <div class="feat glass"><h3>Route between two cards</h3><p>Press <kbd>r</kbd> and pick a second card: the shortest directed route lights up and is spelled out.</p></div>
    <div class="feat glass"><h3>Search</h3><p>Press <kbd>/</kbd> and type part of a name to jump to a card and read its note.</p></div>
    <div class="feat glass"><h3>One file, offline</h3><p>About 500 KB, asks the network for nothing, opens from disk. Mail it, commit it, attach it.</p></div>
    <div class="feat glass"><h3>Light, dark, PNG, print</h3><p>Press <kbd>t</kbd> for the theme. Save a PNG or print to PDF from the toolbar.</p></div>
    <div class="feat glass"><h3>Links that keep the view</h3><p>The address remembers the card, the trace and the theme, so a link opens exactly what you saw.</p></div>
    <div class="feat glass"><h3>Checked before it ships</h3><p>The model is validated by the same data core as the Schematically editor. A failed check names the record and keeps the last good file.</p></div>
    <div class="feat glass"><h3>Laid out for you</h3><p>The agent writes no coordinates. A layered layout places cards along the wires, left to right.</p></div>
    <div class="feat glass"><h3>Meaning, not just boxes</h3><p>Stores, gates, observers, receipts and permissions are different card types; wires carry direction and read or write.</p></div>
  </div>
</div></section>

<section><div class="wrap">
  <div class="eyebrow">Gallery</div>
  <h2>Delivered by the same command.</h2>
  <p class="lead">Each example is the sentence that was asked, the <code>.sov</code> the agent wrote, and the HTML that deliver produced from it.</p>
  <div class="cards">${gallery.slice(0, 4).map(ex => galleryCard(ex, '')).join('\n')}</div>
  <div class="ctas" style="margin-top:22px"><a class="btn" href="gallery.html">All ${gallery.length} examples</a></div>
</div></section>

<section><div class="wrap">
  <div class="eyebrow">Get started</div>
  <h2>Pick your agent.</h2>
  <div class="agents">${AGENTS.map(a => `<a class="agent glass" href="start/${a.id}.html"><b>${esc(a.name)}</b><span>Install, first prompt, checks</span></a>`).join('')}</div>
</div></section>
`;
  return page({title: 'Schematically: describe a system, get an interactive diagram', base: '', current: 'home',
    description: 'An agent skill that turns one sentence into a checked, interactive HTML diagram you can search, trace and share.', body});
}

function galleryPage(gallery) {
  const body = `
<div class="wrap hero">
  <div class="eyebrow">Gallery</div>
  <h1>Every example, delivered.</h1>
  <p class="lead">Each card below is the sentence an agent was given, the <code>.sov</code> it wrote, and the interactive HTML that <code>bin/schematically.mjs deliver</code> made from it when this site was built. Open one and click a card, then press <kbd>d</kbd>, <kbd>u</kbd> or <kbd>r</kbd>.</p>
  <div class="cards">${gallery.map(ex => galleryCard(ex, '')).join('\n')}</div>
</div>`;
  return page({title: 'Gallery · Schematically', base: '', current: 'gallery',
    description: 'Interactive diagrams delivered by Schematically, each with the sentence that asked for it and its .sov source.', body});
}

function startIndex() {
  const body = `
<div class="wrap hero doc">
  <div class="eyebrow">Get started</div>
  <h1>Your first diagram in two minutes.</h1>
  <p class="lead">Schematically is a skill: a folder your agent reads, with one command it runs. Choose the agent you use.</p>
  <div class="agents" style="grid-template-columns:repeat(2,1fr)">${AGENTS.map(a => `<a class="agent glass" href="${a.id}.html"><b>${esc(a.name)}</b><span>${esc(a.host)}</span></a>`).join('')}</div>
  <h2>What every agent needs</h2>
  <ul>
    <li><b>Node 18 or newer.</b> <code>node --version</code> prints it. Nothing else is installed: no Python, no browser engine, no packages.</li>
    <li><b>An agent that can write files and run commands.</b> The skill writes a <code>.sov</code> file next to your work and runs <code>node</code> on it.</li>
  </ul>
  <h2>Try it without an agent</h2>
  <p>The skill's command has a demo that writes a four-card example and delivers it:</p>
  ${codebox('npx skills add ' + SOURCE + ' --skill schematically -g -y\nnode ~/.claude/skills/schematically/bin/schematically.mjs demo --open')}
  <p>The path in the second line is where Claude Code keeps global skills; for Codex, Cursor and OpenCode it is <code>~/.agents/skills/schematically</code>.</p>
</div>`;
  return page({title: 'Get started · Schematically', base: '../', current: 'start',
    description: 'Install the Schematically skill for Claude Code, Codex, Cursor or OpenCode and deliver your first diagram.', body});
}

function startAgent(agent) {
  const tabs = AGENTS.map(a => `<a href="${a.id}.html"${a.id === agent.id ? ' aria-current="page"' : ''}>${esc(a.name)}</a>`).join('');
  const body = `
<div class="wrap hero doc">
  <div class="eyebrow">Get started · ${esc(agent.name)}</div>
  <h1>Schematically in ${esc(agent.name)}</h1>
  <p class="lead">For ${esc(agent.host)}. You need Node 18 or newer; check with <code>node --version</code>.</p>
  <nav class="tabs" aria-label="Agent">${tabs}</nav>

  <h2>1. Install the skill</h2>
  <p>For every project on this machine:</p>
  ${codebox(installCmd(agent.id, true))}
  <p>Or for this project only, run from the project folder (the skill is then a folder you can commit):</p>
  ${codebox(installCmd(agent.id, false))}
  <table class="t">
    <tr><th>Installed to</th><td><code>~/${esc(agent.dir)}</code> for every project, or <code>${esc(agent.dir)}</code> inside the project</td></tr>
    <tr><th>Contains</th><td><code>SKILL.md</code> (what your agent reads), <code>bin/schematically.mjs</code> (the command), the data core it checks with, and the viewer</td></tr>
  </table>
  <p>Start a new ${esc(agent.name)} session afterwards so it sees the skill.</p>

  <h2>2. Ask for a diagram</h2>
  <p>${agent.ask} For example:</p>
  ${codebox(FIRST_PROMPT)}
  <p>Then keep going in the same conversation: <i>add authentication in front of the API</i>, <i>the cache is optional</i>, <i>mark the database as the source of truth</i>. Each change edits the same <code>.sov</code> and delivers again.</p>

  <h2>3. What happens</h2>
  <ol>
    <li>The agent writes <code>web-request.sov</code> in your working folder: cards, the wires between them, a short note on each. No coordinates.</li>
    <li>It runs <code>node ~/${esc(agent.dir)}/bin/schematically.mjs deliver web-request.sov --open --json</code>.</li>
    <li>The command checks the model, lays it out and writes <code>web-request.html</code> beside it, then opens it. It prints <code>{"ok": true, ...}</code>.</li>
    <li>If the check fails it prints <code>{"ok": false, "diagnostics": [...]}</code> naming each record and what is wrong; the agent repairs those records and runs again. A failed run never overwrites the last good HTML.</li>
  </ol>
  <div class="note"><b>Check that it worked</b> without involving the agent: <code>node ~/${esc(agent.dir)}/bin/schematically.mjs demo --open</code> writes and opens a four-card example in <code>./schematically-demo</code>.</div>

  <h2>Update or remove</h2>
  ${codebox(`npx skills update schematically -g -y\nnpx skills remove schematically --agent ${agent.id} -g -y`)}

  <h2>If something goes wrong</h2>
  <table class="t">
    <tr><th>What you see</th><th>What to do</th></tr>
    <tr><td><code>node: command not found</code></td><td>Install Node 18 or newer from nodejs.org, then open a new terminal.</td></tr>
    <tr><td>The agent draws with something else</td><td>Name it: <i>use Schematically to…</i>. If it still does not, the skill is not loaded: start a new session, or check that <code>SKILL.md</code> exists under the folder above.</td></tr>
    <tr><td><code>"ok": false</code> twice in a row</td><td>The skill tells the agent to stop and show you the diagnostics. Each names a record id and the problem; most are a wire pointing at an id that does not exist.</td></tr>
    <tr><td>Windows path errors</td><td>Pass Windows paths (<code>C:\\...</code>) to <code>node</code>; the skill says so to the agent.</td></tr>
  </table>
  <p style="margin-top:28px"><a class="btn primary" href="../gallery.html">See what others asked for</a></p>
</div>`;
  return page({title: `${agent.name} · Get started · Schematically`, base: '../', current: 'start',
    description: `Install the Schematically skill in ${agent.name} and deliver your first interactive diagram.`, body});
}

function main() {
  fs.rmSync(OUT, {recursive: true, force: true});
  fs.mkdirSync(OUT, {recursive: true});
  const gallery = deliverGallery();
  const staticDir = path.join(SITE, 'static');
  for (const entry of fs.readdirSync(staticDir, {recursive: true, withFileTypes: true})) {
    if (!entry.isFile()) continue;
    const from = path.join(entry.parentPath || entry.path, entry.name);
    copy(from, path.relative(staticDir, from));
  }
  write('index.html', landing(gallery));
  write('gallery.html', galleryPage(gallery));
  write('start/index.html', startIndex());
  for (const agent of AGENTS) write(`start/${agent.id}.html`, startAgent(agent));
  if (STAGE) {
    write('_headers', '/*\n  X-Robots-Tag: noindex, nofollow\n');
    write('robots.txt', 'User-agent: *\nDisallow: /\n');
  }
  const commit = (() => { try { return execFileSync('git', ['rev-parse', 'HEAD'], {cwd: ROOT, encoding: 'utf8'}).trim(); } catch { return null; } })();
  write('build.json', JSON.stringify({commit, stage: STAGE, skillSource: SOURCE,
    examples: gallery.map(({id, cards, wires, bytes, sha}) => ({id, cards, wires, bytes, sha}))}, null, 2) + '\n');
  console.log(JSON.stringify({ok: true, out: OUT, stage: STAGE, examples: gallery.length, pages: 3 + AGENTS.length}));
}

main();
