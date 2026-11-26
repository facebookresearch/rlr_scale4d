# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Re-render the paper's qualitative comparison panels at web resolution (run from the infd4rt repo root).

    python reference/website/tools/render_compare.py OUT_DIR KEY
Same data, view and draw code as evaluation/paper_figures/supp_compare.py; only the dpi changes.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "evaluation/paper_figures")
import supp_compare as sc  # noqa: E402

CLIPS = {
    "bottle": ("hot3d__003460", "Hands and a bottle", "HOT3D, Aria glasses"),
    "plate": ("hot3d__003386", "Hands and a plate", "HOT3D, Aria glasses"),
    "lift": ("hot3d__001899", "Lifting an object", "HOT3D, Aria glasses"),
    "catdesk": ("ariagen2__nebula_WDM_Nebula_Eval_V2_30_20261005_091029_t0072", "Cat on a desk", "Aria Gen 2"),
    "catwalk": ("ariagen2__nebula_WDM_Nebula_Eval_V2_26_20261004_200413_t0000", "Cat walking", "Aria Gen 2"),
    "arms": ("ariagen2__yam_test8_20260930_173136_t0235", "Robot arms", "Aria Gen 2"),
    "pick": ("droid__tri_28813166_s0", "Robot pick and place", "DROID"),
}
DPI = 1000


def main():
    out, key = Path(sys.argv[1]), sys.argv[2]
    clip, title, source = CLIPS[key]
    out.mkdir(parents=True, exist_ok=True)
    cell_w, cell_h, _, _ = sc.layout(4, len(sc.METHODS) + 1)
    data = {mid: sc.load(mid, clip) for mid, _ in sc.METHODS}
    ours = data["d4rt160ka1"]
    f = ours["pos_3d"].shape[1] - 1
    la = (ours["rgbs"].shape[3] / float(ours["intrinsics"][0])) / 224.0
    view, lim = sc.column_view(list(data.values()), f)

    def draw_input(ax):
        ax.imshow(sc.input_montage(ours["rgbs"]), aspect="auto")
        ax.axis("off")
    sc.save_panel(out / f"{key}_input.png", (cell_w, cell_h), draw_input, dpi=DPI)
    for mid, _ in sc.METHODS:
        sc.save_panel(out / f"{key}_{mid}.png", (cell_w, cell_h), lambda ax, d=data[mid]: sc.panel(ax, d, view, f, lim, la), dpi=DPI)
        print(key, mid, flush=True)
    (out / f"{key}.json").write_text(json.dumps(dict(key=key, clip=clip, title=title, source=source)))


if __name__ == "__main__":
    main()
