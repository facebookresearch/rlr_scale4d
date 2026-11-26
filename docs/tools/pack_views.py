# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Pack the "Beyond three views" and "Cameras optional" viewers: python tools/pack_views.py [views] [camera] [selftrain]

2026-11-24: PStudio opens at the video v17+ angle (N2) and the page starts at 3 views, like the video.

Aligned with the supplementary video v14 (2026-11-22): the video's examples come first (PStudio softball, 1-10 views;
ADT decoration, cameras on | off side by side) and open at the video's camera angles with its bright ground truth and
trails off; the site's earlier examples (Show3D can; DexYCB subjects 05 and 02) stay, at their earlier angles.

SRC (default /bigtemp/rqa8sm/supp_video_20261120) holds site/views/<clip>/{v,off_v}<V>/ (published motion-viewer pages
of Di's two view-count clips, cameras on / off, 1..10 views; PStudio faces already blurred), traj/gt_<clip>.json
(ground truth in the target-camera frame, mm) and the AJ table from Di's HF examples.
Writes assets/views/: index.html (one viewer for all 40 scenes), data/ (scenes, frames, gt), cases.json.
The viewer keeps the camera fixed relative to the target camera when the parent switches scenes with
{type: "scale4d-load", id, keep: true}, and draws ground truth as green dots ({type: "scale4d-gt", on})."""
import csv, json, re, shutil, sys
from pathlib import Path

SRC = Path("/bigtemp/rqa8sm/supp_video_20261120")
CAMCOND = SRC / "camcond/hf/examples/camera_conditioning"
AJ_CSV = Path("/bigtemp/rqa8sm/scale4d_view_count_hf/examples/view_count/scores/selected.csv")
OUT = None   # set by pack()
CLIPS = {"pstudio": "Panoptic Studio · softball", "show3d": "Show3D · can on a table"}
DOT = {"pstudio": 3.2, "show3d": 2.2, "adt_skeleton": 3.6, "dexycb_subject05": 3.0, "dexycb_subject02": 3.0, "ranch": 3.0}
# The video's opening views (tools/v9_jobs.py, pick_selfimp_obj.py): base view (off, up) in the target camera's frame
# at frame 0, turned like record.js (yaw about up, then pitch about right), at `dist` from the ground-truth centroid,
# with the vertical field of view of the video's tile (w, h) for the reference page's frame-0 intrinsics.
ADT_D = ([0.978944, -0.036103, 0.200909], [-0.07859, -0.975025, 0.207725])   # pick_adt_parallel.offs()[3]: 6 deg off the wall
START = {"pstudio": dict(off=[0, 0, -1], up=[0, -1, 0], yaw=44, pitch=15, dist=round(1.44 * 1.7, 3), tile=(845, 720), ref="site/views/pstudio/v1"),   # video v17+ angle N2 (yaw 44 -> 56, pitch 15, 2.45 m); was angle C
         "adt_skeleton": dict(off=ADT_D[0], up=ADT_D[1], yaw=0, pitch=0, dist=1.6, tile=(640, 720), ref="site/camcond/adt_skeleton/on"),   # angle D
         "ranch": dict(off=[0, 0, -1], up=[0, -1, 0], yaw=45, pitch=25, dist=0.25, tile=(640, 720), ref="site/selfimp_obj/ranch/B3/on"),   # the video's angle C (pick_selfimp_obj.py)
         # the earlier examples keep the site's earlier views (its yaw / raise; raising the view is a negative record.js pitch)
         "show3d": dict(off=[0, 0, -1], up=[0, -1, 0], yaw=28, pitch=-14, dist=1.25, tile=(845, 720), ref="site/views/show3d/v1", fov=0.8),
         "dexycb_subject05": dict(off=[0, 0, -1], up=[0, -1, 0], yaw=40, pitch=-18, dist=1.1, tile=(640, 720), ref="site/camcond/dexycb_subject05/on"),
         "dexycb_subject02": dict(off=[0, 0, -1], up=[0, -1, 0], yaw=40, pitch=-18, dist=1.1, tile=(640, 720), ref="site/camcond/dexycb_subject02/on")}

PATCH_LOAD_OLD = '    $("clip").value = m.id; selectClip(m.id);'
PATCH_LOAD_NEW = '    if (m.keep && clip && cam) window.__keep = keepRel(); else window.__fresh = true;\n    $("clip").value = m.id; selectClip(m.id);'
PATCH_VIEW_OLD = "  applyView(cfg.view);\n  uploadStatic(); prepareMovers(); showCounts();"
PATCH_VIEW_NEW = ("  applyView(cfg.view);\n"
                  "  if (!window.__keep && (!window.__inited || window.__fresh)) { const m = DATA.clips.find(c => c.id === clip.id); if (m && m.view) window.__keep = { ...m.view, t }; }\n"
                  "  window.__inited = true; window.__fresh = false;\n  if (window.__keep) restoreRel();\n  uploadStatic(); prepareMovers(); showCounts();")
EXTRA = r"""
<script>
// --- views site: keep the camera relative to the target camera across scenes, and draw ground truth ---
function fovNow() {                 // the vertical field of view the free view is drawn with now
  if (typeof cam.fov === "number") return cam.fov;
  const el = $("gl"), K = intrinsics();
  return 2 * Math.atan(el.clientHeight / 2 / (K[1] * Math.min(el.clientWidth / clip.W, el.clientHeight / clip.H)));
}
function keepRel() {                // the free view in the frame of the target camera (view 0) at frame 0
  const C = clip.c2w[0], e = [C[0][3], C[1][3], C[2][3]];
  const RT = v => [0, 1, 2].map(c => C[0][c] * v[0] + C[1][c] * v[1] + C[2][c] * v[2]);
  return { target: RT(V3.sub(cam.target, e)), off: RT(cam.off), up: RT(cam.up), dist: cam.dist, fov: fovNow(), t };
}
function restoreRel() {
  const k = window.__keep; window.__keep = null;
  const C = clip.c2w[0], e = [C[0][3], C[1][3], C[2][3]];
  const R = v => [0, 1, 2].map(r => C[r][0] * v[0] + C[r][1] * v[1] + C[r][2] * v[2]);
  cam = { target: V3.add(R(k.target), e), off: R(k.off), up: R(k.up), dist: k.dist, fov: k.fov };
  mode = "orbit"; t = Math.min(k.t, clip.T - 1);
}
(() => {
  const ov = document.createElement("canvas"), cache = {};
  ov.style.cssText = "position:absolute;left:0;top:0;pointer-events:none;z-index:1";
  $("view").appendChild(ov); $("inset").style.zIndex = 2;
  let on = true, G = null, name = null;
  const draw0 = draw;
  draw = function (k) { draw0(k); paint(); };
  function paint() {
    const el = $("gl"), w = el.clientWidth, h = el.clientHeight, px = devicePixelRatio;
    ov.width = Math.round(w * px); ov.height = Math.round(h * px); ov.style.width = w + "px"; ov.style.height = h + "px";
    const g = ov.getContext("2d"); g.setTransform(px, 0, 0, px, 0, 0); g.clearRect(0, 0, w, h);
    const meta = clip && DATA.clips.find(c => c.id === clip.id);
    if (!on || !meta || !meta.gt || !window.__M) return;
    if (name !== meta.gt) {
      name = meta.gt; G = null;
      (cache[name] = cache[name] || fetch(`data/gt_${name}.json${VQ}`).then(r => r.json())).then(d => { if (name === meta.gt) { G = d; draw(); } });
      return;
    }
    if (!G) return;
    const M = window.__M, C = clip.c2w[t], sc = Math.min(1.8, Math.max(0.7, w / (meta.dotref || 900))), rad = (meta.dot || 3) * sc;
    g.fillStyle = "#3bff6b"; g.strokeStyle = "#063d1c"; g.lineWidth = 1.1 * sc;   // the video's bright ground truth
    for (let i = 0; i < G.gt[t].length; i++) {
      if (!G.vis[t][i]) continue;
      const q = G.gt[t][i].map(v => v / 1000), X = [0, 1, 2].map(r => C[r][0] * q[0] + C[r][1] * q[1] + C[r][2] * q[2] + C[r][3]);
      const x = M[0] * X[0] + M[4] * X[1] + M[8] * X[2] + M[12], y = M[1] * X[0] + M[5] * X[1] + M[9] * X[2] + M[13], ww = M[3] * X[0] + M[7] * X[1] + M[11] * X[2] + M[15];
      if (ww <= 0) continue;
      g.beginPath(); g.arc((x / ww + 1) / 2 * w, (1 - y / ww) / 2 * h, rad, 0, 7); g.fill(); g.stroke();
    }
  }
  window.addEventListener("message", e => { const m = e.data; if (m && m.type === "scale4d-gt") { on = !!m.on; draw(); } });
})();
// as in the video: trails off (they hide the ground truth); the site can turn them back on with the Trails button
showTrails = false; $("vTrails").setAttribute("aria-pressed", "false");
</script>
"""

# The site drives play / pause (scale4d-play) and, for side-by-side panes, one clock (scale4d-sync {t}) and one camera:
# a pane the visitor has touched posts its free view relative to its target camera (scale4d-cam), and the page hands
# it to the other pane (scale4d-sync {rel}), the same carry the video used between cameras-on and cameras-off pages.
PLAY = r"""
<script>
window.addEventListener("message", e => {
  const m = e.data;
  if (m && m.type === "scale4d-play" && clip && !!m.on !== playing) $("play").click();
});
</script>
"""
DUO = r"""
<script>
(() => {
  let touched = false, applying = false, last = "";
  const key = () => { const r = keepRel(); return JSON.stringify([r.target, r.off, r.up, r.dist].flat().map(v => +v.toFixed(5))); };
  for (const ev of ["pointerdown", "wheel", "touchstart", "keydown"]) window.addEventListener(ev, () => { touched = true; }, { passive: true, capture: true });
  const draw1 = draw;
  draw = function (k) {
    draw1(k);
    if (!touched || applying || !cam || !clip || parent === window) return;
    const s = key();
    if (s !== last) { last = s; parent.postMessage({ type: "scale4d-cam", id: clip.id, rel: keepRel() }, "*"); }
  };
  window.addEventListener("message", e => {
    const m = e.data;
    if (!m || m.type !== "scale4d-sync" || !clip || !cam) return;
    if (playing) { playing = false; $("play").textContent = "▶"; }
    applying = true;
    if (m.rel) { window.__keep = { ...m.rel, t }; restoreRel(); refresh(); }
    if (typeof m.t === "number" && m.t !== t) setFrame(m.t);
    applying = false; last = key();
  });
  if (new URLSearchParams(location.search).has("duo")) {          // the page's own bar is replaced by the site's
    const st = document.createElement("style");
    st.textContent = "header, .viewbtns { display:none !important } main { height:100vh !important } #view { height:100vh !important }" +
      (new URLSearchParams(location.search).has("noinset") ? " #inset { display:none !important }" : "");
    document.head.appendChild(st);
  }
})();
</script>
"""

VIEWS_SET = {   # Beyond three views: cameras on, 1..10 views
    "out": "views", "cases": CLIPS, "modes": [("on", "v{V}")], "counts": range(1, 11),
    "page": lambda clip, mode, V: SRC / f"site/views/{clip}/v{V}", "gt": lambda clip: SRC / f"traj/gt_{clip}.json"}
CAMERA_SET = {  # Cameras optional: Di's camera ON/OFF examples, three views; the video's ADT example first
    "out": "camera", "cases": {"adt_skeleton": "ADT · decoration", "dexycb_subject05": "DexYCB · subject 05",
                               "dexycb_subject02": "DexYCB · subject 02"},
    "modes": [("on", None), ("off", None)], "counts": [3],
    "page": lambda case, mode, V: SRC / f"site/camcond/{case}/{mode}", "gt": lambda case: SRC / f"camcond/gt_{case}.json"}

SELFTRAIN_SET = {   # Camera-asymmetric self-training: the video's Ranch example (Show3D, three views, cameras off at
    # inference), controlled baseline (B2) | our self-training (B3), with the video's ground truth (every 6th object query)
    "out": "selftrain", "cases": {"ranch": "Show3D · hand holding a bottle"}, "modes": [("B2", None), ("B3", None)], "counts": [3],
    "page": lambda case, mode, V: SRC / f"site/selfimp_obj/{case}/{mode}/off", "gt": lambda case: SRC / f"selfimp/obj/gt_{case}_sub6.json"}


def pack(S):
    out = Path(__file__).resolve().parents[1] / "assets" / S["out"]
    global OUT
    OUT = out
    if (out / "data").exists():
        shutil.rmtree(out / "data")      # only this set's scenes
    pages, clips = {}, []
    for case in S["cases"]:
        for mode, _ in S["modes"]:
            for V in S["counts"]:
                page = S["page"](case, mode, V)
                src = [q.name for q in (page / "data").iterdir() if q.is_dir()][0]
                sid = src if all(c["id"] != src for c in clips) else f"{src}_{mode}"   # B2 / B3 runs of one input share a sid
                if sid != src:
                    for c in clips:
                        if c["id"] == src:                       # rename the first one too, so both say which arm they are
                            first = next(m for m, v in pages[case].items() if src in v)
                            rename(src, f"{src}_{first}"); c["id"] = f"{src}_{first}"; pages[case][first] = [f"{src}_{first}"]
                pages.setdefault(case, {}).setdefault(mode, []).append(sid)
                scene = json.loads((page / f"data/{src}.scene.json").read_text())
                clips.append({"id": sid, "n": 0, "T": scene["T"], "gt": case, "dot": DOT.get(case, 3.0), "dotref": START[case]["tile"][0],
                              "view": start_view(case, S)})
                copy_page(page, src, sid)
    template = (S["page"](next(iter(S["cases"])), S["modes"][0][0], S["counts"][0]) / "index.html").read_text()
    template = re.sub(r"^const DATA = \{.*\};$", "const DATA = " + json.dumps({"mode": "view", "clips": clips}) + ";", template, count=1, flags=re.M)
    for old, new in ((PATCH_LOAD_OLD, PATCH_LOAD_NEW), (PATCH_VIEW_OLD, PATCH_VIEW_NEW)):
        assert template.count(old) == 1, old
        template = template.replace(old, new)
    assert "window.__M = M;" in template, "the draw() matrix hook is missing"
    extra = EXTRA + PLAY + DUO
    template = template.replace("</html>", extra + "</html>") if "</html>" in template else template + extra
    from theme_viewers import inject          # the page look for the embedded viewer (tools/theme_viewers.py)
    (out / "index.html").write_text(inject(template))
    for case in S["cases"]:
        shutil.copy2(S["gt"](case), out / f"data/gt_{case}.json")
    return out, pages, clips


def main():
    which = sys.argv[1:] or ["views", "camera", "selftrain"]
    if "views" in which:
        out, pages, clips = pack(VIEWS_SET)
        aj = {}
        for r in csv.DictReader(open(AJ_CSV)):
            aj.setdefault(r["dataset"], [None] * 10)[int(r["views"]) - 1] = round(float(r["aj"]), 1)
        (out / "cases.json").write_text(json.dumps({"clips": pages, "names": CLIPS, "aj": aj}, indent=1))
        print(f"{out}: {len(clips)} scenes")
    if "selftrain" in which:
        out, pages, clips = pack(SELFTRAIN_SET)
        (out / "cases.json").write_text(json.dumps({"cases": {c: {m: v[0] for m, v in d.items()} for c, d in pages.items()},
                                                    "names": SELFTRAIN_SET["cases"]}, indent=1))
        print(f"{out}: {len(clips)} scenes")
    if "camera" in which:
        out, pages, clips = pack(CAMERA_SET)
        rgb = {x["id"]: x for x in json.load(open(CAMCOND / "scores/rgb_candidates.json"))}
        scores = {c: {m: {"aj": round(rgb[c][m]["aj"], 1), "err_cm": round(rgb[c][m]["epe"], 1)} for m in ("on", "off")} for c in CAMERA_SET["cases"]}
        (out / "cases.json").write_text(json.dumps({"cases": {c: {m: v[0] for m, v in d.items()} for c, d in pages.items()},
                                                    "names": CAMERA_SET["cases"], "scores": scores}, indent=1))
        print(f"{out}: {len(clips)} scenes")


def start_view(clip, S):
    """The video's first free view, in the target camera's frame at frame 0 (OpenCV axes: x right, y down, z forward):
    aimed at the ground-truth centroid, base (off, up) turned `yaw` about up and then `pitch` about the right axis exactly
    as record.js does, with the field of view of the video's tile."""
    import math
    import numpy as np
    d = json.loads(Path(S["gt"](clip)).read_text())
    g, v = np.array(d["gt"], float) / 1000, np.array(d["vis"], bool)
    c = START[clip]

    def rotate(x, k, a):            # Rodrigues, as rotate() in the viewer
        return x * math.cos(a) + np.cross(k, x) * math.sin(a) + k * (k @ x) * (1 - math.cos(a))
    up = np.array(c["up"], float)
    off = rotate(np.array(c["off"], float), up, math.radians(c["yaw"]))
    right = np.cross(up, off); right /= np.linalg.norm(right)
    off = rotate(off, right, math.radians(c["pitch"])); off /= np.linalg.norm(off)
    ref = json.loads(next((SRC / c["ref"] / "data").glob("*.scene.json")).read_text())
    w, h = c["tile"]
    fov = c.get("fov") or 2 * math.atan(h / 2 / (ref["K"][0][1] * min(w / ref["W"], h / ref["H"])))
    return {"target": [round(float(x), 4) for x in g[v].mean(0)], "off": [round(float(x), 6) for x in off],
            "up": [round(float(x), 6) for x in up], "dist": c["dist"], "fov": round(fov, 5)}


def copy_page(page, sid, new=None):
    """Copy one scene (frames dir + scene/config files) under its own sid, or renamed to `new`."""
    new = new or sid
    d = OUT / "data"; d.mkdir(parents=True, exist_ok=True)
    if (d / new).exists():
        shutil.rmtree(d / new)
    shutil.copytree(page / "data" / sid, d / new)
    for f in (page / "data").glob(f"{sid}.*"):
        name = new + f.name[len(sid):]
        if f.name.endswith(".config.json"):
            c = json.loads(f.read_text()); c.setdefault("display", {})["mover_color"] = "rgb"
            (d / name).write_text(json.dumps(c))
        elif f.name.endswith(".scene.json"):
            c = json.loads(f.read_text()); c["id"] = new
            (d / name).write_text(json.dumps(c))
        else:
            shutil.copy2(f, d / name)


def rename(sid, new):
    d = OUT / "data"
    (d / sid).rename(d / new)
    for f in list(d.glob(f"{sid}.*")):
        if f.name.endswith(".scene.json"):
            c = json.loads(f.read_text()); c["id"] = new; f.write_text(json.dumps(c))
        f.rename(d / (new + f.name[len(sid):]))


if __name__ == "__main__":
    main()
