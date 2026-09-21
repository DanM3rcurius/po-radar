"""Regenerate docs/demo/index.html from src/poradar/static/radar.html + sample_results.json."""
import json
import pathlib

ROOT = pathlib.Path("/home/user/po-radar")
RADAR = ROOT / "src/poradar/static/radar.html"
SAMPLE = ROOT / "docs/demo/sample_results.json"
OUT = ROOT / "docs/demo/index.html"

html = RADAR.read_text(encoding="utf-8")
results = json.loads(SAMPLE.read_text(encoding="utf-8"))
payload = json.dumps(results, indent=2, ensure_ascii=False).replace("</", "<\\/")

embed = (
    '<script id="poradar-embedded">\n'
    "/* Static demo: fixture data, no server, no network. Regenerate with the\n"
    "   build_demo script so this file stays byte-identical to radar.html's main script. */\n"
    "window.PORADAR_EMBEDDED = " + payload + ";\n"
    'window.PORADAR_BANK = "provisional";\n'
    'window.PORADAR_GENERATED = "2026-09-21T15:10:00+00:00";\n'
    "</script>\n"
)

anchor = '<script id="poradar-main">'
assert anchor in html, "radar.html lost its main script id"
out = html.replace(anchor, embed + anchor, 1)
out = out.replace(
    "<title>Psyop Radar</title>",
    "<title>Psyop Radar — static demo</title>",
    1,
)
OUT.write_text(out, encoding="utf-8")
print("wrote", OUT, len(out), "bytes")
