# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Pack teaser-studio split scenes into small web scenes: assets/scenes/<key>.{json,bin,jpg}.

    python tools/pack_scenes.py [KEY ...]

Everything is written in display coordinates (OpenCV camera frame with y and z flipped) so the viewer
does not need to know about the source convention. Binary layout is described by `layout` in the JSON.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

DATA = Path("/bigtemp/rqa8sm/clips300_20261009/site/teaser/data")
OUT = Path(__file__).resolve().parent.parent / "assets" / "scenes"
MAX_STATIC, MAX_DYNAMIC = 240_000, 22_000
SPRITE_W, SPRITE_COLS = 256, 8

SCENES = [
    dict(key="droid", id="droid__tri_28813166_s0", title="Robot manipulation",
         note="DROID, one exterior camera. A robot arm works among objects on a table.",
         crop=1.6, yaw=0, pitch=35, dist=1.8, min_motion=10, tracks=320, cam_size=0.12),
    dict(key="kitchen", id="adt__Apartment_release_multiuser_cook_seq117_4", title="Everyday activity",
         note="Aria Digital Twin, egocentric. A person cooks in the kitchen.",
         crop=2.4, yaw=-15, pitch=30, dist=2.2, min_motion=8, tracks=320, cam_size=0.15),
    dict(key="tennis", id="pstudio__tennis_1", title="Fast motion",
         note="Panoptic Studio, one view of the rig. A tennis swing seen from a fixed camera.",
         crop=3.5, yaw=30, pitch=20, dist=1.15, min_motion=10, tracks=220, cam_size=0.3, split_target=True),
    dict(key="arms", id="ariagen2__yam_test8_20260930_173136_t0470", title="Robot arms from glasses",
         note="Aria Gen 2 watching two robot arms from across the table.",
         crop=2.6, yaw=-20, pitch=25, dist=1.7, min_motion=6, tracks=400, cam_size=0.15),
    dict(key="hand", id="dexycb__20200928-subject-07__20200928_144906", title="Hand and object",
         note="DexYCB, one view of the rig. A hand lifts an object from the table.",
         crop=1.7, yaw=10, pitch=2, dist=1.2, min_motion=6, tracks=400, cam_size=0.12),
]


def flip(a):
    return a * np.array([1, -1, -1], a.dtype)


def rotate(v, axis, deg):
    """Rodrigues rotation of v about a unit axis."""
    axis = axis / np.linalg.norm(axis)
    t = math.radians(deg)
    return v * math.cos(t) + np.cross(axis, v) * math.sin(t) + axis * np.dot(axis, v) * (1 - math.cos(t))


def unpack(buf, layout):
    out = {}
    for k, l in layout.items():
        n = int(np.prod(l["shape"]))
        out[k] = np.frombuffer(buf, dtype=l["dtype"], count=n, offset=l["offset"]).reshape(l["shape"])
    return out


def add(blob, layout, name, arr):
    pad = (-len(blob)) % 8
    blob.extend(b"\0" * pad)
    layout[name] = {"offset": len(blob), "dtype": str(arr.dtype), "shape": list(arr.shape)}
    blob.extend(arr.tobytes())


