// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
//
// This source code is licensed under the license found in the
// LICENSE file in the root directory of this source tree.

(function () {
  const V = "?v=20261124z";   // asset version: bump with every deploy so browsers drop cached copies
  const $ = (id) => document.getElementById(id);
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- scroll spy ---------- */
  const dots = [...document.querySelectorAll(".scroll-dot")];
  const spy = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      dots.forEach((d) => d.classList.toggle("is-active", d.dataset.target === e.target.id));
    }
  }, { rootMargin: "-45% 0px -50% 0px" });
  dots.forEach((d) => spy.observe($(d.dataset.target)));
  /* top bar: shown once the hero is mostly scrolled away */
  // the Demo button appears once the live Gradio link is known (demo.json, written by the demo's supervisor on the
  // department server) and goes straight there; where there is no demo.json (GitHub Pages) it stays hidden
  fetch(`demo.json?t=${Date.now()}`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).then((d) => {
    if (d && /^https:\/\/[a-z0-9]+\.gradio\.live\/?$/.test(d.url || "")) { $("demoBtn").href = d.url; $("demoBtn").hidden = false; }
  }).catch(() => {});
  const topbar = $("topbar");
  if (topbar) new IntersectionObserver((e) => topbar.classList.toggle("is-shown", e[e.length - 1].intersectionRatio < 0.12),
    { threshold: [0, 0.12, 0.3] }).observe(document.querySelector(".hero"));

  /* ---------- hero: the title stays; resting on the background for 3 s shows the film alone ----------
     The film plays once and holds its last frame (it is cut before its own title); the page title comes back when
     the pointer leaves the hero or reaches the buttons, and when the film ends. */
  const heroEl = document.querySelector(".hero"), heroVideo = $("heroVideo");
  let idle = null;
  const showTitle = () => { clearTimeout(idle); idle = null; heroEl.classList.remove("is-video-only"); };
  heroEl.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse") return;
    if (e.target.closest(".hero-authors, .hero-actions, .scroll-hint, .scroll-nav")) { showTitle(); return; }
    if (idle || heroEl.classList.contains("is-video-only")) return;
    idle = setTimeout(() => { idle = null; if (!heroVideo.ended && !heroVideo.paused) heroEl.classList.add("is-video-only"); }, 3000);
  });
  heroEl.addEventListener("pointerleave", showTitle);
  heroEl.addEventListener("focusin", showTitle);
  heroVideo.addEventListener("ended", showTitle);
  if (calm) heroVideo.pause();

  /* ---------- benchmarks ---------- */
  const NOTE = {
    dagger: "DA3 metric depth is a model input",
    ddagger: "One per-clip median scale against DA3 metric depth",
    section: "DA3 is embedded in the released checkpoint",
    tto: "Test-time optimization",
  };
  const VIEWS = {
    single: { label: "Single-view tracking", sets: ["ADT", "PStudio", "DexYCB", "DROID"], metrics: ["AJ", "APD 3D", "OA"], block: true },
    multi: { label: "Multi-view tracking", sets: ["ADT", "PStudio", "DexYCB", "DROID"], metrics: ["AJ", "APD 3D", "OA"] },
    depth: { label: "Video depth", sets: ["ScanNet", "Bonn"], metrics: ["AbsRel", "δ 1.25", "TAE"], lower: [true, false, true] },
  };
  const S = { view: "single", block: "Metric", set: 0, metric: 0 };
  let results = null, showTable = false;

  function rowsFor() {
    if (S.view === "single") return results.tracking[S.block].map((r) => ({ name: r.method, marks: r.marks, values: r.values }));
    if (S.view === "multi") return results.multiview.map((r) => ({ name: r.depth ? `${r.method} + ${r.depth}` : r.method, marks: [], values: r.values }));
    return results.depth.map((r) => ({ name: r.method, marks: r.marks, values: r.values }));
  }
  const isOurs = (name) => name.startsWith("Ours");
  const fmt = (x) => (S.view === "depth" && (S.metric < 2) ? x.toFixed(3) : x.toFixed(2));

  function filterGroup(label, options, active, onPick) {
    const wrap = document.createElement("div"); wrap.className = "filter";
    const l = document.createElement("span"); l.className = "filter-label"; l.textContent = label;
    const seg = document.createElement("div"); seg.className = "seg seg--light"; seg.setAttribute("role", "group"); seg.setAttribute("aria-label", label);
    options.forEach((o, i) => {
      const b = document.createElement("button");
      b.textContent = o.label; b.setAttribute("aria-pressed", String(i === active));
      b.addEventListener("click", () => onPick(i));
      seg.append(b);
    });
    wrap.append(l, seg);
    return wrap;
  }
  function drawFilters() {
    const v = VIEWS[S.view], f = $("filters");
    f.replaceChildren();
    const keys = Object.keys(VIEWS);
    f.append(filterGroup("Task", keys.map((k) => ({ label: VIEWS[k].label })), keys.indexOf(S.view), (i) => { S.view = keys[i]; S.set = 0; S.metric = 0; drawAll(); }));
    if (v.block) f.append(filterGroup("Scale", [{ label: "Metric" }, { label: "Scale-aligned" }], S.block === "Metric" ? 0 : 1, (i) => { S.block = i ? "Non-metric" : "Metric"; drawAll(); }));
    f.append(filterGroup("Dataset", v.sets.map((label) => ({ label })), S.set, (i) => { S.set = i; drawAll(); }));
    f.append(filterGroup("Metric", v.metrics.map((label) => ({ label })), S.metric, (i) => { S.metric = i; drawAll(); }));
  }
  function drawBars() {
    const v = VIEWS[S.view], lower = !!(v.lower && v.lower[S.metric]);
    const idx = S.set * 3 + S.metric;
    const rows = rowsFor().map((r) => ({ ...r, v: r.values[idx] })).sort((a, b) => (lower ? a.v - b.v : b.v - a.v));
    const max = Math.max(...rows.map((r) => r.v)) * 1.14;
    const bestOther = rows.find((r) => !isOurs(r.name));
    const scale = S.view === "single" && S.block !== "Metric" ? "scale-aligned" : "metric";
    $("chartTitle").textContent = `${v.sets[S.set]}, ${v.metrics[S.metric]} (${scale})`;
    $("chartDir").textContent = lower ? "Lower is better" : "Higher is better";
    $("bars").replaceChildren(...rows.map((r) => {
      const row = document.createElement("div");
      row.className = `bar-row${isOurs(r.name) ? " is-ours" : ""}`;
      const name = document.createElement("span"); name.className = "bar-name"; name.textContent = r.name; name.title = r.name;
      const track = document.createElement("div"); track.className = "bar-track";
      const fill = document.createElement("div"); fill.className = "bar-fill"; fill.style.width = `${(r.v / max) * 100}%`;
      track.append(fill);
      if (isOurs(r.name) || r === bestOther) {
        const val = document.createElement("span"); val.className = "bar-val"; val.textContent = fmt(r.v);
        track.append(val);
      }
      row.append(name, track);
      row.addEventListener("pointerenter", (e) => showTip(e, r));
      row.addEventListener("pointermove", moveTip);
      row.addEventListener("pointerleave", hideTip);
      return row;
    }));
    const notes = {
      single: S.block === "Metric"
        ? "AJ and APD use fixed 5, 10, 20 and 40 cm thresholds. Ground truth does not set scale for any method; hover a bar to see where each baseline's scale comes from."
        : "Every method gets one per-clip median scale against ground truth, so this block compares shape, not metric scale.",
      multi: "Every method receives three synchronized views, with no ground-truth scale fitting. MVTracker takes depth from the named model as input. OmniX and ARROW predict up-to-scale tracks, scaled per clip against the named model's depth.",
      depth: "Absolute metric depth with no scale alignment, on the first 48 frames of 100 ScanNet and 5 Bonn sequences. TAE measures temporal consistency, not accuracy.",
    }[S.view];
    $("chartNote").textContent = notes;
    drawTable();
  }
  function drawTable() {
    const v = VIEWS[S.view], t = $("chartTable");
    $("bars").hidden = showTable; t.hidden = !showTable;
    $("tableToggle").textContent = showTable ? "Show chart" : "Show table";
    $("tableToggle").setAttribute("aria-pressed", String(showTable));
    if (!showTable) return;
    const table = document.createElement("table");
    const head = document.createElement("tr");
    const th = (s) => { const c = document.createElement("th"); c.textContent = s; return c; };
    head.append(th("Method"));
    v.sets.forEach((s) => v.metrics.forEach((m) => head.append(th(`${s} ${m}`))));
    table.append(head);
    for (const r of rowsFor()) {
      const tr = document.createElement("tr");
      if (isOurs(r.name)) tr.className = "is-ours";
      const td = document.createElement("td"); td.textContent = r.name; tr.append(td);
      r.values.forEach((x, i) => {
        const c = document.createElement("td");
        c.textContent = S.view === "depth" && i % 3 < 2 ? x.toFixed(3) : x.toFixed(2);
        tr.append(c);
      });
      table.append(tr);
    }
    t.replaceChildren(table);
  }
  function drawAll() { drawFilters(); drawBars(); }

  const tip = $("tooltip");
  function showTip(e, r) {
    let extra = "";
    if (S.view === "depth") extra = r.marks.includes("dagger") ? "Given the dataset focal length" : "Camera-free";
    else if (S.view === "single" && S.block !== "Metric") extra = "One per-clip median scale against ground truth";
    else if (isOurs(r.name)) extra = "No external depth model at inference";
    else extra = r.marks.map((m) => NOTE[m]).join(". ");
    tip.replaceChildren();
    const b = document.createElement("b"); b.textContent = `${r.name}: ${fmt(r.v)}`;
    tip.append(b);
    if (extra) { const s = document.createElement("span"); s.textContent = extra; tip.append(s); }
    tip.hidden = false;
    moveTip(e);
  }
  function moveTip(e) {
    const w = tip.offsetWidth, x = Math.min(e.clientX + 14, window.innerWidth - w - 8);
    tip.style.left = `${x}px`; tip.style.top = `${e.clientY + 16}px`;
  }
  function hideTip() { tip.hidden = true; }
  $("tableToggle").addEventListener("click", () => { showTable = !showTable; drawTable(); });
  fetch(`assets/data/results.json${V}`).then((r) => r.json()).then((d) => { results = d; drawAll(); });

  /* ---------- side by side in 3D: one camera, one clock (assets/compare3d, tools/pack_compare3d.py) ---------- */
  const CLIPS = [
    ["bottle", "Hands and a bottle", "HOT3D, Aria glasses"], ["plate", "Hands and a plate", "HOT3D, Aria glasses"],
    ["lift", "Lifting an object", "HOT3D, Aria glasses"], ["catdesk", "Cat on a desk", "Aria Gen 2"],
    ["catwalk", "Cat walking", "Aria Gen 2"], ["arms", "Robot arms", "Aria Gen 2"], ["pick", "Robot pick and place", "DROID"],
  ];
  const METHODS = [["spatrackerv2", "SpaTracker-v2"], ["alltracker", "AllTracker"], ["cotracker3", "CoTracker3"],
                   ["tapip3d", "TAPIP3D"], ["delta", "DELTA"], ["4rc", "4RC"]];
  const C = { clip: 0, method: 0 };
  let duoL = null, duoR = null, duoSprite = null;
  function copyCamera(a, b) {
    b.camera.position.copy(a.camera.position); b.camera.up.copy(a.camera.up);
    b.camera.fov = a.camera.fov; b.camera.updateProjectionMatrix();
    b.controls.target.copy(a.controls.target); b.camera.lookAt(b.controls.target); b.controls.update(); b.dirty = true;
  }
  function paintCmp(clipChanged) {
    const [key, title, source] = CLIPS[C.clip], [mid, label] = METHODS[C.method];
    if (duoL) {
      duoL.load("assets/compare3d", `${key}_${mid}`);
      if (clipChanged) duoR.load("assets/compare3d", `${key}_scale4d140k`);   // Ours = the released 140k checkpoint (tools/pack_compare3d.py)
    }
    $("cmpBaseTag").textContent = label;
    // what Ours receives (tools/pack_compare3d.py): the recording's camera poses on HOT3D and Aria, nothing on DROID
    const ourInput = source === "DROID" ? "the video only" : "the video and the recording's camera poses";
    $("cmpCaption").textContent = `${title}. ${source}. Ours sees ${ourInput}.`;
    [...$("clipTabs").children].forEach((b, i) => b.setAttribute("aria-selected", String(i === C.clip)));
    [...$("methodPills").querySelectorAll("button")].forEach((b, i) => b.setAttribute("aria-pressed", String(i === C.method)));
  }
  function paintDuoTime(t) {
    if (!duoR.data) return;
    const i = Math.round(t), F = duoR.data.frames;
    if (document.activeElement !== $("duoScrub") || duoR.playing) $("duoScrub").value = t;
    $("duoTime").textContent = `${i} / ${F - 1}`;
    if (duoSprite) {
      const c = i % duoSprite.cols, r = Math.floor(i / duoSprite.cols);
      $("duoInset").style.backgroundPosition = `${duoSprite.cols > 1 ? (c / (duoSprite.cols - 1)) * 100 : 0}% ${duoSprite.rows > 1 ? (r / (duoSprite.rows - 1)) * 100 : 0}%`;
    }
  }
  function startDuo() {
    try {
      duoL = new Viewer4D($("duoL"), { sway: false, version: V });
      duoR = new Viewer4D($("duoR"), { sway: false, version: V });
    } catch (e) { duoL = duoR = null; }
    if (!duoL || !duoL.supported) { $("duoLoading").textContent = "This viewer needs WebGL 2"; duoL = duoR = null; return; }
    for (const v of [duoL, duoR]) v.controls.enableDamping = false;
    duoL.setPlaying(false);
    let syncing = false, pending = 0;
    const follow = (a, b) => a.controls.addEventListener("change", () => {
      if (syncing || !b.data) return;
      syncing = true; copyCamera(a, b); syncing = false;
    });
    follow(duoL, duoR); follow(duoR, duoL);
    const loading = (on) => { pending = Math.max(0, pending + (on ? 1 : -1)); $("duoLoading").hidden = pending === 0; };
    duoL.on("loading", loading); duoR.on("loading", loading);
    // a new baseline starts from the camera and time the panes already share
    duoL.on("scene", () => { if (duoR.data) { syncing = true; copyCamera(duoR, duoL); syncing = false; duoL.setTime(duoR.t); } });
    duoR.on("scene", (m) => {
      duoSprite = m.sprite;
      const box = $("duoInset");
      box.style.aspectRatio = `${duoSprite.w} / ${duoSprite.h}`;
      box.style.backgroundImage = `url(assets/compare3d/${CLIPS[C.clip][0]}_input.jpg${V})`;
      box.style.backgroundSize = `${duoSprite.cols * 100}% ${duoSprite.rows * 100}%`;
      $("duoScrub").max = m.frames - 1;
      if (duoL.data) { syncing = true; copyCamera(duoR, duoL); syncing = false; }
    });
    duoR.on("time", (t) => { if (duoL.data && Math.abs(duoL.t - t) > 1e-4) duoL.setTime(t); paintDuoTime(t); });
    duoR.on("playing", (on) => {
      $("duoPlay").setAttribute("aria-label", on ? "Pause" : "Play");
      $("duoPlayIcon").setAttribute("d", on ? "M4 2h3v12H4zM9 2h3v12H9z" : "M4 2l10 6-10 6z");
    });
    $("duoPlay").addEventListener("click", () => duoR.setPlaying(!duoR.playing));
    $("duoScrub").addEventListener("input", (e) => { duoR.setPlaying(false); duoR.setTime(+e.target.value); });
    if (calm) duoR.setPlaying(false);
    paintCmp(true);
  }
  CLIPS.forEach(([, title], i) => {
    const b = document.createElement("button");
    b.textContent = title; b.setAttribute("role", "tab");
    b.addEventListener("click", () => { C.clip = i; paintCmp(true); });
    $("clipTabs").append(b);
  });
  const vs = document.createElement("span"); vs.textContent = "Ours vs."; $("methodPills").append(vs);
  METHODS.forEach(([, label], i) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.addEventListener("click", () => { C.method = i; paintCmp(false); });
    $("methodPills").append(b);
  });
  paintCmp(true);
  const lazyDuo = new IntersectionObserver((e, o) => {
    if (!e[0].isIntersecting) return;
    o.disconnect();
    startDuo();
  }, { rootMargin: "600px" });
  lazyDuo.observe($("duo"));
  paintCmp();

  /* ---------- Explore in 4D: the published motion viewer in an iframe, one card per scene ----------
     assets/gallery is made by tools/pack_gallery.py; the page reads the clip from its hash at load, so a new scene
     gets a new src (the query keeps the browser from treating it as the same document). */
  let wildCases = [], wildCurrent = null, wildFrameUp = false;
  const ver = V.slice(3), poster = $("wildPoster");
  function wildBar(got, total) {
    $("wildBar").style.width = total ? `${Math.min(100, (100 * got) / total).toFixed(1)}%` : "15%";
    $("wildMsg").textContent = total ? `Loading scene · ${(got / 1e6).toFixed(1)} / ${(total / 1e6).toFixed(1)} MB` : "Loading scene";
  }
  function selectWild(id) {
    wildCurrent = id;
    [...$("wildGrid").children].forEach((b) => b.setAttribute("aria-selected", String(b.dataset.id === id)));
    $("wildPosterImg").src = `assets/gallery/thumbs/${id}.jpg${V}`;   // the card while the scene loads
    wildBar(0, 0);
    poster.classList.remove("is-done");
    // the viewer page stays; it switches scenes when asked, so only the scene's own files are fetched
    if (wildFrameUp) $("wildFrame").contentWindow.postMessage({ type: "scale4d-load", id }, "*");
    else $("wildFrame").src = `assets/gallery/index.html?embed=1&v=${ver}#${id}`;
  }
  $("wildFrame").addEventListener("load", () => { wildFrameUp = true; });
  let wildStyle = "surface";        // Surface: the scene's own look; Point cloud: every tracked point as a dot
  const sendStyle = () => { if (wildFrameUp) $("wildFrame").contentWindow.postMessage({ type: "scale4d-style", style: wildStyle }, "*"); };
  [...$("wildStyle").children].forEach((b) => b.addEventListener("click", () => {
    wildStyle = b.dataset.style;
    [...$("wildStyle").children].forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    sendStyle();
  }));
  window.addEventListener("message", (e) => {
    const m = e.data;
    if (!m || typeof m.id !== "string" || m.id.replace(/\.scene$/, "") !== wildCurrent) return;
    if (m.type === "scale4d-progress" && m.total >= 0) wildBar(m.got, m.total);
    if (m.type === "scale4d-ready") { poster.classList.add("is-done"); if (wildStyle !== "surface") sendStyle(); }
  });
  const warmed = new Set();         // a card held under the pointer starts its download (same cache as the viewer)
  function warm(id) {
    if (warmed.has(id) || id === wildCurrent) return;
    warmed.add(id);
    for (const f of [`${id}.scene.json`, `${id}.scene.bin`]) fetch(`assets/gallery/data/${f}?v=${ver}`).catch(() => warmed.delete(id));
  }
  fetch(`assets/gallery/cases.json${V}`).then((r) => r.json()).then((cases) => {
    wildCases = cases;
    const ORDER = ["Robot Manipulation", "Hand and Object Interaction", "In the wild captures", "DAVIS"];   // the video's chapters 02-04, then DAVIS
    const rank = (k) => (ORDER.includes(k) ? ORDER.indexOf(k) : ORDER.length);
    const kinds = ["All", ...[...new Set(cases.map((c) => c.kind))].filter((k) => cases.filter((c) => c.kind === k).length >= 3).sort((a, b) => rank(a) - rank(b))];
    const counts = Object.fromEntries(kinds.map((k) => [k, k === "All" ? cases.length : cases.filter((c) => c.kind === k).length]));
    let kindOn = "All";
    const grid = $("wildGrid"), more = $("wildMore");
    function paintFilter() {
      [...$("wildFilter").children].forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.kind === kindOn)));
      [...grid.children].forEach((b) => { b.hidden = kindOn !== "All" && b.dataset.kind !== kindOn; });
      let shown = 0;
      [...grid.children].forEach((b) => { if (!b.hidden) shown++; b.toggleAttribute("data-extra", !b.hidden && shown > 16); });
      more.hidden = !grid.classList.contains("is-collapsed") || shown <= 16;
      more.textContent = `Show all ${shown} scenes`;
    }
    for (const k of kinds) {
      const f = document.createElement("button");
      f.dataset.kind = k; f.textContent = `${k} ${counts[k]}`;
      f.addEventListener("click", () => { kindOn = k; paintFilter(); });
      $("wildFilter").append(f);
    }
    more.addEventListener("click", () => { grid.classList.remove("is-collapsed"); paintFilter(); });
    for (const c of cases) {
      const b = document.createElement("button");
      b.dataset.kind = c.kind;
      b.className = "wild-card";
      b.dataset.id = c.id;
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", "false");
      b.innerHTML = `<img src="assets/gallery/thumbs/${c.id}.jpg${V}" alt="" loading="lazy"><span><b>${c.kind}</b>${c.setup}</span>`;
      b.addEventListener("click", () => selectWild(c.id));
      let hold = null;
      b.addEventListener("pointerenter", () => { hold = setTimeout(() => warm(c.id), 250); });
      b.addEventListener("pointerleave", () => clearTimeout(hold));
      $("wildGrid").append(b);
    }
    paintFilter();
    const lazyWild = new IntersectionObserver((e, o) => {
      if (!e[0].isIntersecting) return;
      o.disconnect();
      if (!wildCurrent && wildCases.length) selectWild(wildCases[0].id);
    }, { rootMargin: "1200px" });
    lazyWild.observe($("wildStage"));
  });
  /* ---------- Zero-shot multi view inference: Di's two view-count clips, 3-10 views (the video's range; the 1- and 2-view
     scenes stay in assets/views but are not offered), cameras on ----------
     assets/views is made by tools/pack_views.py. Changing the view count or the cameras sends keep: true, so the
     camera stays put relative to the target camera while the reconstruction changes. */
  const VW0 = 3;                    // first view count offered (user: "从3开始所以12都不要了")
  const vwS = { clip: null, n: VW0, cam: "on", gt: true };   // the video starts at three views
  let vwCases = null, vwCurrent = null, vwUp = false;
  const vwPoster = $("viewsPoster");
  function vwBar(got, total) {
    $("viewsBar").style.width = total ? `${Math.min(100, (100 * got) / total).toFixed(1)}%` : "15%";
    $("viewsMsg").textContent = total ? `Loading scene · ${(got / 1e6).toFixed(1)} / ${(total / 1e6).toFixed(1)} MB` : "Loading scene";
  }
  function vwChart() {               // AJ with cameras on (per clip), the current view count marked
    const aj = vwCases.aj[vwS.clip], w = 300, h = 168, pl = 30, pr = 14, pt = 16, pb = 34;
    const X = (v) => pl + ((v - VW0) / (10 - VW0)) * (w - pl - pr), Y = (a) => pt + (1 - a / 100) * (h - pt - pb);
    const vs = []; for (let v = VW0; v <= 10; v++) vs.push(v);
    let s = `<svg viewBox="0 0 ${w} ${h}" width="100%" role="img" aria-label="AJ versus number of input views">`;
    s += `<rect x="${(X(3) + X(4)) / 2}" y="${pt}" width="${X(10) + 10 - (X(3) + X(4)) / 2}" height="${h - pt - pb}" fill="#e07a2e" opacity="0.08"/>`;
    s += `<text x="${(X(4) + X(10)) / 2}" y="${h - pb - 6}" font-size="11" fill="#c4621c" text-anchor="middle" font-style="italic">zero-shot</text>`;
    for (const a of [0, 25, 50, 75, 100]) s += `<line x1="${pl}" x2="${w - pr}" y1="${Y(a)}" y2="${Y(a)}" stroke="#ececec"/><text x="${pl - 6}" y="${Y(a) + 3.5}" font-size="10" fill="#8a8a8a" text-anchor="end">${a}</text>`;
    for (const v of vs) s += `<text x="${X(v)}" y="${h - pb + 14}" font-size="10" fill="#8a8a8a" text-anchor="middle">${v}</text>`;
    s += `<text x="${(pl + w - pr) / 2}" y="${h - 3}" font-size="11" fill="#333" text-anchor="middle">input views</text>`;
    s += `<text x="9" y="${(pt + h - pb) / 2}" font-size="11" fill="#333" text-anchor="middle" transform="rotate(-90 9 ${(pt + h - pb) / 2})">AJ</text>`;
    s += `<polyline points="${vs.map((v) => `${X(v)},${Y(aj[v - 1])}`).join(" ")}" fill="none" stroke="#112D4E" stroke-width="2"/>`;
    vs.forEach((v) => { const on = v === vwS.n; s += `<circle cx="${X(v)}" cy="${Y(aj[v - 1])}" r="${on ? 5.5 : 3}" fill="${on ? "#e07a2e" : "#112D4E"}" stroke="#fff" stroke-width="1.5"/>`; });
    const a = aj[vwS.n - 1];   // the first point sits on the axis: its label starts there, clear of the tick labels (as in the video)
    s += `<text x="${X(vwS.n) + (vwS.n <= VW0 ? 6 : 0)}" y="${Y(a) - 10}" font-size="12" font-weight="600" fill="#111" stroke="#fff" stroke-width="4" stroke-linejoin="round" paint-order="stroke" text-anchor="${vwS.n >= 9 ? "end" : vwS.n <= VW0 ? "start" : "middle"}">${a.toFixed(1)}</text></svg>`;   // white halo: the value never sits on the line
    $("viewsChart").innerHTML = s + `<p class="views-chart-note">AJ with cameras on</p>`;
  }
  function vwPaint() {
    [...$("viewsClip").children].forEach((b) => b.setAttribute("aria-selected", String(b.dataset.clip === vwS.clip)));
    [...$("viewsBtns").children].forEach((b) => b.setAttribute("aria-pressed", String(+b.dataset.n === vwS.n)));
    $("viewsN").textContent = vwS.n;
    vwChart();
  }
  function vwLoad(keep) {
    vwPaint();
    const id = vwCases.clips[vwS.clip][vwS.cam][vwS.n - 1];
    if (id === vwCurrent) return;
    vwCurrent = id;
    if (!keep) { vwBar(0, 0); vwPoster.classList.remove("is-done"); }
    if (vwUp) $("viewsFrame").contentWindow.postMessage({ type: "scale4d-load", id, keep }, "*");
    else $("viewsFrame").src = `assets/views/index.html?embed=1&v=${ver}#${id}`;
  }
  $("viewsFrame").addEventListener("load", () => { vwUp = true; });
  window.addEventListener("message", (e) => {
    const m = e.data;
    if (!m || typeof m.id !== "string" || m.id.replace(/\.scene$/, "") !== vwCurrent) return;
    if (m.type === "scale4d-progress" && m.total >= 0) vwBar(m.got, m.total);
    if (m.type === "scale4d-ready") {
      vwPoster.classList.add("is-done");
      $("viewsFrame").contentWindow.postMessage({ type: "scale4d-gt", on: vwS.gt }, "*");
      $("viewsFrame").contentWindow.postMessage({ type: "scale4d-play", on: vwSeen && !calm }, "*");   // it plays, as in the video
    }
  });
  const lazyViews = new IntersectionObserver((e, o) => {
    if (!e[0].isIntersecting) return;
    o.disconnect();
    fetch(`assets/views/cases.json${V}`).then((r) => r.json()).then((cases) => {
      vwCases = cases; vwS.clip = Object.keys(cases.names)[0];
      for (const [k, name] of Object.entries(cases.names)) {
        const b = document.createElement("button"); b.dataset.clip = k; b.textContent = name; b.setAttribute("role", "tab");
        b.addEventListener("click", () => { if (vwS.clip !== k) { vwS.clip = k; vwLoad(false); } });
        $("viewsClip").append(b);
      }
      for (let n = VW0; n <= 10; n++) {
        const b = document.createElement("button"); b.dataset.n = n; b.textContent = n;
        if (n > 3) { b.classList.add("is-zero"); b.title = "Zero-shot: more views than seen in training"; }
        b.addEventListener("click", () => { vwS.n = n; vwLoad(true); });
        $("viewsBtns").append(b);
      }
      $("viewsGT").addEventListener("change", () => { vwS.gt = $("viewsGT").checked; if (vwUp) $("viewsFrame").contentWindow.postMessage({ type: "scale4d-gt", on: vwS.gt }, "*"); });
      vwLoad(false);
    });
  }, { rootMargin: "1200px" });
  lazyViews.observe($("viewsStage"));
  let vwSeen = false;               // play while on screen
  new IntersectionObserver((e) => {
    vwSeen = e[e.length - 1].isIntersecting;
    if (vwUp) $("viewsFrame").contentWindow.postMessage({ type: "scale4d-play", on: vwSeen && !calm }, "*");
  }, { threshold: 0.3 }).observe($("viewsStage"));
  /* ---------- Cameras optional: cameras on | off side by side, as in the supplementary video (the ADT example and
     its angle first; assets/camera, tools/pack_views.py). The page runs one clock for both panes; the pane the visitor
     drags posts its view relative to its target camera (scale4d-cam) and the other pane takes it (scale4d-sync). ---------- */
  const cmS = { c: null, gt: true, t: 0, playing: !calm, seen: false };
  const cmFrames = [...document.querySelectorAll("#camPair iframe")], cmPosters = [...document.querySelectorAll("#camPair .wild-poster")];
  const CM_MODES = ["on", "off"], CM_T = 48;   // every camera scene is 48 frames
  let cmCases = null, cmReady = [false, false], cmUp = [false, false], cmTimer = null;
  const cmPost = (i, m) => { if (cmReady[i]) cmFrames[i].contentWindow.postMessage(m, "*"); };
  const cmAll = (m) => cmFrames.forEach((_, i) => cmPost(i, m));
  function cmBar(i, got, total) {
    cmPosters[i].querySelector("i").style.width = total ? `${Math.min(100, (100 * got) / total).toFixed(1)}%` : "15%";
    cmPosters[i].querySelector("span").textContent = total ? `Loading scene · ${(got / 1e6).toFixed(1)} / ${(total / 1e6).toFixed(1)} MB` : "Loading scene";
  }
  function cmSetT(v) { cmS.t = v; $("camScrub").value = v; $("camTime").textContent = `${v} / ${CM_T - 1}`; cmAll({ type: "scale4d-sync", t: v }); }
  function cmTick() {
    const run = cmS.playing && cmS.seen && cmReady.every(Boolean);
    if (run && !cmTimer) cmTimer = setInterval(() => cmSetT((cmS.t + 1) % CM_T), 125);   // the viewer's own 8 frames per second
    if (!run && cmTimer) { clearInterval(cmTimer); cmTimer = null; }
  }
  function cmPaintPlay() {
    $("camPlay").setAttribute("aria-label", cmS.playing ? "Pause" : "Play");
    $("camPlayIcon").setAttribute("d", cmS.playing ? "M4 2h3v12H4zM9 2h3v12H9z" : "M4 2l10 6-10 6z");
  }
  function cmLoad() {
    [...$("camCase").children].forEach((b) => b.setAttribute("aria-selected", String(b.dataset.c === cmS.c)));
    CM_MODES.forEach((mode, i) => {
      const id = cmCases.cases[cmS.c][mode];
      cmReady[i] = false; cmBar(i, 0, 0); cmPosters[i].classList.remove("is-done");
      if (cmUp[i]) cmFrames[i].contentWindow.postMessage({ type: "scale4d-load", id }, "*");   // a new case opens at its own start view
      else cmFrames[i].src = `assets/camera/index.html?embed=1&duo=1${i ? "&noinset=1" : ""}&v=${ver}#${id}`;
    });
    cmSetT(0); cmTick();
  }
  cmFrames.forEach((f, i) => f.addEventListener("load", () => { cmUp[i] = f.src.includes("index.html"); }));
  window.addEventListener("message", (e) => {
    const i = cmFrames.findIndex((f) => f.contentWindow === e.source), m = e.data;
    if (i < 0 || !m) return;
    if (m.type === "scale4d-progress" && m.total >= 0) cmBar(i, m.got, m.total);
    if (m.type === "scale4d-ready") {
      cmReady[i] = true; cmPosters[i].classList.add("is-done");
      cmPost(i, { type: "scale4d-gt", on: cmS.gt }); cmPost(i, { type: "scale4d-sync", t: cmS.t });
      cmTick();
    }
    if (m.type === "scale4d-cam") cmFrames.forEach((_, j) => { if (j !== i) cmPost(j, { type: "scale4d-sync", rel: m.rel }); });
  });
  $("camPlay").addEventListener("click", () => { cmS.playing = !cmS.playing; cmPaintPlay(); cmTick(); });
  $("camScrub").addEventListener("input", () => { cmS.playing = false; cmPaintPlay(); cmTick(); cmSetT(+$("camScrub").value); });
  $("camGT").addEventListener("change", () => { cmS.gt = $("camGT").checked; cmAll({ type: "scale4d-gt", on: cmS.gt }); });
  $("camFS").addEventListener("click", () => { if (document.fullscreenElement) document.exitFullscreen(); else if ($("camPair").requestFullscreen) $("camPair").requestFullscreen(); });
  cmPaintPlay();
  new IntersectionObserver((e) => { cmS.seen = e[e.length - 1].isIntersecting; cmTick(); }, { threshold: 0.3 }).observe($("camPair"));
  const lazyCam = new IntersectionObserver((e, o) => {
    if (!e[0].isIntersecting) return;
    o.disconnect();
    fetch(`assets/camera/cases.json${V}`).then((r) => r.json()).then((cases) => {
      cmCases = cases; cmS.c = Object.keys(cases.names)[0];
      for (const [k, name] of Object.entries(cases.names)) {
        const b = document.createElement("button"); b.dataset.c = k; b.textContent = name; b.setAttribute("role", "tab");
        b.addEventListener("click", () => { if (cmS.c !== k) { cmS.c = k; cmLoad(); } });
        $("camCase").append(b);
      }
      cmLoad();
    });
  }, { rootMargin: "1200px" });
  lazyCam.observe($("camPair"));
  /* ---------- Self-training: the video's Ranch example, controlled baseline | our self-training (cameras off at
     inference), one clock and one camera like Cameras optional (assets/selftrain, tools/pack_views.py selftrain) ---------- */
  (() => {
    const root = $("stPair"); if (!root) return;
    const frames = [...root.querySelectorAll("iframe")], posters = [...root.querySelectorAll(".wild-poster")];
    const ARMS = ["B2", "B3"], T = 48;
    const S = { gt: true, t: 0, playing: !calm, seen: false };
    let cases = null, ready = [false, false], timer = null;
    const post = (i, m) => { if (ready[i]) frames[i].contentWindow.postMessage(m, "*"); };
    const all = (m) => frames.forEach((_, i) => post(i, m));
    const bar = (i, got, total) => {
      posters[i].querySelector("i").style.width = total ? `${Math.min(100, (100 * got) / total).toFixed(1)}%` : "15%";
      posters[i].querySelector("span").textContent = total ? `Loading scene · ${(got / 1e6).toFixed(1)} / ${(total / 1e6).toFixed(1)} MB` : "Loading scene";
    };
    const setT = (v) => { S.t = v; $("stScrub").value = v; $("stTime").textContent = `${v} / ${T - 1}`; all({ type: "scale4d-sync", t: v }); };
    const tick = () => {
      const run = S.playing && S.seen && ready.every(Boolean);
      if (run && !timer) timer = setInterval(() => setT((S.t + 1) % T), 125);
      if (!run && timer) { clearInterval(timer); timer = null; }
    };
    const paintPlay = () => {
      $("stPlay").setAttribute("aria-label", S.playing ? "Pause" : "Play");
      $("stPlayIcon").setAttribute("d", S.playing ? "M4 2h3v12H4zM9 2h3v12H9z" : "M4 2l10 6-10 6z");
    };
    window.addEventListener("message", (e) => {
      const i = frames.findIndex((f) => f.contentWindow === e.source), m = e.data;
      if (i < 0 || !m) return;
      if (m.type === "scale4d-progress" && m.total >= 0) bar(i, m.got, m.total);
      if (m.type === "scale4d-ready") {
        ready[i] = true; posters[i].classList.add("is-done");
        post(i, { type: "scale4d-gt", on: S.gt }); post(i, { type: "scale4d-sync", t: S.t }); tick();
      }
      if (m.type === "scale4d-cam") frames.forEach((_, j) => { if (j !== i) post(j, { type: "scale4d-sync", rel: m.rel }); });
    });
    $("stPlay").addEventListener("click", () => { S.playing = !S.playing; paintPlay(); tick(); });
    $("stScrub").addEventListener("input", () => { S.playing = false; paintPlay(); tick(); setT(+$("stScrub").value); });
    $("stGT").addEventListener("change", () => { S.gt = $("stGT").checked; all({ type: "scale4d-gt", on: S.gt }); });
    $("stFS").addEventListener("click", () => { if (document.fullscreenElement) document.exitFullscreen(); else if (root.requestFullscreen) root.requestFullscreen(); });
    paintPlay();
    new IntersectionObserver((e) => { S.seen = e[e.length - 1].isIntersecting; tick(); }, { threshold: 0.3 }).observe(root);
    new IntersectionObserver((e, o) => {
      if (!e[0].isIntersecting) return;
      o.disconnect();
      fetch(`assets/selftrain/cases.json${V}`).then((r) => r.json()).then((c) => {
        cases = c; const k = Object.keys(c.names)[0];
        ARMS.forEach((arm, i) => { bar(i, 0, 0); frames[i].src = `assets/selftrain/index.html?embed=1&duo=1${i ? "&noinset=1" : ""}&v=${ver}#${c.cases[k][arm]}`; });
        setT(0); tick();
      });
    }, { rootMargin: "1200px" }).observe(root);
  })();
  /* ---------- browser-side cache: the server sends no Cache-Control, so sw.js keeps every versioned file (?v=) after
     its first download; revisits and scene switches then load from disk. A new V starts a new cache. ---------- */
  if ("serviceWorker" in navigator && window.isSecureContext)
    addEventListener("load", () => navigator.serviceWorker.register(`sw.js${V}`).catch(() => {}));
})();
