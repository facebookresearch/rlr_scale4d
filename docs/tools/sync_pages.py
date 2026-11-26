# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Build the GitHub Pages copy of this site: facebookresearch/rlr_scale4d, branch `main`, folder `docs/`.

    python tools/sync_pages.py DOCS_DIR          (from this worktree; then commit DOCS_DIR in the rlr_scale4d clone)

The Pages site serves everything itself, the 3D scene data included (2026-11-24, user: "on githubio these cases cannot
be loaded ... make sure it works"; the gallery used to load from the private Hugging Face repo, which a browser cannot
read). GitHub Pages publishes at most 1 GB, so the copy differs from the department site in size only:

- input frames of every 3D viewer (data/<scene>/tNN.jpg) become WebP, quality 85 (about half the bytes), and the
  viewers ask for .webp;
- files the page never requests are left out: assets/scenes (the old Viewer4D scenes), assets/compare (2D panels),
  the 160k side-by-side scenes (*_d4rt160ka1.*), and the 1- and 2-view scenes of the zero-shot views section (it
  offers 3 to 10).

Kept from the rlr_scale4d branch, never overwritten: LICENSE, LICENSES/, license.html, README.md, .nojekyll,
.gitignore and demo.json (the demo's supervisor pushes the live link there). The footer gets the copyright statement and
the license and legal policy links. The script refuses to write a copy of 980 MB or more.
"""
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
KEEP = {"LICENSE", "LICENSES", "license.html", "README.md", ".nojekyll", ".gitignore", "demo.json"}
SKIP_TRACKED = ("README.md", ".gitignore", "assets/scenes/", "assets/compare/")
DATA = ("gallery", "views", "camera", "selftrain")
FRAME = re.compile(r"^t\d\d\.jpg$")
WEBP_Q = 85
LIMIT = 980e6
FOOTER = ('  <p class="footer-aff">Reality Labs Research, Meta</p>\n',
          '  <p class="footer-aff">Reality Labs Research, Meta</p>\n'
          '  <p>Copyright ©2026 Meta Platforms, Inc. and affiliates.</p>\n'
          '  <p><a href="license.html">CC-BY-NC 4.0 and third party licenses</a></p>\n'
          '  <p><a href="https://opensource.fb.com/legal/privacy/">Privacy Policy</a> · '
          '<a href="https://opensource.fb.com/legal/terms/">Terms of Use</a></p>\n')
FRAME_URL = ('t${String(i).padStart(2, "0")}.jpg${VQ}', 't${String(i).padStart(2, "0")}.webp${VQ}')


def skipped(name: str) -> bool:
    return name in SKIP_TRACKED or name.startswith(SKIP_TRACKED[2:]) or "_d4rt160ka1." in name


def views_not_offered() -> set:
    """Scene ids of the 1- and 2-view runs: js/main.js offers 3 to 10 views (VW0)."""
    cases = json.loads((HERE / "assets/views/cases.json").read_text())
    return {ids[i] for clip in cases["clips"].values() for ids in clip.values() for i in (0, 1)}


def to_webp(src: Path, dst: Path) -> None:
    Image.open(src).convert("RGB").save(dst, "WEBP", quality=WEBP_Q, method=6)


def main():
    docs = Path(sys.argv[1]).resolve()
    assert docs.name == "docs" and (docs / "LICENSE").exists(), f"{docs} is not the rlr_scale4d docs folder"
    for p in docs.iterdir():                        # clear everything but the branch's own files
        if p.name not in KEEP:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    tar = subprocess.run(["git", "-C", str(HERE), "archive", "HEAD"], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        members = [m for m in t.getmembers() if not skipped(m.name)]
        t.extractall(docs, members=members)
    drop = views_not_offered()
    jobs = []
    for part in DATA:
        src = HERE / "assets" / part / "data"
        for f in src.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(src)
            if part == "views" and rel.parts[0].split(".")[0] in drop:
                continue
            out = docs / "assets" / part / "data" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if FRAME.match(f.name):
                jobs.append((f, out.with_suffix(".webp")))
            else:
                shutil.copyfile(f, out)
    with ThreadPoolExecutor(32) as ex:
        list(ex.map(lambda j: to_webp(*j), jobs))
    for part in DATA:                               # the viewers ask for .webp frames
        page = docs / "assets" / part / "index.html"
        s = page.read_text()
        assert s.count(FRAME_URL[0]) == 1, f"{page}: frame URL pattern not found once"
        page.write_text(s.replace(*FRAME_URL))
    index = docs / "index.html"
    s = index.read_text()
    assert s.count(FOOTER[0]) == 1
    index.write_text(s.replace(*FOOTER))
    with open(docs / "styles.css", "a") as f:
        f.write("\n/* footer license link (GitHub Pages copy) */\n"
                ".footer a { text-decoration: underline; text-underline-offset: 0.15em; }\n")
    lic = docs / "license.html"
    v = re.search(r'const V = "\?v=([0-9a-z]+)"', (docs / "js/main.js").read_text()).group(1)
    lic.write_text(re.sub(r"styles\.css\?v=[0-9a-z]+", f"styles.css?v={v}", lic.read_text()))
    total = sum(p.stat().st_size for p in docs.rglob("*") if p.is_file())
    print(f"{len(jobs)} frames as WebP, {len(drop)} view scenes left out; docs/ = {total / 1e6:.0f} MB")
    if total >= LIMIT:
        raise SystemExit(f"docs/ is {total / 1e6:.0f} MB: over the {LIMIT / 1e6:.0f} MB budget for GitHub Pages (1 GB)")


if __name__ == "__main__":
    main()
