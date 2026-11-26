# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Render hero video segments from the web scenes (run on maxwell).

    python tools/render_hero.py preview OUT_DIR
    python tools/render_hero.py segment OUT_DIR KEY    (one segment; run several in parallel with CDP_PORT set)
"""
import asyncio, base64, json, math, os, shutil, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

import websockets

URL = os.environ.get("URL", "http://127.0.0.1:8920/tools/capture.html")
PORT = int(os.environ.get("CDP_PORT", "9350"))
W, H, FPS, SECONDS = 1920, 1080, 30, 7.0
# key: yaw start, yaw end, pitch start, pitch end, zoom start, zoom end, lift (m)
SEGMENTS = json.loads(os.environ.get("SEGMENTS", "null")) or {
    "cat": [-14, 12, 0, 6, 1.0, 0.86, 0.0],
    "droid": [-12, 14, 0, 4, 1.0, 0.86, 0.0],
    "kitchen": [-12, 12, 0, 4, 0.92, 0.8, 0.0],
    "tennis": [-16, 12, 0, 4, 1.0, 0.86, 0.0],
    "arms": [-12, 12, 0, 4, 1.0, 0.86, 0.0],
    "hand": [-12, 12, 0, 4, 1.0, 0.86, 0.0],
}


def ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * u)


async def session(work, w, h):
    profile = tempfile.mkdtemp(prefix="hero-chrome-")
    chrome = subprocess.Popen(["google-chrome", "--headless=new", "--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                               f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", f"--window-size={w},{h}", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")); break
            except Exception:
                time.sleep(0.25)
        ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url, max_size=2 ** 31) as ws:
            n = 0

            async def call(method, **params):
                nonlocal n
                n += 1
                await ws.send(json.dumps({"id": n, "method": method, "params": params}))
                while True:
                    m = json.loads(await ws.recv())
                    if m.get("id") == n:
                        return m

            async def ev(expr):
                r = await call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True, timeout=120000)
                if "exceptionDetails" in r.get("result", {}):
                    raise RuntimeError(json.dumps(r["result"]["exceptionDetails"])[:500])
                return r["result"]["result"].get("value")
            await call("Page.enable")
            await call("Page.navigate", url=URL)
            await asyncio.sleep(4)
            await work(ev)
    finally:
        chrome.kill()
        chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)


def save(url, path):
    Path(path).write_bytes(base64.b64decode(url.split(",", 1)[1]))


def preview(out):
    async def work(ev):
        for key in SEGMENTS:
            F = await ev(f"capture.load('{key}', 960, 540)")
            for t, name in ((F // 2, "a"), (F - 1, "b")):
                save(await ev(f"capture.frame({t}, 0, 0, 1)"), f"{out}/{key}_{name}.jpg")
            print(key, F, flush=True)
    asyncio.run(session(work, 1000, 600))


def segment(out, key):
    y0, y1, p0, p1, z0, z1, lift = SEGMENTS[key]
    total = int(SECONDS * FPS)

    async def work(ev):
        F = await ev(f"capture.load('{key}', {W}, {H})")
        t0 = time.time()
        for i in range(total):
            u = i / (total - 1)
            # tracks grow over 90% of the shot, then hold on the finished trajectories
            t = (F - 1) * min(1.0, u / 0.9)
            e = ease(u)
            args = (t, y0 + (y1 - y0) * e, p0 + (p1 - p0) * e, z0 + (z1 - z0) * e, lift)
            save(await ev(f"capture.frame({args[0]:.4f}, {args[1]:.4f}, {args[2]:.4f}, {args[3]:.4f}, {args[4]})"), f"{out}/{key}/{i:04d}.jpg")
            if i % 30 == 0:
                print(key, i, f"{(time.time() - t0) / (i + 1):.2f} s/frame", flush=True)
    Path(f"{out}/{key}").mkdir(parents=True, exist_ok=True)
    asyncio.run(session(work, W + 40, H + 40))


if __name__ == "__main__":
    mode, out = sys.argv[1], sys.argv[2]
    Path(out).mkdir(parents=True, exist_ok=True)
    preview(out) if mode == "preview" else segment(out, sys.argv[3])
