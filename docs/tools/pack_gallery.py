# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""In the Wild gallery: the best SCALE4D 140k cases as embedded motion-viewer pages, plus card thumbnails.

Input: the published folder of the gallery site (motion_seg.py export; built by
/bigtemp/rqa8sm/scale4d_gallery_20261112/build.py with the exact settings of the paper renders, input inset on)
and the paper renders (/bigtemp/rqa8sm/paperfig_20261111/renders_final, wild_final.py).

    python tools/pack_gallery.py [PUBLISH_DIR]    -> assets/gallery/{index.html, data/, thumbs/, cases.json}

index.html is the published viewer with an embed mode (?embed): no title, case menu or settings panel, English
tooltips. Everything drawn is the model's prediction; no ground truth."""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parents[1]
PUB = Path(sys.argv[1] if len(sys.argv) > 1 else "/bigtemp/rqa8sm/scale4d_gallery_20261112/site/motion/publish")
RENDERS = Path("/bigtemp/rqa8sm/paperfig_20261111/renders_final")
OUT = HERE / "assets" / "gallery"

# (clip id in the published folder, render key, kind, setup) in page order
CASES = [
    ("adtmv8__multiuser_meal_seq137_7__f0048_0095", "adtmv8__multiuser_meal_seq137_7__f0048_0095@10,-6,0.6,0",
     "Egocentric", "3 views, cameras"),
    ("agibot__392_672634", "agibot__392_672634", "Robot", "3 views, cameras"),
    ("wild2_rollerblade--ours", "rollerblade", "Person", "1 view, RGB only"),
    ("droid__tri_2024-01-11-14h-29m-31s", "droid__tri_2024-01-11-14h-29m-31s@4,-3,0.8", "Robot", "2 views, cameras"),
    ("adtmv8__multiskeleton_party_seq121_2__f0120_0167", "adtmv8__multiskeleton_party_seq121_2__f0120_0167@10,-6,0.6,0",
     "Egocentric", "3 views, cameras"),
    ("vitra__000211", "vitra__000211", "Robot", "1 view, RGB only"),
    ("abc__pull_the_plug_off_the_socket_af1f17eb", "abc__pull_the_plug_off_the_socket_af1f17eb", "Robot", "1 view, RGB only"),
    ("droid__iliad_2023-07-19-17h-51m-37s", "droid__iliad_2023-07-19-17h-51m-37s", "Robot", "2 views, cameras"),
    ("adtmv8__meal_seq147_3", "adtmv8__meal_seq147_3@10,-6,0.6,0", "Egocentric", "3 views, cameras"),
    ("wild_forge--ours", "forge", "Egocentric", "3 views, cameras"),
    ("agibot__358_670702", "agibot__358_670702", "Robot", "3 views, cameras"),
]

EMBED_CSS = """
  body.embed header h1, body.embed header label, body.embed #timing, body.embed #vPanel { display:none !important; }
  body.embed header { border-bottom:0; padding:6px 10px; background:#fff; }
  body.embed main { grid-template-columns:minmax(0,1fr) !important; }
  body.embed aside { display:none !important; }
"""
EMBED_JS = '<script>if (new URLSearchParams(location.search).has("embed")) document.body.classList.add("embed");</script>'
ENGLISH = {'title="播放 (空格)"': 'title="Play (space)"', 'title="自由视角 (R 重置)"': 'title="Free view (R resets)"',
           'title="输入相机 (I)"': 'title="Input camera (I)"', '<h1 id="title">动静态分割</h1>': '<h1 id="title">SCALE4D</h1>'}


def clean(im: Image.Image, crack: int = 12, speck: int = 900) -> Image.Image:
    """The figure's touch-up (compose_wild9.py): close cracks inside the surface, drop specks on the background."""
    import cv2
    a = np.asarray(im).copy()
    content = (a.min(-1) < 245).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * crack + 1, 2 * crack + 1))
    closed = cv2.morphologyEx(content, cv2.MORPH_CLOSE, k)
    holes = (closed > 0) & (content == 0)
    if holes.any():
        a = cv2.inpaint(a, holes.astype(np.uint8), 3, cv2.INPAINT_TELEA)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(closed, 8)
    small = np.flatnonzero(stats[:, cv2.CC_STAT_AREA] < speck)
    small = small[small > 0]
    if len(small):
        a[np.isin(lab, small)] = 255
    return Image.fromarray(a)


