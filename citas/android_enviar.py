#!/usr/bin/env python3
"""Núcleo de Hinge/Bumble en el Android emulado (adb $ANDROID_SERIAL, uiautomator). Lo usan hinge.py y bumble.py:
  {hinge,bumble}.py chats            -> JSON [{nombre, ultimo, toca_contestar, extra}] de la lista de chats
  {hinge,bumble}.py chat NOMBRE      -> abre ese chat y da [{quien: ella|yo|info, texto}]
  {hinge,bumble}.py perfil NOMBRE    -> textos de su perfil (abre el chat y su perfil)
  {hinge,bumble}.py enviar NOMBRE "texto" -> abre el chat, escribe (ADBKeyboard, admite tildes/emojis),
                                       pulsa «Send message» y comprueba que salió. Respeta envio.py (PAUSA, 45 s, 40/día) y lo registra."""
import base64, html, json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import envio

ADB = ["adb", "-s", os.environ.get("ANDROID_SERIAL", "127.0.0.1:5556"), "shell"]
APPS = {  # actividad, pestaña de chats (content-desc empieza por...), filtros a recorrer (Bumble: «All» no es estable)
    "hinge": ("co.hinge.app/.ui.AppActivity", "Matches", [None]),
    "bumble": ("com.bumble.app/.ui.launcher.BumbleLauncherActivity", "Chats", ["New", "Active"]),
}
IME_ADB, IME_NORMAL = "com.android.adbkeyboard/.AdbIME", "com.android.inputmethod.latin/.LatinIME"


def sh(*a):
    return subprocess.run(ADB + list(a), capture_output=True, text=True, timeout=30).stdout


