# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Turn the rendered comparison panels into web JPEGs: python tools/compress_compare.py SRC_DIR"""
import sys
from pathlib import Path

from PIL import Image

src, dst = Path(sys.argv[1]), Path(__file__).resolve().parent.parent / "assets" / "compare"
dst.mkdir(parents=True, exist_ok=True)
total = 0
for p in sorted(src.glob("*.png")):
    im = Image.open(p).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    im = bg.convert("RGB")
    w = 720 if p.stem.endswith("_input") else 1500
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    out = dst / f"{p.stem}.jpg"
    im.save(out, quality=84, optimize=True, progressive=True)
    total += out.stat().st_size
print(len(list(dst.glob('*.jpg'))), "files", round(total / 1e6, 1), "MB", im.size)
