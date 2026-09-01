from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'index.source.html').read_text();model=(ROOT/'src/10-model.js').read_text();canvas=(ROOT/'src/30-canvas.js').read_text();render=(ROOT/'src/55-render.js').read_text()
assert '3D · Volume' not in html and '<option value="volume">' not in html
assert 'componentIsPoint' in model and 'componentIsPath' in model
assert "kind:'path'" in canvas and "kind:'edge'" in canvas
assert 'dimensional-point-body' in render and 'dimensional-path-body' in render
print('DIMENSIONAL FORM PASS')
