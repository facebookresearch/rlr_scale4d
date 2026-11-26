# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Pack the side-by-side comparison as 4D scenes (assets/compare3d/<clip>_<method>.{json,bin}) for js/viewer4d.js.

    python tools/pack_compare3d.py [CLIP_KEY ...]       (from the website worktree; reads clips300 tracks)

Same data as the 2D panels (tools/render_compare.py, evaluation/paper_figures/supp_compare.py): every method's
tracks of frame 0's lattice, as predicted (no edge filtering, no smoothing), thinned to every second row and column
(112 x 112, the same points for every method; discs twice as wide) so the scenes stay small. Several baselines
predict in the moving camera's frame, so on egocentric clips nearly all their points move; capping moving points
would make them look sparser than ours, so nothing else is dropped. Points that stay put are
stored once at their frame-0 position; moving points keep their per-frame positions and visibility; trails are
drawn on up to TRAILS movers. All methods of a clip share the camera of Figure 4's column view (orbit centre on the
input camera's axis at the pooled median frame-0 depth, 18 deg yaw, 10 deg pitch), so the two panes start aligned.
Everything is written in display axes (OpenCV camera frame with y and z flipped).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path("/p/3dllmselftraining/infd4rt")
sys.path.insert(0, str(REPO / "evaluation/paper_figures"))
import supp_compare as sc  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_compare import CLIPS  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "assets" / "compare3d"
# Ours = the released SCALE4D checkpoint (140k, the paper's Table 2 model; 2026-11-24, user: "Side by Side make it better
# using our best checkpoints"), Algorithm 1 on the same clips300 frames: the benchmark batch's 224-lattice tracks
# (/bigtemp/rqa8sm/scale4d_bench_20261111, run_bench.py: camera ON with the dataset cameras on HOT3D, camera OFF on
# DROID; Aria Gen 2 below). Same rgbs, intrinsics and extrinsics as the clips300 files. The 160k scenes (d4rt160ka1) were
# the earlier Ours and stay on disk.
# Aria Gen 2 clips: the benchmark batch ran them with cameras OFF, and on the two cat clips (head-mounted, ~0.9 m camera
# path) 140k then lets the static scene slide ~19 cm over the clip (160k: <1 cm). They are rerun with cameras ON from the
# recording's VIO poses, world up +Z (/bigtemp/rqa8sm/compare3d_140k_20261124/run_aria_on.py; cat desk: 2.2 cm).
OURS, OURS_RUNS = "scale4d140k", Path("/bigtemp/rqa8sm/scale4d_bench_20261111/runs")
OURS_RUNS_ON = Path("/bigtemp/rqa8sm/compare3d_140k_20261124/runs")
METHODS = [(m, label) for m, label in sc.METHODS if m != "d4rt160ka1"] + [(OURS, "Ours")]


def track_file(mid, clip):
    if mid != OURS:
        return sc.TRACKS / f"dense_{mid}_{clip}.npz"
    return (OURS_RUNS_ON if clip.startswith("ariagen2__") else OURS_RUNS) / clip / "model" / "tracks_224.npz"


def load(mid, clip):
    """sc.load for any method: frame-0 queries of the camera-0-frame tracks."""
    with np.load(track_file(mid, clip), allow_pickle=True) as d:
        assert str(d["frame"]) == "camera0"
        keep = d["t_src"] == 0
        return {k: np.asarray(d[k])[keep] if k in ("pos_3d", "vis", "colors") else np.asarray(d[k])
                for k in ("pos_3d", "vis", "colors", "rgbs", "intrinsics")}
STEP, TRAILS, MIN_MOTION = 2, 300, 0.06
SPRITE_W, SPRITE_COLS = 256, 8


def flip(a):
    return a * np.array([1, -1, -1], np.float64)


def add(blob, layout, name, arr):
    pad = (-len(blob)) % 8
    blob.extend(b"\0" * pad)
    layout[name] = {"offset": len(blob), "dtype": str(arr.dtype), "shape": list(arr.shape)}
    blob.extend(arr.tobytes())