def nodos():
    sh("uiautomator", "dump", "/sdcard/ui.xml")
    out = []
    for n in re.findall(r"<node [^>]*>", sh("cat", "/sdcard/ui.xml")):
        g = lambda k: html.unescape((re.search(k + r'="([^"]*)"', n) or [0, ""])[1])
        b = re.search(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", g("bounds"))
        out.append({"t": g("text"), "d": g("content-desc"), "cls": g("class").split(".")[-1],
                    "id": g("resource-id").split("/")[-1], "b": tuple(map(int, b.groups())) if b else (0, 0, 0, 0)})
    return out


def tap(n):
    x1, y1, x2, y2 = n["b"]
    sh("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
    time.sleep(3)


def esperar_carga():
    for _ in range(8):
        ns = nodos()
        if not any((n["t"] or n["d"]).startswith("Loading") for n in ns):
            return ns
        time.sleep(2.5)
    return ns


def buscar(ns, pred):
    return next((n for n in ns if pred(n)), None)


def ir_a_lista(app, filtro=None):
    act, tab, _ = APPS[app]
    sh("am", "start", "-n", act)
    for _ in range(4):  # ponytail: salir de un chat/perfil abierto a base de «Back» de la app, máx 4
        time.sleep(4)
        ns = nodos()
        t = buscar(ns, lambda n: n["d"].startswith(tab))
        if t:
            tap(t)
            esperar_carga()
            for _ in range(5):  # lista arriba del todo
                sh("input", "swipe", "360", "450", "360", "1100", "200")
            if filtro:
                f = buscar(nodos(), lambda n: n["t"] == filtro)
                f and tap(f)
            return time.sleep(1)
        b = buscar(ns, lambda n: n["d"] == "Back")
        if b:
            tap(b)
    sys.exit(f"no encuentro la pestaña {tab} de {app} (¿pantalla de carga o popup? mira ui.sh dump)")


def chats(app):
    vistos = {}  # nombre -> fila (la última lectura completa gana)
    for filtro in APPS[app][2]:
        ir_a_lista(app, filtro)
        _pantallas(vistos)
    return list(vistos.values())


def _pantallas(vistos):
    seccion = None
    for _ in range(3):  # ponytail: 3 pantallas de lista; subir si tiene más chats
        ns = nodos()
        txt = sorted([n for n in ns if n["cls"] == "TextView" and n["t"].strip()], key=lambda n: n["b"][1])
        filas = []
        for n in txt:
            if n["b"][0] < 100 and re.match(r"(Your turn|Their turn)", n["t"]):
                seccion = n["t"]
            elif 190 <= n["b"][0] <= 235 and n["b"][1] > 300:  # columna de nombre/preview, a la derecha de la foto
                if filas and not filas[-1]["ultimo"] and n["b"][1] - filas[-1]["_y2"] < 30:
                    filas[-1]["ultimo"] = n["t"]
                elif 40 <= n["b"][3] - n["b"][1] <= 55 and not n["t"].startswith("It's a match"):  # un nombre es 1 línea
                    filas.append({"nombre": n["t"].strip(), "ultimo": None, "seccion": seccion, "_y1": n["b"][1], "_y2": n["b"][3]})
        for i, f in enumerate(filas):
            y2 = min(filas[i + 1]["_y1"] if i + 1 < len(filas) else 9999, f["_y1"] + 180, 1220) - 10
            f["extra"] = [n["t"] or n["d"] for n in ns if f["_y1"] - 10 <= n["b"][1] < y2 and 235 < n["b"][0]
                          and (n["t"] or n["d"]) and n["t"] != f["ultimo"]]
            nuevo = not f["ultimo"] or f["ultimo"].startswith("It's a match") or any("Start chat" in e for e in f["extra"])
            f["toca_contestar"] = True if nuevo or (f["seccion"] or "").startswith("Your turn") or any("Your move" in e for e in f["extra"]) \
                else (False if f["seccion"] else None)  # None = la lista no dice quién escribió: abre el chat
            muerto = re.match(r"(Chat expired|They deleted|They ended)", f["ultimo"] or "")
            if f["_y2"] < 1220 and not muerto and (f["nombre"] not in vistos or not vistos[f["nombre"]]["ultimo"]):
                vistos[f["nombre"]] = {k: v for k, v in f.items() if not k.startswith("_")}
        sh("input", "swipe", "360", "1050", "360", "450", "400")
        time.sleep(2)


def abrir(app, nombre):
    for filtro in APPS[app][2]:
        ir_a_lista(app, filtro)
        for _ in range(3):
            n = buscar(nodos(), lambda n: n["t"].strip() == nombre and n["b"][0] > 150 and n["b"][1] > 300)
            if n:
                tap(n)
                return esperar_carga()
            sh("input", "swipe", "360", "1050", "360", "450", "400")
            time.sleep(2)
    sys.exit(f"no encuentro el chat de {nombre} en {app}")


def leer():
    ns = nodos()
    caja = buscar(ns, lambda n: n["cls"] == "EditText")
    tope = caja["b"][1] if caja else 1224
    out = []
    for n in sorted(ns, key=lambda n: n["b"][1]):  # orden visual (el árbol de Bumble no va en orden)
        x1, y1, x2, y2 = n["b"]
        if n["cls"] != "TextView" or not n["t"].strip() or y1 < 200 or y2 > tope:
            continue
        # ponytail: burbuja pegada a la izquierda = ella, a la derecha = yo, resto = aviso/fecha de la app (pantalla 720 px)
        info = (x1 <= 160) == (x2 >= 640) or re.fullmatch(r"\d{1,2}:\d{2}( ?[AP]M)?|.* ago|Yesterday.*|Today.*", n["t"])
        out.append({"quien": "info" if info else ("ella" if x1 <= 160 else "yo"), "texto": n["t"]})
    return out


def perfil(app, nombre):
    abrir(app, nombre)
    ns = nodos()
    p = buscar(ns, lambda n: n["t"] == "Profile" and n["b"][1] < 250) or buscar(ns, lambda n: n["t"].strip() == nombre and n["b"][1] < 200)
    if p:
        tap(p)
    for _ in range(3):  # arriba del todo antes de leer
        sh("input", "swipe", "360", "450", "360", "1100", "300")
    textos = []
    for _ in range(6):
        for n in nodos():
            v = (n["t"] or n["d"]).strip()
            if v and v not in textos and 210 < n["b"][1] < 1200 and "photo" not in v and n["cls"] != "EditText":
                textos.append(v)
        sh("input", "swipe", "360", "1050", "360", "450", "500")
        time.sleep(2)
    return textos


def enviar(app, nombre, texto):
    texto = texto.strip()
    if not texto:
        sys.exit("texto vacio")
    envio.control()
    abrir(app, nombre)
    caja = buscar(nodos(), lambda n: n["cls"] == "EditText")
    if not caja:
        sys.exit("no veo la caja de texto del chat")
    tap(caja)
    sh("ime", "set", IME_ADB)
    try:
        sh("am", "broadcast", "-a", "ADB_CLEAR_TEXT")
        sh("am", "broadcast", "-a", "ADB_INPUT_B64", "--es", "msg", base64.b64encode(texto.encode()).decode())
        time.sleep(2)
        ns = nodos()
        caja = buscar(ns, lambda n: n["cls"] == "EditText")
        if not caja or caja["t"].strip() != texto:
            sh("am", "broadcast", "-a", "ADB_CLEAR_TEXT")
            sys.exit(f"no se escribió bien el texto (caja: {caja and caja['t']!r}); no se envía")
        boton = buscar(ns, lambda n: n["d"] == "Send message")
        if not boton:
            sh("am", "broadcast", "-a", "ADB_CLEAR_TEXT")
            sys.exit("no veo el botón Send message; no se envía")
        tap(boton)
    finally:
        sh("ime", "set", IME_NORMAL)
    envio.registrar(app, nombre, texto)  # se registra al pulsar: cuenta para límites aunque no se vea en el chat
    if not any(m["texto"].strip() == texto for m in leer()):
        sys.exit("⚠️ pulsé enviar pero no veo el mensaje en el chat: revisa con chat NOMBRE antes de reintentar")
    print(f"✅ enviado a {nombre} ({app})")


def main(app, argv):
    cmd = argv[0] if argv else "?"
    if cmd == "chats":
        r = chats(app)
    elif cmd == "chat" and len(argv) > 1:
        abrir(app, argv[1])
        r = leer()
    elif cmd == "perfil" and len(argv) > 1:
        r = perfil(app, argv[1])
    elif cmd == "enviar" and len(argv) > 2:
        return enviar(app, argv[1], " ".join(argv[2:]))
    else:
        sys.exit(__doc__)
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(__doc__)
