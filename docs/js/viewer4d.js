// Copyright (c) Meta Platforms, Inc. and affiliates.
// All rights reserved.
//
// This source code is licensed under the license found in the
// LICENSE file in the root directory of this source tree.

/* Viewer4D: plays a packed 4D scene in WebGL2.
   Moving points live in a float texture and are positioned in the vertex shader, so playback costs one uniform
   per frame and time can be fractional. Trails are one fat-line buffer sorted by time; playing them is only a
   change of instance count. */
(function () {
  const TEX_W = 4096;
  const turbo = (x) => {
    x = Math.min(1, Math.max(0, x));
    const r = 0.13572138 + x * (4.6153926 + x * (-42.66032258 + x * (132.13108234 + x * (-152.94239396 + x * 59.28637943))));
    const g = 0.09140261 + x * (2.19418839 + x * (4.84296658 + x * (-14.18503333 + x * (4.27729857 + x * 2.82956604))));
    const b = 0.1066733 + x * (12.64194608 + x * (-60.58204836 + x * (110.36276771 + x * (-89.90310912 + x * 27.34824973))));
    return [r, g, b].map((v) => Math.min(1, Math.max(0, v)));
  };
  const TYPED = { int16: Int16Array, uint8: Uint8Array, uint16: Uint16Array };
  const unpack = (buf, layout) => {
    const o = {};
    for (const [k, l] of Object.entries(layout)) o[k] = new TYPED[l.dtype](buf, l.offset, l.shape.reduce((a, b) => a * b, 1));
    return o;
  };

  const pointFrag = `
    uniform float uAlpha; varying vec3 vRgb;
    void main() { vec2 c = gl_PointCoord - 0.5; if (dot(c, c) > 0.25) discard; gl_FragColor = vec4(vRgb, uAlpha); }`;
  const staticVert = `
    attribute vec3 rgb; attribute float radius;
    uniform float uScale, uSize;
    varying vec3 vRgb;
    void main() {
      vRgb = rgb;
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      gl_Position = projectionMatrix * mv;
      gl_PointSize = max(1.0, 2.0 * radius * uSize * uScale / max(-mv.z, 1e-4));
    }`;
  const dynamicVert = `
    attribute vec3 rgb; attribute float radius;
    uniform highp sampler2D uTraj;
    uniform float uT, uScale, uSize; uniform int uF, uCols;
    varying vec3 vRgb;
    void main() {
      int id = int(position.x + 0.5);
      int t0 = int(floor(uT)), t1 = min(t0 + 1, uF - 1);
      int col = id % uCols, row = id / uCols;
      vec4 a = texelFetch(uTraj, ivec2(col * uF + t0, row), 0);
      vec4 b = texelFetch(uTraj, ivec2(col * uF + t1, row), 0);
      if (a.w < 0.5 && b.w < 0.5) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 0.0; return; }
      float f = a.w < 0.5 ? 1.0 : b.w < 0.5 ? 0.0 : uT - float(t0);
      vec4 mv = modelViewMatrix * vec4(mix(a.xyz, b.xyz, f), 1.0);
      vRgb = rgb;
      gl_Position = projectionMatrix * mv;
      gl_PointSize = max(1.0, 2.0 * radius * uSize * uScale / max(-mv.z, 1e-4));
    }`;

  class Viewer4D {
    constructor(canvas, opts = {}) {
      this.canvas = canvas;
      this.opts = Object.assign({ background: 0x0b0d10, pixelRatio: Math.min(window.devicePixelRatio || 1, 2), sway: true, fps: 12 }, opts);
      this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: !!opts.capture });
      this.renderer.setClearColor(this.opts.background, 1);
      this.renderer.setPixelRatio(this.opts.pixelRatio);
      this.supported = this.renderer.capabilities.isWebGL2;
      this.scene = new THREE.Scene();
      this.camera = new THREE.PerspectiveCamera(40, 16 / 9, 0.01, 200);
      this.controls = new THREE.OrbitControls(this.camera, canvas);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.08;
      this.controls.screenSpacePanning = true;
      this.shared = { uScale: { value: 500 }, uSize: { value: 1 } };
      this.t = 0; this.playing = true; this.speed = 1; this.mode = "orbit";
      this.showTracks = true; this.showCam = true;
      this.visible = true; this.dirty = true; this.touched = false;
      this.listeners = {};
      this.data = null;
      this.token = 0;
      this.last = 0;
      this.elapsed = 0;
      this.tick = this.tick.bind(this);
      // the wheel keeps scrolling the page until the visitor engages with the scene
      this.controls.enableZoom = false;
      canvas.addEventListener("pointerdown", () => { this.touched = true; this.controls.enableZoom = true; });
      canvas.addEventListener("pointerleave", () => { this.controls.enableZoom = false; });
      this.controls.addEventListener("change", () => { this.dirty = true; });
      if (!opts.capture) {
        new ResizeObserver(() => this.resize()).observe(canvas.parentElement);
        new IntersectionObserver((e) => { this.visible = e[0].isIntersecting; this.last = 0; }).observe(canvas);
        requestAnimationFrame(this.tick);
      }
      this.resize();
    }

    on(name, fn) { (this.listeners[name] = this.listeners[name] || []).push(fn); }
    emit(name, ...args) { (this.listeners[name] || []).forEach((fn) => fn(...args)); }

    resize(w, h) {
      if (w === undefined) { const box = this.canvas.parentElement; w = box.clientWidth; h = box.clientHeight; }
      if (!w || !h) return;
      this.renderer.setSize(w, h, false);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.dirty = true;
    }

    clear() {
      for (const o of [this.statics, this.moving, this.lines, this.frustum, this.path]) {
        if (!o) continue;
        this.scene.remove(o); o.geometry.dispose(); o.material.dispose();
      }
      if (this.traj) this.traj.dispose();
      this.statics = this.moving = this.lines = this.frustum = this.path = this.traj = null;
    }

    async load(base, key) {
      const my = ++this.token;
      this.emit("loading", true);
      const [meta, buf] = await Promise.all([
        fetch(`${base}/${key}.json${this.opts.version || ""}`).then((r) => r.json()),
        fetch(`${base}/${key}.bin${this.opts.version || ""}`).then((r) => r.arrayBuffer()),
      ]);
      if (my !== this.token) return;
      this.clear();
      this.data = meta;
      this.t = 0; this.touched = false; this.elapsed = 0;
      this.build(meta, unpack(buf, meta.layout));
      this.resetView();
      this.emit("loading", false);
      this.emit("scene", meta);
      this.emit("time", 0);
      this.dirty = true;
    }

    build(m, b) {
      const F = m.frames, D = m.dynamic, S = m.static;
      const ptMat = (vert, extra) => new THREE.ShaderMaterial({
        uniforms: { ...this.shared, uAlpha: { value: 1 }, ...extra }, vertexShader: vert, fragmentShader: pointFrag, transparent: false,
      });

      // static surface
      const sPos = new Float32Array(S * 3), sRad = new Float32Array(S);
      for (let i = 0; i < S * 3; i++) sPos[i] = b.s_xyz[i] / 1000;
      for (let i = 0; i < S; i++) sRad[i] = b.s_rad[i] / 1e4;
      const sg = new THREE.BufferGeometry();
      sg.setAttribute("position", new THREE.BufferAttribute(sPos, 3));
      sg.setAttribute("rgb", new THREE.BufferAttribute(b.s_rgb, 3, true));
      sg.setAttribute("radius", new THREE.BufferAttribute(sRad, 1));
      this.statics = new THREE.Points(sg, ptMat(staticVert, { uSize: { value: 1.75 } }));
      this.statics.frustumCulled = false;
      this.scene.add(this.statics);

      // moving points: xyz + visibility per point and frame, addressed by texelFetch
      const cols = Math.floor(TEX_W / F), rows = Math.ceil(D / cols);
      const tex = new Float32Array(cols * F * rows * 4);
      for (let i = 0; i < D; i++) {
        const col = i % cols, row = Math.floor(i / cols);
        for (let t = 0; t < F; t++) {
          const o = (row * cols * F + col * F + t) * 4, s = (i * F + t) * 3, bit = i * F + t;
          tex[o] = b.d_traj[s] / 1000; tex[o + 1] = b.d_traj[s + 1] / 1000; tex[o + 2] = b.d_traj[s + 2] / 1000;
          tex[o + 3] = (b.d_vis[bit >> 3] >> (7 - (bit & 7))) & 1;
        }
      }
      this.traj = new THREE.DataTexture(tex, cols * F, rows, THREE.RGBAFormat, THREE.FloatType);
      this.traj.minFilter = this.traj.magFilter = THREE.NearestFilter;
      this.traj.generateMipmaps = false;
      this.traj.needsUpdate = true;
      const ids = new Float32Array(D * 3), dRad = new Float32Array(D);
      for (let i = 0; i < D; i++) { ids[i * 3] = i; dRad[i] = b.d_rad[i] / 1e4; }
      const dg = new THREE.BufferGeometry();
      dg.setAttribute("position", new THREE.BufferAttribute(ids, 3));
      dg.setAttribute("rgb", new THREE.BufferAttribute(b.d_rgb, 3, true));
      dg.setAttribute("radius", new THREE.BufferAttribute(dRad, 1));
      this.moving = new THREE.Points(dg, ptMat(dynamicVert, {
        uTraj: { value: this.traj }, uT: { value: 0 }, uF: { value: F }, uCols: { value: cols },
      }));
      this.moving.frustumCulled = false;
      this.scene.add(this.moving);

      // trails, sorted by time so that a prefix of the buffer is the history up to t
      const N = m.tracks, pos = new Float32Array(N * (F - 1) * 6), col = new Float32Array(N * (F - 1) * 6);
      let k = 0;
      for (let u = 0; u < F - 1; u++) {
        const c0 = turbo(0.04 + 0.92 * u / (F - 1)), c1 = turbo(0.04 + 0.92 * (u + 1) / (F - 1));
        for (let i = 0; i < N; i++) {
          const a = (i * F + u) * 3;
          for (let j = 0; j < 3; j++) { pos[k * 6 + j] = b.d_traj[a + j] / 1000; pos[k * 6 + 3 + j] = b.d_traj[a + 3 + j] / 1000; }
          col.set(c0, k * 6); col.set(c1, k * 6 + 3);
          k++;
        }
      }
      const lg = new THREE.LineSegmentsGeometry();
      lg.setPositions(pos); lg.setColors(col);
      this.lines = new THREE.LineSegments2(lg, new THREE.LineMaterial({ vertexColors: true, linewidth: 1.6 }));
      this.lines.frustumCulled = false;
      this.scene.add(this.lines);

      // input camera: frustum at t, path so far
      const fg = new THREE.LineSegmentsGeometry();
      fg.setPositions(new Float32Array(16 * 3));
      this.frustum = new THREE.LineSegments2(fg, new THREE.LineMaterial({ color: new THREE.Color("#ff8a3d"), linewidth: 1.8 }));
      this.frustum.frustumCulled = false;
      this.scene.add(this.frustum);
      const moved = Math.hypot(...m.cam_eye[0].map((v, i) => v - m.cam_eye[F - 1][i])) > 0.05;
      if (moved) {
        const pg = new THREE.LineSegmentsGeometry(), seg = [];
        for (let u = 0; u < F - 1; u++) seg.push(...m.cam_eye[u], ...m.cam_eye[u + 1]);
        pg.setPositions(new Float32Array(seg));
        this.path = new THREE.LineSegments2(pg, new THREE.LineMaterial({ color: new THREE.Color("#ff8a3d"), linewidth: 1.2 }));
        this.path.frustumCulled = false;
        this.scene.add(this.path);
      }
      this.applyTime();
    }

    applyTime() {
      const m = this.data;
      if (!m) return;
      const F = m.frames;
      this.moving.material.uniforms.uT.value = this.t;
      this.lines.geometry.instanceCount = m.tracks * Math.floor(this.t);
      const c = m.cams[Math.round(this.t)];
      const p = (i) => [c[i * 3], c[i * 3 + 1], c[i * 3 + 2]];
      const seg = [];
      for (let i = 1; i <= 4; i++) seg.push(...p(0), ...p(i), ...p(i), ...p(i % 4 + 1));
      const data = this.frustum.geometry.attributes.instanceStart.data;
      data.array.set(seg); data.needsUpdate = true;
      this.lines.visible = this.showTracks;
      this.frustum.visible = this.showCam && this.mode === "orbit";
      if (this.path) {
        this.path.visible = this.showCam && this.mode === "orbit";
        this.path.geometry.instanceCount = Math.max(0, Math.floor(this.t));
      }
      if (this.mode === "input") this.followInput();
      this.dirty = true;
      if (F) this.emit("time", this.t);
    }

    setTime(t) { this.t = Math.max(0, Math.min(this.data ? this.data.frames - 1 : 0, t)); this.applyTime(); }
    setPlaying(on) { this.playing = on; this.emit("playing", on); }
    setOptions(o) { Object.assign(this, o); this.applyTime(); }

    setMode(mode) {
      if (mode === this.mode) return;
      this.mode = mode;
      this.controls.enabled = mode === "orbit";
      if (mode === "orbit") this.resetView(); else this.followInput();
      this.applyTime();
    }

    followInput() {
      const m = this.data, i = Math.floor(this.t), j = Math.min(i + 1, m.frames - 1), f = this.t - i;
      const mix = (a, b) => a.map((v, k) => v + (b[k] - v) * f);
      const eye = mix(m.cam_eye[i], m.cam_eye[j]), fwd = mix(m.cam_fwd[i], m.cam_fwd[j]), up = mix(m.cam_up[i], m.cam_up[j]);
      this.camera.fov = m.fov_input;
      this.camera.updateProjectionMatrix();
      this.camera.up.set(...up).normalize();
      this.camera.position.set(...eye);
      this.camera.lookAt(eye[0] + fwd[0], eye[1] + fwd[1], eye[2] + fwd[2]);
    }

    resetView() {
      const m = this.data;
      if (!m) return;
      this.camera.fov = m.fov;
      this.camera.updateProjectionMatrix();
      this.camera.up.set(...m.up).normalize();
      this.camera.position.set(...m.eye);
      this.controls.target.set(...m.target);
      this.camera.lookAt(this.controls.target);
      this.controls.update();
      this.base = this.camera.position.clone().sub(this.controls.target);
      this.touched = false;
      this.elapsed = 0;
      this.dirty = true;
    }

    /* Slow side-to-side drift until the viewer takes over, so the depth reads straight away. */
    sway(yawDeg) {
      const v = this.base.clone().applyAxisAngle(this.camera.up, THREE.MathUtils.degToRad(yawDeg));
      this.camera.position.copy(this.controls.target).add(v);
      this.camera.lookAt(this.controls.target);
    }

    draw() {
      const gl = this.renderer.getContext();
      this.shared.uScale.value = gl.drawingBufferHeight / (2 * Math.tan((this.camera.fov * Math.PI) / 360));
      for (const o of [this.lines, this.frustum, this.path]) if (o) o.material.resolution.set(this.canvas.clientWidth || gl.drawingBufferWidth, this.canvas.clientHeight || gl.drawingBufferHeight);
      this.renderer.render(this.scene, this.camera);
    }

    tick(now) {
      requestAnimationFrame(this.tick);
      if (!this.visible || !this.data) { this.last = 0; return; }
      const dt = this.last ? Math.min((now - this.last) / 1000, 0.1) : 0;
      this.last = now;
      if (this.playing && dt) {
        const F = this.data.frames;
        this.t = (this.t + dt * this.opts.fps * this.speed) % (F - 1);
        this.elapsed += dt;
        this.applyTime();
      }
      if (this.opts.sway && !this.touched && this.mode === "orbit") { this.sway(9 * Math.sin(this.elapsed * 0.45)); this.dirty = true; }
      else if (this.mode === "orbit") this.controls.update();
      if (this.dirty) { this.dirty = false; this.draw(); }
    }
  }
  window.Viewer4D = Viewer4D;
})();
