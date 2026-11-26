# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Headless screenshots of the local site (run on maxwell): python tools/shot.py OUT_DIR [W H] [selector ...]
Prints console errors and failed requests, which is the point of this check."""
import asyncio, base64, json, os, subprocess, sys, time, urllib.request
from pathlib import Path
import websockets

URL = os.environ.get("URL", "http://127.0.0.1:8920/index.html")
PORT = int(os.environ.get("CDP_PORT", "9341"))


async def main(out, w, h, sels):
    Path(out).mkdir(parents=True, exist_ok=True)
    chrome = subprocess.Popen(["google-chrome", "--headless=new", "--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                               "--hide-scrollbars", "--autoplay-policy=no-user-gesture-required", f"--user-data-dir={out}/profile",
                               f"--remote-debugging-port={PORT}", f"--window-size={w},{h}", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")); break
            except Exception:
                time.sleep(0.2)
        ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url, max_size=2 ** 31) as ws:
            n, waiters = 0, {}

            async def pump():
                async for raw in ws:
                    m = json.loads(raw)
                    if "id" in m:
                        waiters.pop(m["id"]).set_result(m)
                    elif m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] in ("error", "warning"):
                        print("console:", " ".join(str(a.get("value", a.get("description", ""))) for a in m["params"]["args"])[:300])
                    elif m.get("method") == "Runtime.exceptionThrown":
                        d = m["params"]["exceptionDetails"]
                        print("exception:", (d.get("exception", {}).get("description") or d.get("text"))[:400])
                    elif m.get("method") == "Network.responseReceived" and m["params"]["response"]["status"] >= 400:
                        print("http", m["params"]["response"]["status"], m["params"]["response"]["url"])
                    elif m.get("method") == "Network.loadingFailed" and not m["params"].get("canceled"):
                        print("failed:", m["params"].get("errorText"), m["params"].get("requestId"))
            asyncio.ensure_future(pump())

            async def call(method, **params):
                nonlocal n
                n += 1
                fut = asyncio.get_event_loop().create_future()
                waiters[n] = fut
                await ws.send(json.dumps({"id": n, "method": method, "params": params}))
                return await fut

            async def shot(name):
                r = await call("Page.captureScreenshot", format="jpeg", quality=82)
                Path(f"{out}/{name}.jpg").write_bytes(base64.b64decode(r["result"]["data"]))

            for d in ("Page", "Runtime", "Network"):
                await call(f"{d}.enable")
            await call("Page.navigate", url=URL)
            await asyncio.sleep(4)
            await shot("00_top")
            for i, sel in enumerate(sels, 1):
                await call("Runtime.evaluate", expression=f"document.documentElement.style.scrollBehavior='auto';document.querySelector({json.dumps(sel)}).scrollIntoView({{block:'start'}})")
                await asyncio.sleep(9 if sel in ("#explore", "#stage") else 2.5)
                await shot(f"{i:02d}_{sel.strip('#.')}")
            info = await call("Runtime.evaluate", expression="JSON.stringify({w:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,h:document.documentElement.scrollHeight})", returnByValue=True)
            print("doc:", info["result"]["result"].get("value"))
    finally:
        chrome.kill()


a = sys.argv[1:]
w, h = (int(a[1]), int(a[2])) if len(a) > 2 else (1440, 900)
asyncio.run(main(a[0], w, h, a[3:] or ["#overview", "#explore", "#method", ".subsec-h", "#flywheel", "#benchmarks", "#comparison"]))
