# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Click through every control on the local site and report what breaks (run on maxwell).
    python tools/check_page.py
Exits non-zero on any page error, failed request or missing image."""
import asyncio, json, os, subprocess, sys, tempfile, shutil, time, urllib.request
import websockets

URL = os.environ.get("URL", "http://127.0.0.1:8920/index.html")
PORT = int(os.environ.get("CDP_PORT", "9343"))
BAD = []

TEST = r"""
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (id) => document.getElementById(id);
  const out = {};
  document.documentElement.style.scrollBehavior = "auto";
  $("explore").scrollIntoView(); await sleep(2500);
  out.scenes = [];
  for (const b of [...$("sceneTabs").children, $("sceneTabs").children[0]]) {
    b.click();
    for (let i = 0; i < 100 && !(window.__v0 = $("stageLoading").hidden === false); i++) await sleep(10);
    for (let i = 0; i < 400 && !$("stageLoading").hidden; i++) await sleep(25);
    await sleep(400);
    out.scenes.push([b.textContent, $("scrub").max, $("stageTime").textContent, $("sceneNote").textContent.slice(0, 44)]);
  }
  const t0 = $("stageTime").textContent; await sleep(1200); out.playing = [t0, $("stageTime").textContent];
  $("play").click(); await sleep(150); const a = $("stageTime").textContent; await sleep(700); out.paused = a === $("stageTime").textContent;
  out.playIcon = $("play").getAttribute("aria-label");
  const sc = $("scrub"); sc.value = 20; sc.dispatchEvent(new Event("input")); await sleep(120); out.scrub = $("stageTime").textContent;
  $("viewInput").click(); await sleep(300); $("viewFree").click(); await sleep(300);
  out.pressed = [$("viewFree").getAttribute("aria-pressed"), $("viewInput").getAttribute("aria-pressed")];
  $("layerTracks").click(); await sleep(80); out.tracksOff = $("layerTracks").getAttribute("aria-pressed");
  $("layerTracks").click(); $("layerCam").click(); await sleep(80); $("layerCam").click();
  const wheel = new WheelEvent("wheel", { deltaY: 100, bubbles: true, cancelable: true });
  $("viewerCanvas").dispatchEvent(wheel); out.wheelScrollsPage = !wheel.defaultPrevented;

  document.querySelector("#benchmarks").scrollIntoView(); await sleep(300);
  out.chart = [];
  const groups = () => [...document.querySelectorAll("#filters .filter")];
  const task = (i) => groups()[0].querySelectorAll("button")[i];
  for (let v = 0; v < 3; v++) {
    task(v).click(); await sleep(40);
    const label = (s) => groups().find((g) => g.querySelector(".filter-label").textContent === s);
    const nSets = label("Dataset").querySelectorAll("button").length;
    for (let d = 0; d < nSets; d++) for (let m = 0; m < 3; m++) {
      label("Dataset").querySelectorAll("button")[d].click(); await sleep(5);
      label("Metric").querySelectorAll("button")[m].click(); await sleep(5);
      const rows = [...document.querySelectorAll(".bar-row")];
      out.chart.push([$("chartTitle").textContent, rows.length, rows[0].querySelector(".bar-name").textContent, $("chartDir").textContent.split(" ")[0]]);
    }
  }
  task(0).click(); await sleep(30);
  groups()[1].querySelectorAll("button")[1].click(); await sleep(30);
  out.aligned = $("chartTitle").textContent;
  const r = document.querySelector(".bar-row"); r.dispatchEvent(new PointerEvent("pointerenter", { clientX: 300, clientY: 300 }));
  out.tip = $("tooltip").textContent; r.dispatchEvent(new PointerEvent("pointerleave"));
  groups()[1].querySelectorAll("button")[0].click(); await sleep(30);
  $("tableToggle").click(); await sleep(50);
  out.table = [document.querySelectorAll("#chartTable tr").length, document.querySelectorAll("#chartTable th").length, $("bars").hidden];
  $("tableToggle").click(); await sleep(50);

  document.querySelector("#comparison").scrollIntoView(); await sleep(300);
  out.images = 0; out.broken = [];
  const clips = [...$("clipTabs").children], pills = [...$("methodPills").querySelectorAll("button")];
  for (const c of clips) for (const p of pills) {
    c.click(); p.click();
    for (const id of ["cmpOurs", "cmpBase", "cmpInput"]) {
      const im = $(id);
      for (let i = 0; i < 300 && !(im.complete && im.naturalWidth); i++) await sleep(10);
      if (!im.naturalWidth) out.broken.push(im.src); else out.images++;
    }
  }
  const rg = $("cmpRange"); rg.value = 25; rg.dispatchEvent(new Event("input")); await sleep(30);
  out.slider = getComputedStyle($("cmp")).getPropertyValue("--x").trim();

  $("wheel").scrollIntoView(); await sleep(300);
  document.querySelectorAll(".wheel-node")[2].dispatchEvent(new MouseEvent("click", { bubbles: true })); await sleep(50);
  out.wheel = $("wheelTitle").textContent + " / " + $("wheelLabeler").textContent;
  const hero = $("heroVideo"); out.hero = [hero.readyState, Math.round(hero.duration * 10) / 10, hero.videoWidth];
  out.doc = [document.documentElement.scrollWidth, document.documentElement.clientWidth];
  return JSON.stringify(out);
})()
"""


async def main():
    profile = tempfile.mkdtemp(prefix="check-chrome-")
    chrome = subprocess.Popen(["google-chrome", "--headless=new", "--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                               "--autoplay-policy=no-user-gesture-required", f"--user-data-dir={profile}",
                               f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
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
                    elif m.get("method") == "Runtime.exceptionThrown":
                        d = m["params"]["exceptionDetails"]
                        BAD.append("exception: " + (d.get("exception", {}).get("description") or d.get("text"))[:300])
                    elif m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] == "error":
                        BAD.append("console: " + str(m["params"]["args"])[:300])
                    elif m.get("method") == "Network.responseReceived" and m["params"]["response"]["status"] >= 400:
                        BAD.append(f"http {m['params']['response']['status']} {m['params']['response']['url']}")
            asyncio.ensure_future(pump())

            async def call(method, **params):
                nonlocal n
                n += 1
                fut = asyncio.get_event_loop().create_future()
                waiters[n] = fut
                await ws.send(json.dumps({"id": n, "method": method, "params": params}))
                return await fut
            for d in ("Page", "Runtime", "Network"):
                await call(f"{d}.enable")
            await call("Page.navigate", url=URL)
            await asyncio.sleep(4)
            r = await call("Runtime.evaluate", expression=TEST, awaitPromise=True, returnByValue=True, timeout=200000)
            if "exceptionDetails" in r["result"]:
                BAD.append(json.dumps(r["result"]["exceptionDetails"])[:600])
            else:
                o = json.loads(r["result"]["result"]["value"])
                chart = o.pop("chart")
                print(json.dumps(o, indent=0, ensure_ascii=False))
                print("chart views:", len(chart), "first-ranked non-Ours:", sum(1 for c in chart if not c[2].startswith("Ours")))
                for c in chart:
                    if not c[2].startswith("Ours"):
                        print("  ", c)
                if o["broken"]:
                    BAD.append(f"{len(o['broken'])} broken images")
    finally:
        chrome.kill()
        chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
    print("PROBLEMS:", BAD or "none")
    return 1 if BAD else 0


sys.exit(asyncio.run(main()))
