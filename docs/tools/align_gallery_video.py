# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Explore in 4D, aligned with the supplementary video (2026-11-24, user: "都做 和video对齐 / 0203可以放一起"):
the video's gallery scenes come first, robot manipulation and hand-object interaction together, then its in-the-wild
captures, then its nine DAVIS clips; every earlier scene stays after them in its old order. The video's scenes are
copied from its site (SAM 3 face masks applied to frames and point colours), so the site shows the same face-blurred
files as the video. Run after tools/pack_gallery.py:

    python tools/align_gallery_video.py            # or --kinds: only relabel the scene kinds

Writes assets/gallery/{cases.json, index.html (clip list), data/, thumbs/}."""
import json
import re
import shutil
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "assets" / "gallery"
SRC = Path("/bigtemp/rqa8sm/supp_video_20261120")

# (id, kind, setup). Hand-object interaction opens the list so the gallery's first scene stays the ADT apartment meal
# (the AgiBot sink's per-frame surface flickers when it is the first thing a visitor sees); the video's robot clips follow.
VIDEO = [
    ("adtmv8__multiuser_meal_seq137_7__f0048_0095", "Egocentric", "3 views, cameras"),
    ("hot3d__002051", "Egocentric", "1 view, cameras"),
    ("adtmv8__meal_seq147_3", "Egocentric", "3 views, cameras"),
    ("hot3d__002009", "Egocentric", "1 view, cameras"),
    ("agibot__392_672634", "Robot", "3 views, cameras"),
    ("droid__tri_2024-01-11-14h-29m-31s", "Robot", "2 views, cameras"),
    ("abc__pull_the_plug_off_the_socket_af1f17eb", "Robot", "1 view, RGB only"),
    ("agibot__358_670702", "Robot", "3 views, cameras"),
    ("vitra__000211", "Robot", "1 view, RGB only"),
    ("ariagen2__nebula_WDM_Nebula_Eval_V2_32_20261005_095313_t0141", "Egocentric", "1 view, RGB only"),
    ("ariagen2__nebula_WDM_Nebula_Eval_V2_22_20261004_195102_t0143", "Egocentric", "1 view, RGB only"),
    ("ariagen2__yam_test5_20260930_172321_t0191", "Egocentric", "1 view, RGB only"),
    ("ariagen2__nebula_WDM_Nebula_Eval_V2_36_20261005_100008_t0000", "Egocentric", "1 view, RGB only"),
]
# earlier gallery scenes the video's face pass also blurred (cut from the video later): the site takes the blurred files
BLURRED_ONLY = ["adtmv8__multiskeleton_party_seq121_2__f0120_0167"]
# The gallery's other scenes were face-checked on 2026-11-24 (SAM 3, faces/detect.py + apply.py with
# FACES_ORIG=/bigtemp/rqa8sm/website_faces_20261124/orig): 8 of 49 had faces and were blurred in assets/gallery/data
# (staging, masks and originals in /bigtemp/rqa8sm/website_faces_20261124). Rebuilding with pack_gallery.py brings the
# unblurred files back: re-run that face pass afterwards.
# Scene kinds are the video's chapter titles (cards 02-04; DAVIS keeps its name), by id prefix (2026-11-24, user:
# "这些text不是在video里面都改过了"): ADT and HOT3D are hand-object interaction, Aria Gen 2 and the earlier wild2/wild
# captures are in the wild. Card text is the user's wording, so it is copied, not paraphrased.
KINDS = [(("agibot__", "droid__", "abc__", "vitra__"), "Robot Manipulation"),
         (("adt", "hot3d__"), "Hand and Object Interaction"),
         (("ariagen2__", "wild"), "In the wild captures")]


def kind_of(c: dict) -> str:
    if c["kind"] == "DAVIS":
        return "DAVIS"
    return next((k for pre, k in KINDS if c["id"].startswith(pre)), c["kind"])


def relabel(cases: list) -> list:
    return [{**c, "kind": kind_of(c)} for c in cases]


DAVIS = ["rollerblade", "parkour", "breakdance-flare", "dog", "bear", "camel", "horsejump-high", "cows", "judo"]


def copy_scene(data: Path, sid: str) -> int:
    for f in (f"{sid}.scene.json", f"{sid}.scene.bin", f"{sid}.config.json"):
        shutil.copyfile(data / f, OUT / "data" / f)
    if (OUT / "data" / sid).exists():
        shutil.rmtree(OUT / "data" / sid)
    shutil.copytree(data / sid, OUT / "data" / sid)
    return json.loads((data / f"{sid}.scene.json").read_text())["T"]


def thumb(frames: Path, sid: str) -> None:
    """The card image: the middle frame of the video's recording of this clip, centre-cropped to the cards' 4:3."""
    files = sorted(frames.glob("*.jpg"))
    im = Image.open(files[len(files) // 2]).convert("RGB")
    w, h = im.size
    cw = min(w, round(h * 4 / 3)); ch = round(cw * 3 / 4)
    im = im.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch))
    im.resize((720, 540), Image.LANCZOS).save(OUT / "thumbs" / f"{sid}.jpg", quality=86, optimize=True)


def main():
    old = json.loads((OUT / "cases.json").read_text())
    known = {c["id"]: c for c in old}
    page = (OUT / "index.html").read_text()
    m = re.search(r"^const DATA = (\{.*\});$", page, flags=re.M)
    data = json.loads(m.group(1))
    clip_of = {c["id"]: c for c in data["clips"]}

    first, clips = [], []
    for sid, kind, setup in VIDEO:
        T = copy_scene(SRC / "site/gallery/data", sid)
        first.append({**known.get(sid, {}), "id": sid, "kind": kind, "setup": setup})
        clips.append({**clip_of.get(sid, {"n": 0}), "id": sid, "T": T})
    for seq in DAVIS:
        d = SRC / "site/davis" / seq / "data"
        sid = next(p.name for p in d.iterdir() if p.is_dir())
        T = copy_scene(d, sid)
        thumb(SRC / "rec" / f"davis_{seq}" / "frames", sid)
        first.append({"id": sid, "kind": "DAVIS", "setup": f"{seq.replace('-', ' ')} · 1 view, no camera"})
        clips.append({"id": sid, "n": 0, "T": T})
    for sid in BLURRED_ONLY:
        copy_scene(SRC / "site/gallery/data", sid)
    ids = {c["id"] for c in first}
    rest = [c for c in old if c["id"] not in ids]
    cases = relabel(first + rest)
    clips += [clip_of[c["id"]] for c in rest]
    page = page.replace(m.group(0), "const DATA = " + json.dumps({**data, "clips": clips}) + ";", 1)
    (OUT / "index.html").write_text(page)
    (OUT / "cases.json").write_text(json.dumps(cases, indent=1) + "\n")
    print(f"{len(cases)} scenes ({len(first)} from the video first, {len(rest)} earlier ones after)")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--kinds"]:      # only rewrite the kinds in cases.json (no data copy)
        cases = relabel(json.loads((OUT / "cases.json").read_text()))
        (OUT / "cases.json").write_text(json.dumps(cases, indent=1) + "\n")
        print({k: sum(c["kind"] == k for c in cases) for k in dict.fromkeys(c["kind"] for c in cases)})
    else:
        main()
