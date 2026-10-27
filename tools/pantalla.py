#!/usr/bin/env python3
"""Pantalla remota del Android del copiloto (adb $ANDROID_SERIAL) en el navegador.
Escucha solo en 127.0.0.1:8977; se publica con un túnel de cloudflared. pantalla.env (junto a este fichero) = una línea usuario:clave."""
import base64, os, subprocess, http.server, json
ADB = ["adb", "-s", os.environ.get("ANDROID_SERIAL", "127.0.0.1:5556")]
U, P = open(os.path.join(os.path.dirname(__file__), "pantalla.env")).read().split()[0].split(":", 1)
PAGE = b"""<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>Android copiloto</title>
<style>body{margin:0;background:#111;color:#eee;font:14px sans-serif;text-align:center}img{max-width:100%;max-height:85vh;touch-action:none}button{margin:4px;padding:8px 14px}</style>
<div><button onclick="k('BACK')">Atras</button><button onclick="k('HOME')">Inicio</button><button onclick="t()">Escribir</button></div>
<img id=s src=/shot.png>
<script>
let d=null,s=document.getElementById('s');
function xy(e){const r=s.getBoundingClientRect();return[Math.round((e.clientX-r.left)*s.naturalWidth/r.width),Math.round((e.clientY-r.top)*s.naturalHeight/r.height)]}
s.onpointerdown=e=>{d=xy(e);e.preventDefault()};
s.onpointerup=e=>{const u=xy(e);fetch('/in',{method:'POST',body:JSON.stringify({a:d,b:u})});d=null;setTimeout(r,400)};
function k(c){fetch('/in',{method:'POST',body:JSON.stringify({k:c})});setTimeout(r,400)}
function t(){const v=prompt('Texto');if(v)fetch('/in',{method:'POST',body:JSON.stringify({t:v})})}
function r(){s.src='/shot.png?'+Date.now()} setInterval(r,1500);
</script>"""
class H(http.server.BaseHTTPRequestHandler):
    def auth(self):
        ok = self.headers.get("Authorization") == "Basic " + base64.b64encode(f"{U}:{P}".encode()).decode()
        if not ok:
            self.send_response(401); self.send_header("WWW-Authenticate", 'Basic realm="copiloto"'); self.end_headers()
        return ok
    def do_GET(self):
        if not self.auth(): return
        if self.path.startswith("/shot.png"):
            img = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=10).stdout
            self.send_response(200); self.send_header("Content-Type", "image/png"); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(img)
        else:
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(PAGE)
    def do_POST(self):
        if not self.auth(): return
        j = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if "k" in j and j["k"] in ("BACK", "HOME"):
            cmd = ["input", "keyevent", j["k"]]
        elif "t" in j:
            cmd = ["input", "text", str(j["t"]).replace(" ", "%s")]
        else:
            (x1, y1), (x2, y2) = [map(int, p) for p in (j["a"], j["b"])]
            cmd = ["input", "tap", str(x2), str(y2)] if abs(x1 - x2) + abs(y1 - y2) < 20 else ["input", "swipe", str(x1), str(y1), str(x2), str(y2), "300"]
        subprocess.run(ADB + ["shell"] + cmd, timeout=10)
        self.send_response(204); self.end_headers()
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(("127.0.0.1", 8977), H).serve_forever()
