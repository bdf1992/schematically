# The front door

The public site for Schematically: a landing page, a gallery of delivered diagrams, and a
getting-started page per agent (Claude Code, Codex, Cursor, OpenCode).

```bash
node site/build.mjs                 # writes site/_build/
node site/build.mjs --stage         # the same, marked noindex for a private preview
```

The build needs Node 18 or newer and nothing else. It delivers every example in `gallery/` with
`bin/schematically.mjs deliver`, the command a newcomer's agent runs, so the gallery always shows
what that command makes today. `gallery.json` holds each example's sentence (what was asked), its
kind and one line about it; `gallery/<id>.sov` is what an agent writes from that sentence.
`--skill-source` changes the source in every install command, for example
`https://github.com/bdf1992/schematically/tree/dev` while the skill has not reached `main`.

| Path | What it is |
| --- | --- |
| `build.mjs` | The pages, written from data in one file. |
| `gallery.json`, `gallery/*.sov` | The examples. Add one by adding both. |
| `static/` | Stylesheet, page script, and the pictures `capture/` makes. Copied as is. |
| `capture/capture.py` | Maintainer's tool: gallery thumbnails, the README hero, and the walkthrough film. |
| `capture/walkthrough.html` | The film's stage. It exposes `seek(t)`; every frame is a screenshot after a seek. |

## Pictures

```bash
node site/build.mjs && python site/capture/capture.py
```

`capture.py` needs Playwright with Chromium, Pillow, and ffmpeg with libx264. It writes
`static/assets/thumbs/<id>.<dark|light>.png`, `static/assets/walkthrough.mp4` with its poster,
and, for the repository README, `docs/assets/readme-hero.<dark|light>.png` and
`docs/assets/walkthrough.gif`. Run it again after changing an example, the viewer or the film.
`--only thumbs|hero|film` runs one part.

## Staging and publishing

The site is hosted on the Cloudflare Pages project `schematically`. A preview deploy:

```bash
node site/build.mjs --stage
npx wrangler pages deploy site/_build --project-name schematically --branch <name>
```

A preview is served at an unlisted address, with `noindex` on every page and file and a
`robots.txt` that refuses crawlers. It is not behind a login: Cloudflare Access on the project
would add one. Publishing to the project's production address is a deploy from `--branch main`
of a build without `--stage`.

`tests/site_qa.py` builds the site twice and checks every example, every link and every install
command.