def thumb(key: str, out: Path, width: int = 720, aspect: float = 4 / 3) -> None:
    im = clean(Image.open(RENDERS / f"{key}.png").convert("RGB"))
    g = np.asarray(im.convert("L"))
    ys, xs = np.nonzero(g < 245)
    x0, x1, y0, y1 = np.percentile(xs, 0.5), np.percentile(xs, 99.5), np.percentile(ys, 0.5), np.percentile(ys, 99.5)
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    w, h = max(w, h * aspect), max(h, w / aspect)              # the content's box at the card's aspect, no cropping
    box = Image.new("RGB", (int(w), int(h)), "white")
    box.paste(im, (int(w / 2 - cx), int(h / 2 - cy)))
    box.resize((width, int(width / aspect)), Image.LANCZOS).save(out, quality=86, optimize=True)


EXTRA = Path("/bigtemp/rqa8sm/scale4d_gallery_20261112/extra_site_cases.json")
PREVIEWS = Path("/bigtemp/rqa8sm/scale4d_gallery_20261112/previews")
KIND = {"adt": "Egocentric", "hot3d": "Egocentric", "forge": "Egocentric", "ariagen2": "Egocentric", "droid": "Robot",
        "agibot": "Robot", "vitra": "Robot", "abc": "Robot", "realsource": "Robot", "humanoid": "Robot"}


def setup_of(sid: str) -> str:
    """'N view(s), cameras' or '1 view, RGB only' from the run the clip was packed from."""
    meta = json.loads((Path("/bigtemp/rqa8sm/scale4d_sq_20261111/site/motion/data") / f"{sid}.json").read_text())
    rec = json.loads((Path(meta["run"]) / "run.json").read_text())
    v = rec.get("views", 1)
    return f"{v} view{'s' if v > 1 else ''}, cameras" if rec.get("camera") == "on" else f"{v} view, RGB only"


def thumb_preview(sid: str, out: Path, width: int = 720, aspect: float = 4 / 3) -> None:
    """The review preview (1x) as the card, framed like thumb()."""
    im = clean(Image.open(PREVIEWS / f"{sid}.jpg").convert("RGB"), crack=6, speck=300)
    g = np.asarray(im.convert("L"))
    ys, xs = np.nonzero(g < 245)
    x0, x1, y0, y1 = np.percentile(xs, 0.5), np.percentile(xs, 99.5), np.percentile(ys, 0.5), np.percentile(ys, 99.5)
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    w, h = max(w, h * aspect), max(h, w / aspect)
    box = Image.new("RGB", (int(w), int(h)), "white")
    box.paste(im, (int(w / 2 - cx), int(h / 2 - cy)))
    box.resize((width, int(width / aspect)), Image.LANCZOS).save(out, quality=86, optimize=True)


if __name__ == "__main__":
    if EXTRA.exists():
        have = {c[0] for c in CASES}
        for sid in json.loads(EXTRA.read_text()):
            if sid not in have:
                CASES.append((sid, None, KIND[sid.split("__")[0]], setup_of(sid)))
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    (OUT / "thumbs").mkdir(exist_ok=True)
    page = (PUB / "index.html").read_text()
    page = page.replace("...current(d.display), ...current(c && c.display) }", "...current(d.display), ...current(c && c.display), trail: 24 }", 1)
    page = page.replace("</style>", EMBED_CSS + "</style>", 1).replace("</header>", "</header>\n" + EMBED_JS, 1)
    for a, b in ENGLISH.items():
        page = page.replace(a, b)
    ids = [c[0] for c in CASES]
    clips = [{"id": i, "n": 0, "T": 48} for i in ids]
    data = json.loads(page.split("const DATA = ", 1)[1].split(";", 1)[0]) if "const DATA = " in page else None
    if data:                                                   # only the gallery's clips, in page order
        keep = {c["id"]: c for c in data["clips"]}
        clips = [keep[i] for i in ids]
        page = page.replace(json.dumps(data), json.dumps({**data, "clips": clips}), 1)
    from theme_viewers import inject          # the page look for the embedded viewer (tools/theme_viewers.py)
    (OUT / "index.html").write_text(inject(page))
    for sid, key, kind, setup in CASES:
        for f in (f"{sid}.scene.json", f"{sid}.scene.bin", f"{sid}.config.json"):
            shutil.copyfile(PUB / "data" / f, OUT / "data" / f)
        config_path = OUT / "data" / f"{sid}.config.json"
        config = json.loads(config_path.read_text())
        config.setdefault("display", {})["trail"] = 24
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        if (OUT / "data" / sid).exists():
            shutil.rmtree(OUT / "data" / sid)
        shutil.copytree(PUB / "data" / sid, OUT / "data" / sid)
        thumb(key, OUT / "thumbs" / f"{sid}.jpg") if key else thumb_preview(sid, OUT / "thumbs" / f"{sid}.jpg")
    (OUT / "cases.json").write_text(json.dumps([{"id": s, "kind": k, "setup": u} for s, _, k, u in CASES], indent=1) + "\n")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"{len(CASES)} cases -> {OUT} ({size / 1e6:.0f} MB)")
