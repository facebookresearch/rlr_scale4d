# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""The SCALE4D apartment film (60 fps) -> assets/hero.mp4 (1920x1080, 30 fps, H.264, no audio, faststart)
and assets/hero_poster.jpg (frame 300, 10 s in; the film opens on black).

    python tools/hero_from_film.py /p/3dllmselftraining/infd4rt/outputs/v2.mp4 --end 70.5

--end cuts the film just before its own SCALE4D title (v2: letters start at 71.0 s): the page fades its title in
when the video ends (js/main.js), so the two titles never overlap.
"""
import argparse
import sys
from fractions import Fraction
from pathlib import Path

import av

ASSETS = Path(__file__).resolve().parent.parent / "assets"
POSTER_FRAME = 300


def main(src: str, end: float | None) -> None:
    dst = ASSETS / "hero.mp4"
    with av.open(src) as inp, av.open(str(dst), "w", options={"movflags": "+faststart"}) as out:
        vin = inp.streams.video[0]
        vout = out.add_stream("libx264", rate=30)
        vout.width, vout.height, vout.pix_fmt = 1920, 1080, "yuv420p"
        vout.options = {"crf": "24", "preset": "slow", "profile": "high", "tune": "film"}
        n = 0
        for i, frame in enumerate(inp.decode(vin)):
            if end is not None and i / 60.0 >= end:
                break
            if i % 2:            # 60 -> 30 fps
                continue
            f = frame.reformat(width=1920, height=1080, format="yuv420p", interpolation="LANCZOS")
            f.pts, f.time_base = n, Fraction(1, 30)
            if n == POSTER_FRAME:
                f.to_image().save(ASSETS / "hero_poster.jpg", quality=85)
            for p in vout.encode(f):
                out.mux(p)
            n += 1
        for p in vout.encode():
            out.mux(p)
    print(f"{dst}: {n} frames, {dst.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("film")
    ap.add_argument("--end", type=float, help="seconds of the film to keep")
    a = ap.parse_args()
    main(a.film, a.end)
