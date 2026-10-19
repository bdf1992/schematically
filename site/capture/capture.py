#!/usr/bin/env python3
"""Capture the front door's pictures from a built site: gallery thumbnails, the README hero and
the walkthrough film. A maintainer's tool, run after `node site/build.mjs`; the site build itself
needs Node only and uses what this writes.

    python site/capture/capture.py [--only thumbs|hero|film] [--fps 24]

Needs Playwright with Chromium, Pillow, and ffmpeg with libx264 for the MP4. Writes:
  site/static/assets/thumbs/<id>.<dark|light>.png   gallery thumbnails
  docs/assets/readme-hero.<dark|light>.png          the README picture
  site/static/assets/walkthrough.mp4 and walkthrough-poster.png
  docs/assets/walkthrough.gif                        the README's moving version

The film is stepped, not recorded: site/capture/walkthrough.html exposes seek(t), and every frame
is a screenshot taken after seek, so it does not depend on how fast this machine is.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import io
import json
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parent
BUILD = SITE / '_build'
THUMBS = SITE / 'static' / 'assets' / 'thumbs'
ASSETS = SITE / 'static' / 'assets'
DOCS = ROOT / 'docs' / 'assets'


def serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass
    handler = functools.partial(Quiet, directory=str(directory))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{server.server_address[1]}'


def open_viewer(page, url: str) -> None:
    page.goto('about:blank')  # a change of fragment alone would keep the old page and its zoom
    page.goto(url)
    page.wait_for_function('window.SovViewer && SovViewer.data && document.querySelector("#stage svg")')
    page.wait_for_timeout(150)


def save_png(raw: bytes, out: Path, width: int | None = None) -> None:
    image = Image.open(io.BytesIO(raw)).convert('RGB')
    if width and image.width > width:
        image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, optimize=True)


def thumbs(browser, base: str) -> None:
    examples = json.loads((SITE / 'gallery.json').read_text(encoding='utf-8'))['examples']
    page = browser.new_page(viewport={'width': 1600, 'height': 820}, device_scale_factor=1)
    for example in examples:
        for theme in ('dark', 'light'):
            open_viewer(page, f'{base}/examples/{example["id"]}.html#theme={theme}')
            save_png(page.locator('#stage').screenshot(), THUMBS / f'{example["id"]}.{theme}.png', width=1120)
    page.close()


def hero(browser, base: str) -> None:
    page = browser.new_page(viewport={'width': 1440, 'height': 720}, device_scale_factor=1)
    for theme in ('dark', 'light'):
        open_viewer(page, f'{base}/examples/web-request.html#focus=api&mode=down&theme={theme}')
        # The card panel opens on the right; zoom out a step and pan left so it covers no card.
        page.keyboard.press('-')
        page.mouse.move(720, 400)
        page.mouse.down()
        page.mouse.move(560, 400, steps=8)
        page.mouse.up()
        page.wait_for_timeout(100)
        save_png(page.screenshot(), DOCS / f'readme-hero.{theme}.png')
    page.close()


def write_gif(frames: Path, count: int, fps: int, out: Path, gif_fps: int = 10, width: int = 880) -> None:
    """One palette for the whole film, taken from frames across it, so colours do not flicker."""
    step = fps / gif_fps
    picks = [round(i * step) for i in range(int(count / step))]
    def load(i: int) -> Image.Image:
        image = Image.open(frames / f'{i:05d}.png').convert('RGB')
        return image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    samples = [load(i) for i in picks[:: max(1, len(picks) // 12)]]
    sheet = Image.new('RGB', (width, samples[0].height * len(samples)))
    for n, image in enumerate(samples):
        sheet.paste(image, (0, n * image.height))
    palette = sheet.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    images = [load(i).quantize(palette=palette, dither=Image.Dither.NONE) for i in picks]
    images[0].save(out, save_all=True, append_images=images[1:], duration=round(1000 / gif_fps), loop=0, optimize=True)


def film(browser, base: str, fps: int) -> None:
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise SystemExit('ffmpeg is needed for the film')
    page = browser.new_page(viewport={'width': 1440, 'height': 810}, device_scale_factor=1)
    page.goto(f'{base}/capture/walkthrough.html')
    page.evaluate('window.ready')
    duration = page.evaluate('window.DURATION')
    with tempfile.TemporaryDirectory() as tmp:
        frames = Path(tmp)
        count = int(duration * fps)
        for i in range(count):
            page.evaluate(f'seek({i / fps})')
            (frames / f'{i:05d}.png').write_bytes(page.screenshot())
        ASSETS.mkdir(parents=True, exist_ok=True)
        mp4 = ASSETS / 'walkthrough.mp4'
        subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', str(frames / '%05d.png'),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '24', '-preset', 'slow',
                        '-movflags', '+faststart', str(mp4)], check=True)
        shutil.copy(frames / f'{int(23.0 * fps):05d}.png', ASSETS / 'walkthrough-poster.png')
        DOCS.mkdir(parents=True, exist_ok=True)
        write_gif(frames, count, fps, DOCS / 'walkthrough.gif')
    page.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--only', choices=['thumbs', 'hero', 'film'])
    parser.add_argument('--fps', type=int, default=24)
    args = parser.parse_args()
    if not (BUILD / 'index.html').exists():
        raise SystemExit('build the site first: node site/build.mjs')
    with tempfile.TemporaryDirectory() as tmp:
        # Serve the built site with the capture stage beside it, so the stage's ../examples resolve.
        stage = Path(tmp) / 'site'
        shutil.copytree(BUILD, stage)
        shutil.copytree(SITE / 'capture', stage / 'capture')
        server, base = serve(stage)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                if args.only in (None, 'thumbs'):
                    thumbs(browser, base)
                if args.only in (None, 'hero'):
                    hero(browser, base)
                if args.only in (None, 'film'):
                    film(browser, base, args.fps)
                browser.close()
        finally:
            server.shutdown()
    print(json.dumps({'ok': True, 'only': args.only}))


if __name__ == '__main__':
    main()
