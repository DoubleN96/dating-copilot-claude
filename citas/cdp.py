#!/usr/bin/env python3
"""Minimal CDP CLI: one command per invocation against the first page tab (CDP_PORT, default 9250).
usage: cdp.py nav URL | eval JS | text | shot PATH [full] | type TEXT | key NAME
       | clickxy X Y | waittext TEXT [SECS] | url
"""
import asyncio, base64, json, sys, time, urllib.request
import websockets

PORT = int(__import__("os").environ.get("CDP_PORT", "9250"))


def page_ws():
    tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list"))
    tab = __import__("os").environ.get("CDP_TAB")  # navegador compartido: solo la pestaña propia
    return [t for t in tabs if t["type"] == "page" and (not tab or t["id"] == tab)][0]["webSocketDebuggerUrl"]


class CDP:
    def __init__(self, ws):
        self.ws, self.i = ws, 0

    async def call(self, method, params=None, timeout=90):
        self.i += 1
        mid = self.i
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await asyncio.wait_for(self.ws.recv(), timeout))
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    async def ev(self, js):
        r = await self.call("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in r:
            return {"exception": r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"].get("text")}
        return r["result"].get("value")

    async def wait_ready(self, secs=30):
        end = time.time() + secs
        while time.time() < end:
            try:
                if await self.ev("document.readyState") == "complete":
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False


async def main(argv):
    cmd, args = argv[0], argv[1:]
    async with websockets.connect(page_ws(), max_size=None) as ws:
        c = CDP(ws)
        if cmd == "nav":
            await c.call("Page.navigate", {"url": args[0]})
            await asyncio.sleep(1)
            print("ready" if await c.wait_ready() else "timeout", await c.ev("location.origin+location.pathname+(location.search?' [query]':'')"))
        elif cmd == "url":
            print(await c.ev("location.origin+location.pathname+(location.search?' [query]':'')"))
        elif cmd == "eval":
            print(json.dumps(await c.ev(args[0]), ensure_ascii=False, indent=1))
        elif cmd == "text":
            print(await c.ev("document.body.innerText"))
        elif cmd == "shot":
            p = {"format": "png"}
            if len(args) > 1 and args[1] == "full":
                m = await c.call("Page.getLayoutMetrics")
                cs = m["cssContentSize"]
                p.update(captureBeyondViewport=True, clip={"x": 0, "y": 0, "width": cs["width"], "height": cs["height"], "scale": 1})
            r = await c.call("Page.captureScreenshot", p)
            open(args[0], "wb").write(base64.b64decode(r["data"]))
            print("saved", args[0])
        elif cmd == "mshot":  # phone-width screenshot: mshot PATH [W H]
            w, h = (int(args[1]), int(args[2])) if len(args) > 2 else (390, 844)
            await c.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 2, "mobile": True})
            await asyncio.sleep(1.5)
            r = await c.call("Page.captureScreenshot", {"format": "png"})
            open(args[0], "wb").write(base64.b64decode(r["data"]))
            await c.call("Emulation.clearDeviceMetricsOverride")
            print("saved", args[0])
        elif cmd == "type":
            await c.call("Input.insertText", {"text": args[0]})
            print("typed")
        elif cmd == "key":
            k = {"Enter": ("Enter", 13, "\r"), "Tab": ("Tab", 9, "")}[args[0]]
            for t in ("keyDown", "keyUp"):
                p = {"type": t, "key": k[0], "code": k[0], "windowsVirtualKeyCode": k[1], "nativeVirtualKeyCode": k[1]}
                if t == "keyDown" and k[2]:
                    p["text"] = k[2]
                await c.call("Input.dispatchKeyEvent", p)
            print("key", args[0])
        elif cmd == "clickxy":
            x, y = float(args[0]), float(args[1])
            for t in ("mousePressed", "mouseReleased"):
                await c.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1})
            print("clicked", x, y)
        elif cmd == "waittext":
            secs = float(args[1]) if len(args) > 1 else 60
            end = time.time() + secs
            while time.time() < end:
                if args[0] in (await c.ev("document.body ? document.body.innerText : ''") or ""):
                    print("found")
                    return
                await asyncio.sleep(1)
            print("notfound")
        else:
            sys.exit(f"unknown cmd {cmd}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