def pack(cfg):
    entry = json.loads((DATA / f"{cfg['id']}.json").read_text())
    sp = entry["split"]
    raw = unpack((DATA / f"{cfg['id']}.split.bin").read_bytes(), sp["layout"])
    F = sp["frames"]
    rng = np.random.default_rng(0)
    target = flip(np.array(sp["target"] if cfg.get("split_target") else entry["target"], np.float32))

    # static points: crop to the region of interest, then thin; radii grow to keep surfaces closed
    s_xyz = flip(raw["s_xyz"].astype(np.float32))
    good = raw["s_radius"] > 0  # the studio marks outliers with a negative radius
    near = np.linalg.norm(s_xyz - target, axis=1) < cfg["crop"]
    keep = np.where(good & near)[0]
    big = np.quantile(raw["s_radius"][keep], 0.998)  # stray points next to the camera render as huge discs
    keep = keep[raw["s_radius"][keep] <= big]
    # floaters: drop points with almost no neighbours at their own splat scale
    radius = 6 * np.median(raw["s_radius"][keep])
    neighbours = cKDTree(s_xyz[keep]).query_ball_point(s_xyz[keep], radius, return_length=True, workers=8)
    keep = keep[neighbours >= 6]
    grow = 1.0
    if len(keep) > MAX_STATIC:
        grow = math.sqrt(len(keep) / MAX_STATIC)
        keep = rng.choice(keep, MAX_STATIC, replace=False)
    s_mm = np.clip(np.round(s_xyz[keep] * 1000), -32767, 32767).astype(np.int16)
    s_rgb = raw["s_rgb"][keep].astype(np.uint8)
    s_rad = np.clip(np.round(raw["s_radius"][keep] * grow * 1e4), 0, 65535).astype(np.uint16)

    # moving points: tracks are chosen first so their ids survive the thinning
    d_traj = flip(raw["d_traj"].astype(np.int32))
    vis = raw["d_vis"]
    disp = np.linalg.norm(d_traj - d_traj[:, :1], axis=2).max(axis=1) / 10  # cm
    end = d_traj[:, -1].astype(np.float32) / 1000
    cand = (raw["d_src"] == 0) & (vis[:, 0] > 0) & (disp >= cfg["min_motion"]) & \
           (np.linalg.norm(end - target, axis=1) < cfg["crop"])
    cand = rng.permutation(np.where(cand)[0])[:cfg["tracks"]]
    rest = np.setdiff1d(np.where(raw["d_radius"] > 0)[0], cand)
    budget = max(MAX_DYNAMIC - len(cand), 0)
    grow_d = 1.0
    if len(rest) > budget:
        grow_d = math.sqrt((len(rest) + len(cand)) / MAX_DYNAMIC)
        rest = rng.choice(rest, budget, replace=False)
    keep_d = np.concatenate([cand, rest])
    d_mm = np.clip(d_traj[keep_d], -32767, 32767).astype(np.int16)
    d_vis = np.packbits(vis[keep_d].reshape(-1) > 0)
    d_rgb = raw["d_rgb"][keep_d].astype(np.uint8)
    d_rad = np.clip(np.round(raw["d_radius"][keep_d] * grow_d * 1e4), 0, 65535).astype(np.uint16)

    # cameras: apex + 4 image-plane corners per frame
    c = entry["cameras"][0]
    K, (W, H) = np.array(c["K"], np.float64), c["size"]
    s = cfg["cam_size"]
    local = np.array([[0, 0, 0]] + [[(u - K[0, 2]) / K[0, 0] * s, (v - K[1, 2]) / K[1, 1] * s, s]
                                    for u, v in ((0, 0), (W, 0), (W, H), (0, H))])
    cams, eyes, fwds, ups = [], [], [], []
    for M in sp["cams"]:
        M = np.array(M, np.float64)
        R, t = M[:3, :3], M[:3, 3]
        cams.append(flip(local @ R.T + t).astype(np.float32))
        eyes.append(flip(t)); fwds.append(flip(R[:, 2])); ups.append(flip(-R[:, 1]))
    cams, eyes, fwds, ups = (np.array(a) for a in (cams, eyes, fwds, ups))

    # default view: the last input camera rotated about the subject, as in the paper figures
    M = np.array(entry["cameras"][0]["c2w"], np.float64)
    up = flip(-M[:3, 1]) / np.linalg.norm(M[:3, 1])
    v = flip(M[:3, 3]) - target
    v = rotate(v, up, cfg["yaw"])
    v = rotate(v, np.cross(v, up), cfg["pitch"]) * cfg["dist"]

    blob, layout = bytearray(), {}
    add(blob, layout, "s_xyz", s_mm)
    add(blob, layout, "s_rgb", s_rgb)
    add(blob, layout, "s_rad", s_rad)
    add(blob, layout, "d_traj", d_mm)
    add(blob, layout, "d_vis", d_vis)
    add(blob, layout, "d_rgb", d_rgb)
    add(blob, layout, "d_rad", d_rad)

    # input frames as one sprite, so playback needs a single request and never flickers
    names = sorted((DATA / cfg["id"]).glob("t*.jpg"))[:F]
    w0, h0 = Image.open(names[0]).size
    fw, fh = SPRITE_W, round(SPRITE_W * h0 / w0)
    rows = math.ceil(F / SPRITE_COLS)
    sheet = Image.new("RGB", (fw * SPRITE_COLS, fh * rows))
    for i, p in enumerate(names):
        sheet.paste(Image.open(p).convert("RGB").resize((fw, fh), Image.LANCZOS),
                    ((i % SPRITE_COLS) * fw, (i // SPRITE_COLS) * fh))
    OUT.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT / f"{cfg['key']}.jpg", quality=72, optimize=True)

    meta = dict(key=cfg["key"], title=cfg["title"], note=cfg["note"], source=cfg["id"], frames=F,
                static=len(s_mm), dynamic=len(d_mm), tracks=len(cand), crop=cfg["crop"],
                fov=round(float(min(60, max(25, entry["fov_y"]))), 1),
                fov_input=round(float(2 * math.degrees(math.atan(H / (2 * K[1, 1])))), 2),
                target=[round(float(x), 4) for x in target],
                eye=[round(float(x), 4) for x in target + v], up=[round(float(x), 4) for x in up],
                cams=np.round(cams, 4).reshape(F, -1).tolist(),
                cam_eye=np.round(eyes, 4).tolist(), cam_fwd=np.round(fwds, 4).tolist(), cam_up=np.round(ups, 4).tolist(),
                sprite=dict(w=fw, h=fh, cols=SPRITE_COLS, rows=rows), layout=layout)
    (OUT / f"{cfg['key']}.json").write_text(json.dumps(meta, separators=(",", ":")))
    (OUT / f"{cfg['key']}.bin").write_bytes(bytes(blob))
    size = len(blob) / 1e6
    print(f"{cfg['key']}: {len(s_mm)} static, {len(d_mm)} moving, {len(cand)} tracks, {size:.1f} MB", flush=True)


def main():
    want = set(sys.argv[1:])
    for cfg in SCENES:
        if not want or cfg["key"] in want:
            pack(cfg)


if __name__ == "__main__":
    main()