def smooth(x, k=5):
    pad = np.pad(x, ((0, 0), (k // 2, k // 2), (0, 0)), mode="edge")
    c = np.cumsum(pad, axis=1)
    c = np.concatenate([np.zeros_like(c[:, :1]), c], axis=1)
    return (c[:, k:] - c[:, :-k]) / k


def stratified(points, count, seed=0):
    if len(points) <= count:
        return np.arange(len(points))
    lo, hi = points.min(0), points.max(0)
    cell = (np.prod(np.maximum(hi - lo, 1e-3)) / count) ** (1 / 3)
    _, first = np.unique(np.floor((points - lo) / cell).astype(np.int64), axis=0, return_index=True)
    rng = np.random.default_rng(seed)
    if len(first) >= count:
        return np.sort(rng.choice(first, count, replace=False))
    rest = np.setdiff1d(np.arange(len(points)), first)
    return np.sort(np.concatenate([first, rng.choice(rest, count - len(first), replace=False)]))


def shared_view(data, f):
    """Figure 4's column view in display axes: eye, target, up and a vertical field of view covering its crop."""
    view, lim = sc.column_view(data, f)
    y, p = math.radians(view.yaw), math.radians(view.pitch)
    back = np.array([math.cos(p) * math.sin(y), -math.sin(p), -math.cos(p) * math.cos(y)])
    eye = view.target + view.dist * back
    half = max(abs(lim[2]), abs(lim[3]), abs(lim[0]) / 1.6, abs(lim[1]) / 1.6)
    fov = float(np.clip(2 * math.degrees(math.atan(half)), 25, 75))
    return flip(eye), flip(view.target), np.array([0.0, 1.0, 0.0]), fov


def lattice_subset(path, W, H):
    """Frame-0 queries on every STEP-th row and column of the 224 lattice (indices into the t_src == 0 tracks)."""
    with np.load(path, allow_pickle=True) as f:
        uv = np.asarray(f["query_uv"], np.float64)[np.asarray(f["t_src"]) == 0]
    col, row = np.round(uv[:, 0] * 224 / W).astype(int), np.round(uv[:, 1] * 224 / H).astype(int)
    return (col % STEP == 0) & (row % STEP == 0)


def pack_method(d, keep, cams_meta, view, out, key):
    pos, vis, rgb = d["pos_3d"][keep].astype(np.float64), d["vis"][keep], d["colors"][keep]
    T = pos.shape[1]
    W = d["rgbs"].shape[3]
    fx = float(d["intrinsics"][0])
    ok = np.isfinite(pos).all((1, 2))
    pos, vis, rgb = pos[ok], vis[ok], rgb[ok]
    z0 = np.maximum(pos[:, 0, 2], 1e-3)
    radius = 0.62 * (W / 224) * STEP * z0 / fx
    sm = smooth(pos)
    disp = np.linalg.norm(sm - sm[:, :1], axis=-1).max(1)
    rng = np.linalg.norm(pos[:, 0], axis=-1)
    moving = disp > np.maximum(0.03, 0.02 * rng)
    s_ids, d_ids = np.flatnonzero(~moving), np.flatnonzero(moving)
    # trails first: steady movers that travel at least MIN_MOTION, spread over space
    cand = d_ids[(disp[d_ids] >= MIN_MOTION) & (vis[d_ids, 0] >= 0.5)]
    cand = cand[stratified(sm[cand, -1], TRAILS)] if len(cand) > TRAILS else cand
    d_ids = np.concatenate([cand, np.setdiff1d(d_ids, cand)])
    s_mm = np.clip(np.round(flip(pos[s_ids, 0]) * 1000), -32767, 32767).astype(np.int16)
    d_mm = np.clip(np.round(flip(pos[d_ids]) * 1000), -32767, 32767).astype(np.int16)
    d_vis = np.packbits((vis[d_ids] >= 0.5).reshape(-1))
    u8 = lambda a: np.clip(np.round(a * 255), 0, 255).astype(np.uint8)  # noqa: E731
    r16 = lambda a: np.clip(np.round(a * 1e4), 0, 65535).astype(np.uint16)  # noqa: E731
    blob, layout = bytearray(), {}
    add(blob, layout, "s_xyz", s_mm)
    add(blob, layout, "s_rgb", u8(rgb[s_ids]))
    add(blob, layout, "s_rad", r16(radius[s_ids]))
    add(blob, layout, "d_traj", d_mm)
    add(blob, layout, "d_vis", d_vis)
    add(blob, layout, "d_rgb", u8(rgb[d_ids]))
    add(blob, layout, "d_rad", r16(radius[d_ids]))
    eye, target, up, fov = view
    meta = dict(key=key, frames=T, static=len(s_mm), dynamic=len(d_mm), tracks=int(len(cand)), fov=round(fov, 1),
                target=np.round(target, 4).tolist(), eye=np.round(eye, 4).tolist(), up=up.tolist(), layout=layout,
                **cams_meta)
    (out / f"{key}.json").write_text(json.dumps(meta, separators=(",", ":")))
    (out / f"{key}.bin").write_bytes(bytes(blob))
    return meta, len(blob)


def cameras(c2w, intr, W, H, size):
    fx, fy, cx, cy = (float(v) for v in intr)
    local = np.array([[0, 0, 0]] + [[(u - cx) / fx * size, (v - cy) / fy * size, size]
                                    for u, v in ((0, 0), (W, 0), (W, H), (0, H))])
    cams, eyes, fwds, ups = [], [], [], []
    for M in c2w:
        R, t = M[:3, :3], M[:3, 3]
        cams.append(flip(local @ R.T + t)); eyes.append(flip(t)); fwds.append(flip(R[:, 2])); ups.append(flip(-R[:, 1]))
    return dict(cams=np.round(np.array(cams), 4).reshape(len(c2w), -1).tolist(), cam_eye=np.round(eyes, 4).tolist(),
                cam_fwd=np.round(fwds, 4).tolist(), cam_up=np.round(ups, 4).tolist(),
                fov_input=round(float(2 * math.degrees(math.atan(H / (2 * fy)))), 2))


def main():
    want = set(sys.argv[1:])
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for key, (clip, title, source) in CLIPS.items():
        if want and key not in want:
            continue
        data = {mid: load(mid, clip) for mid, _ in METHODS}
        ours = data[OURS]
        T, H, W = ours["rgbs"].shape[0], ours["rgbs"].shape[2], ours["rgbs"].shape[3]
        with np.load(track_file(OURS, clip), allow_pickle=True) as f:
            c2w = np.asarray(f["extrinsic"], np.float64)
        view = shared_view(list(data.values()), T - 1)
        cams_meta = cameras(c2w, ours["intrinsics"], W, H, 0.15 * float(np.nanmedian(ours["pos_3d"][:, 0, 2])))
        # input frames as one sprite
        fw, fh = SPRITE_W, round(SPRITE_W * H / W)
        rows = math.ceil(T / SPRITE_COLS)
        sheet = Image.new("RGB", (fw * SPRITE_COLS, fh * rows))
        for i, fr in enumerate(ours["rgbs"]):
            sheet.paste(Image.fromarray(fr.transpose(1, 2, 0)).resize((fw, fh), Image.LANCZOS),
                        ((i % SPRITE_COLS) * fw, (i // SPRITE_COLS) * fh))
        sheet.save(OUT / f"{key}_input.jpg", quality=72, optimize=True)
        cams_meta["sprite"] = dict(w=fw, h=fh, cols=SPRITE_COLS, rows=rows)
        for mid, label in METHODS:
            keep = lattice_subset(track_file(mid, clip), W, H)
            meta, size = pack_method(data[mid], keep, cams_meta, view, OUT, f"{key}_{mid}")
            total += size
            print(f"{key} {label:14s} static {meta['static']:6d} moving {meta['dynamic']:5d} trails {meta['tracks']:3d} "
                  f"{size / 1e6:.1f} MB", flush=True)
    print(f"total {total / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
