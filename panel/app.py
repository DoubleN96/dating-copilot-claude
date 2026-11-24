#!/usr/bin/env python3
"""Panel de CelestIA (fase 1): entrar con Google, conectar Calendar y WhatsApp (QR), y bandeja donde la IA propone o contesta.
Todo se filtra por uid en el servidor. Secretos solo por variables de entorno. `python3 app.py` sirve en :8990."""
import base64, hashlib, hmac, html, http.cookies, json, os, random, re, sqlite3, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo
from cryptography.fernet import Fernet
import ia

# config.env junto a app.py (KEY=valor, sin comillas obligatorias); las variables de entorno reales mandan
_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.env")
for _l in (open(_CFG, encoding="utf-8").read().splitlines() if os.path.exists(_CFG) else ()):
    _k, _s, _v = _l.strip().partition("=")
    if _s and not _k.startswith("#"):
        _v = _v.strip()
        os.environ.setdefault(_k.strip(), _v[1:-1] if len(_v) > 1 and _v[0] == _v[-1] and _v[0] in "\"'" else _v)
ENV = os.environ.get
BASE = ENV("BASE_URL", "http://localhost:8990").rstrip("/")
DB = ENV("DB_PATH", "/data/celestia.db")
EVO, EVOKEY = ENV("EVO_URL", "http://evolution-celestia:8080"), ENV("EVO_KEY", "")
SKEY = ENV("SESSION_KEY", "dev-only-key").encode()
TZ = ZoneInfo("Europe/Madrid")
TOPE, PAUSA_MIN = int(ENV("TOPE_DIARIO", "40")), 45  # por usuario
D = os.path.dirname(os.path.abspath(__file__))
INST_RE = re.compile(r"^celestia-[0-9a-f]{12}$")
APPS = ("tinder", "hinge", "bumble")  # chats que llegan por el puente: solo lectura + sugerencias
BRIDGE_SECRET, BRIDGE_EMAIL = ENV("BRIDGE_SECRET", ""), ENV("BRIDGE_EMAIL", "")
es_wa = lambda jid: "@" in jid  # los de apps de citas van como "tinder:<id>": nunca se envían por WhatsApp
es_ig = lambda jid: jid.startswith("ig:")  # DMs de Instagram por la API oficial (inicio de sesión unificado): envío dentro de la ventana de 24 h de Meta
META_ID, META_SECRET, IG_CONFIG, IG_VERIFY = ENV("META_APP_ID", ""), ENV("META_APP_SECRET", ""), ENV("IG_CONFIG_ID", ""), ENV("IG_VERIFY_TOKEN", "")
IGV = "https://graph.facebook.com/v23.0"
es_nube = lambda jid: jid.startswith("n-")  # chats del Android en la nube PROPIO del usuario: envío manual desde el panel
NUBE, NUBE_SECRET = ENV("NUBE_URL", "http://127.0.0.1:8995"), ENV("NUBE_SECRET", "")
OPERADOR = ENV("OPERADOR", "quien despliega esta instancia (configura OPERADOR con tu razón social y NIF)")
TINDER = ENV("TINDER_URL", "http://127.0.0.1:8996")  # agente opcional del servidor: Tinder web en un Chrome propio por usuario (mismo secreto)
CIUDADES = {"Madrid": (40.4203, -3.7058), "Barcelona": (41.3874, 2.1686), "Valencia": (39.4699, -0.3763), "Sevilla": (37.3891, -5.9845),
            "Málaga": (36.7213, -4.4214), "Bilbao": (43.2630, -2.9350)}
MANIFEST = {"name": "CelestIA", "short_name": "CelestIA", "description": "Tu copiloto de citas: del match a la cita.", "lang": "es",
            "start_url": "/", "scope": "/", "display": "standalone", "background_color": "#FFF7F4", "theme_color": "#14101F",
            "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                      {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}
e = lambda s: html.escape(str(s if s is not None else ""))
fernet = lambda: Fernet(ENV("FERNET_KEY").encode())

ESQUEMA = """
CREATE TABLE IF NOT EXISTS users(uid TEXT PRIMARY KEY, email TEXT, nombre TEXT, cal_rt BLOB, inst TEXT UNIQUE, hook TEXT,
  modo_auto INT DEFAULT 0, pausa INT DEFAULT 0, perfil TEXT DEFAULT '', consent_at TEXT, creado TEXT, tel TEXT);
CREATE TABLE IF NOT EXISTS chats(uid TEXT, jid TEXT, nombre TEXT, activo INT DEFAULT 0, auto INT DEFAULT 0, ultimo TEXT,
  etapa TEXT DEFAULT 'conversando', cita TEXT, PRIMARY KEY(uid, jid));
CREATE TABLE IF NOT EXISTS sugerencias(id INTEGER PRIMARY KEY, uid TEXT, jid TEXT, msg_id TEXT, entrada TEXT CHECK(length(entrada)<=500),
  texto TEXT, escalar INT, motivo TEXT, estado TEXT DEFAULT 'pendiente', creado TEXT, UNIQUE(uid, msg_id));
CREATE TABLE IF NOT EXISTS envios(uid TEXT, jid TEXT, texto TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS personas(id INTEGER PRIMARY KEY, uid TEXT NOT NULL, nombre TEXT, edad INT, foto TEXT,
  etapa TEXT NOT NULL DEFAULT 'match' CHECK(etapa IN ('match','conversando','plan','contacto','cita_fijada','cita_hecha','resultado')),
  resultado TEXT CHECK(resultado IN ('repetir','relacion','sin_quimica','descartada')),
  etapa_fuente TEXT NOT NULL DEFAULT 'ia' CHECK(etapa_fuente IN ('ia','usuario')),
  temperatura INT NOT NULL DEFAULT 2 CHECK(temperatura BETWEEN 1 AND 3), proxima TEXT, notas TEXT CHECK(length(notas)<=2000),
  archivada INT NOT NULL DEFAULT 0, ultimo_at TEXT, creada_at TEXT);
CREATE INDEX IF NOT EXISTS ix_personas ON personas(uid, archivada, etapa);
CREATE TABLE IF NOT EXISTS eventos(id INTEGER PRIMARY KEY, uid TEXT, persona_id INT, tipo TEXT, de TEXT, a TEXT, detalle TEXT, origen TEXT, at TEXT);
CREATE INDEX IF NOT EXISTS ix_eventos ON eventos(persona_id, at);
CREATE TABLE IF NOT EXISTS citas(id INTEGER PRIMARY KEY, uid TEXT, persona_id INT, inicio TEXT, lugar TEXT, texto TEXT,
  estado TEXT DEFAULT 'fijada' CHECK(estado IN ('propuesta','fijada','hecha','cancelada')));
CREATE TABLE IF NOT EXISTS stripe_eventos(id TEXT PRIMARY KEY, tipo TEXT, at TEXT);
"""
ORDEN = ("match", "conversando", "plan", "contacto", "cita_fijada", "cita_hecha", "resultado")
IA_ETAPA = {"conversando": "conversando", "propuesta": "plan", "cita": "cita_fijada"}  # etapas viejas / de la IA -> nuevas
RESULTADOS = ("repetir", "relacion", "sin_quimica", "descartada")


def db():
    c = sqlite3.connect(DB, timeout=10); c.row_factory = sqlite3.Row
    return c


def q(sql, *a):
    with db() as c:
        return c.execute(sql, a).fetchall()


def user(uid):
    r = q("SELECT * FROM users WHERE uid=?", uid)
    return r[0] if r else None


# ---------- CRM: personas, etapas, citas ----------
ahora = lambda: datetime.now(TZ).isoformat(timespec="seconds")


def evento(uid, pid, tipo, de, a, origen, detalle=""):
    with db() as c:
        return c.execute("INSERT INTO eventos(uid,persona_id,tipo,de,a,detalle,origen,at) VALUES(?,?,?,?,?,?,?,?)",
                         (uid, pid, tipo, de, a, detalle[:300], origen, ahora())).lastrowid


def persona_de(uid, jid, etapa="conversando"):
    """id de la persona de ese chat; si el chat aún no tiene, la crea (una por chat; unir es manual)."""
    ch = q("SELECT persona_id, nombre, ultimo FROM chats WHERE uid=? AND jid=?", uid, jid)
    if not ch:
        return None
    if ch[0]["persona_id"]:
        return ch[0]["persona_id"]
    nombre = (ch[0]["nombre"] or "?").split(" · ")[0]
    with db() as c:
        pid = c.execute("INSERT INTO personas(uid,nombre,etapa,ultimo_at,creada_at) VALUES(?,?,?,?,?)",
                        (uid, nombre, etapa, ahora(), ahora())).lastrowid
        c.execute("UPDATE chats SET persona_id=?, desde=? WHERE uid=? AND jid=?", (pid, ahora(), uid, jid))
    evento(uid, pid, "etapa", None, etapa, "ia", "Nueva historia")
    return pid


def avanzar(uid, pid, etapa, origen, detalle=""):
    """ÚNICA escritura de etapa. La IA solo avanza, nunca pisa lo que fijó el usuario y nunca da una cita por hecha.
    Devuelve el id del evento (para deshacer) o None si no cambió nada."""
    p = q("SELECT etapa, etapa_fuente FROM personas WHERE id=? AND uid=?", pid, uid)
    if not p or etapa not in ORDEN or etapa == p[0]["etapa"]:
        return None
    de = p[0]["etapa"]
    if origen == "ia" and (p[0]["etapa_fuente"] == "usuario" or ORDEN.index(etapa) <= ORDEN.index(de) or etapa in ("cita_hecha", "resultado")):
        return None
    if origen == "calendar" and not (de == "cita_fijada" and etapa == "cita_hecha"):
        return None
    fuente = "usuario" if origen == "usuario" else p[0]["etapa_fuente"]
    q("UPDATE personas SET etapa=?, etapa_fuente=?, resultado=CASE WHEN ?='resultado' THEN resultado ELSE NULL END WHERE id=? AND uid=?",
      etapa, fuente, etapa, pid, uid)
    return evento(uid, pid, "etapa", de, etapa, origen, detalle)


def poner_resultado(uid, pid, r):
    """El resultado de una cita lo pone siempre el usuario."""
    p = q("SELECT etapa, resultado FROM personas WHERE id=? AND uid=?", pid, uid)
    if not p or r not in RESULTADOS:
        return None
    q("UPDATE personas SET etapa='resultado', resultado=?, etapa_fuente='usuario', archivada=?, "
      "proxima=CASE WHEN ?='repetir' THEN 'Proponer segunda cita' ELSE proxima END WHERE id=? AND uid=?",
      r, int(r == "descartada"), r, pid, uid)
    if r == "relacion":  # fuera del modo automático
        q("UPDATE chats SET auto=0 WHERE uid=? AND persona_id=?", uid, pid)
    return evento(uid, pid, "resultado", p[0]["resultado"] or p[0]["etapa"], r, "usuario")


def deshacer(uid, ev):
    """Revierte un cambio de etapa o resultado hecho por el usuario."""
    x = q("SELECT * FROM eventos WHERE id=? AND uid=? AND origen='usuario' AND tipo IN ('etapa','resultado')", ev, uid)
    if not x:
        return
    x = x[0]
    if x["tipo"] == "resultado" and x["de"] in RESULTADOS:
        q("UPDATE personas SET resultado=?, archivada=0 WHERE id=? AND uid=?", x["de"], x["persona_id"], uid)
    else:
        etapa = x["de"] if x["de"] in ORDEN else "conversando"
        q("UPDATE personas SET etapa=?, resultado=NULL, archivada=0 WHERE id=? AND uid=?", etapa, x["persona_id"], uid)
    q("DELETE FROM eventos WHERE id=?", ev)


def leer_cita(txt, hoy=None):
    """«vie 28/11 21:00 · Lugar» (formato antiguo) -> (iso, lugar); año inferido. (None, txt) si no se entiende."""
    m = re.search(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})", txt or "")
    if not m:
        return None, txt
    hoy = hoy or datetime.now(TZ)
    d = datetime(hoy.year, int(m[2]), int(m[1]), int(m[3]), int(m[4]), tzinfo=TZ)
    if d < hoy - timedelta(days=180):
        d = d.replace(year=hoy.year + 1)
    return d.isoformat(timespec="minutes"), (txt.split("·", 1)[1].strip() if "·" in txt else "")


def anotar_cita(uid, pid, inicio, lugar, texto):
    if pid and not q("SELECT 1 FROM citas WHERE uid=? AND persona_id=? AND estado='fijada'", uid, pid):
        q("INSERT INTO citas(uid,persona_id,inicio,lugar,texto) VALUES(?,?,?,?,?)", uid, pid, inicio, lugar, texto)


def barrido(t=None):
    """Citas fijadas que ya pasaron (+2 h) -> hecha; la persona pasa a «cita hecha» y aparece el resultado en Hoy."""
    lim = ((t or datetime.now(TZ)) - timedelta(hours=2)).isoformat(timespec="minutes")
    for c in q("SELECT * FROM citas WHERE estado='fijada' AND inicio IS NOT NULL AND inicio<?", lim):
        q("UPDATE citas SET estado='hecha' WHERE id=?", c["id"])
        avanzar(c["uid"], c["persona_id"], "cita_hecha", "calendar", c["texto"] or "")


def migrar():
    """Idempotente: cada chat sin persona recibe la suya con la etapa traducida; las citas en texto pasan a la tabla citas."""
    for ch in q("SELECT * FROM chats WHERE persona_id IS NULL AND (activo=1 OR jid NOT LIKE '%@%')"):
        etapa = IA_ETAPA.get(ch["etapa"] or "conversando", "conversando")
        if ch["cita"] and es_wa(ch["jid"]) and etapa == "conversando":
            etapa = "contacto"
        pid = persona_de(ch["uid"], ch["jid"], etapa)
        if ch["cita"]:
            ini, lugar = leer_cita(ch["cita"])
            anotar_cita(ch["uid"], pid, ini, lugar, ch["cita"])


def unir(uid, a, b):
    """Une la historia b dentro de a (misma persona en otra app). El detalle guarda los canales movidos."""
    pa = q("SELECT * FROM personas WHERE id=? AND uid=?", a, uid); pb = q("SELECT * FROM personas WHERE id=? AND uid=?", b, uid)
    if not pa or not pb or a == b:
        return False
    pa, pb = pa[0], pb[0]
    movidos = [r["jid"] for r in q("SELECT jid FROM chats WHERE uid=? AND persona_id=?", uid, b)]
    etapa = max(pa["etapa"], pb["etapa"], "contacto", key=ORDEN.index)
    notas = "\n".join(x for x in (pa["notas"], pb["notas"]) if x)[:2000] or None
    with db() as c:
        c.execute("UPDATE chats SET persona_id=? WHERE uid=? AND persona_id=?", (a, uid, b))
        c.execute("UPDATE eventos SET persona_id=? WHERE uid=? AND persona_id=?", (a, uid, b))
        c.execute("UPDATE citas SET persona_id=? WHERE uid=? AND persona_id=?", (a, uid, b))
        c.execute("UPDATE personas SET etapa=?, notas=?, temperatura=max(temperatura,?) WHERE id=?", (etapa, notas, pb["temperatura"], a))
        c.execute("DELETE FROM personas WHERE id=? AND uid=?", (b, uid))
    evento(uid, a, "union", pb["nombre"], etapa, "usuario", f"Con la historia de {pb['nombre']} ({len(movidos)} canal(es))")
    return True


# ---------- sesión firmada ----------
def firmar(d):
    return d + "." + hmac.new(SKEY, d.encode(), "sha256").hexdigest()


def leer(v):
    d, _, f = (v or "").rpartition(".")
    return d if d and hmac.compare_digest(f, hmac.new(SKEY, d.encode(), "sha256").hexdigest()) else None


def inst_de(uid):
    i = "celestia-" + hashlib.sha256(uid.encode()).hexdigest()[:12]
    assert INST_RE.match(i)
    return i


# ---------- Evolution (solo instancias celestia-*) ----------
def evo(path, inst=None, body=None, metodo=None, qs=""):
    if inst is not None and not INST_RE.match(inst):
        raise ValueError("instancia no permitida")
    url = f"{EVO}/{path}" + (f"/{inst}" if inst else "") + (f"?{qs}" if qs else "")
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=metodo or ("POST" if body is not None else "GET"),
                               headers={"apikey": EVOKEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=30))


def nube(path, uid, body=None, base=None):
    """Agente opcional del servidor que crea y maneja el Android en la nube del usuario (base=TINDER: su Chrome de Tinder). Devuelve (status, bytes)."""
    r = urllib.request.Request((base or NUBE) + path, data=json.dumps(body).encode() if body is not None else None,
                               headers={"X-Nube-Secret": NUBE_SECRET, "X-Uid": uid, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as x:
            return x.status, x.read()
    except urllib.error.HTTPError as x:
        return x.code, x.read()


def wa_estado(uid):
    """Solo connectionState (no rota QR ni código); al quedar abierto engancha el webhook."""
    u = user(uid); inst = u["inst"]
    try:
        st = evo("instance/connectionState", inst)["instance"]["state"]
    except Exception:
        return None
    if st == "open":
        evo("webhook/set", inst, {"webhook": {"enabled": True, "url": f"{BASE}/hook/{uid}/{u['hook']}", "byEvents": False,
                                              "base64": False, "events": ["MESSAGES_UPSERT"]}})
    return st


def wa_qr(uid):
    inst = user(uid)["inst"]
    st = wa_estado(uid)
    if st is None:
        evo("instance/create", body={"instanceName": inst, "integration": "WHATSAPP-BAILEYS", "qrcode": True})
        st = "close"
    if st == "open":
        return {"estado": "open"}
    return {"estado": st, "qr": evo("instance/connect", inst).get("base64", "")}


def tel_ok(t):
    """Número de WhatsApp: solo dígitos con prefijo de país; 9 cifras que empiezan por 6/7 = España."""
    d = re.sub(r"[\s+\-().]", "", t or "")
    if not d.isdigit():
        return None
    if len(d) == 9 and d[0] in "67":
        d = "34" + d
    return d if 10 <= len(d) <= 15 else None


def wa_codigo(uid, tel):
    """Código de 8 caracteres para «Vincular con el número de teléfono». Evolution solo lo da en una instancia
    recién creada sin QR, así que si no está abierta se rehace (nunca se toca una instancia abierta)."""
    inst = user(uid)["inst"]
    st = wa_estado(uid)
    if st == "open":
        return {"estado": "open"}
    if st is not None:
        evo("instance/delete", inst, metodo="DELETE")
    for i in range(8):  # Evolution tarda un poco en liberar el nombre tras borrar
        try:
            evo("instance/create", body={"instanceName": inst, "integration": "WHATSAPP-BAILEYS", "qrcode": False})
            break
        except urllib.error.HTTPError:
            if i == 7:
                raise
            time.sleep(1)
    c = evo("instance/connect", inst, qs="number=" + tel).get("pairingCode")
    return {"estado": "connecting", "codigo": c} if c else {"estado": "error"}


def mensajes(inst, jid, n=20):
    r = evo("chat/findMessages", inst, {"where": {"key": {"remoteJid": jid}}, "limit": n})
    ms = r.get("messages", r)
    ms = ms.get("records", []) if isinstance(ms, dict) else ms
    out = []
    for m in sorted(ms, key=lambda m: m.get("messageTimestamp", 0)):
        t = texto(m)
        if t:
            out.append(("yo" if m["key"].get("fromMe") else "otro", t))
    return out


def texto(m):
    msg = m.get("message") or {}
    if "audioMessage" in msg:
        return "[nota de voz]"
    if "imageMessage" in msg:
        return "[foto] " + (msg["imageMessage"].get("caption") or "")
    return msg.get("conversation") or (msg.get("extendedTextMessage") or {}).get("text") or ""


# ---------- envío con salvaguardas ----------
def control(uid):
    """None si se puede enviar ahora; si no, el motivo."""
    u = user(uid)
    if not u or u["pausa"]:
        return "pausa"
    hoy = datetime.now(TZ).replace(hour=0, minute=0, second=0).timestamp()
    if q("SELECT count(*) n FROM envios WHERE uid=? AND ts>=?", uid, hoy)[0]["n"] >= TOPE:
        return "tope diario"
    ult = q("SELECT max(ts) t FROM envios WHERE uid=?", uid)[0]["t"]
    if ult and time.time() - ult < PAUSA_MIN:
        return "ritmo"
    return None


def enviar(uid, jid, txt):
    if not (es_wa(jid) or es_nube(jid) or es_ig(jid)) or jid.startswith("n-tinder:"):  # Tinder web: solo lectura
        return "solo lectura"  # apps leídas por el puente: el panel solo propone
    motivo = control(uid)
    if motivo:
        return motivo
    if es_nube(jid):  # "n-hinge:<nombre>" -> la app de su Android en la nube, solo a mano desde el panel
        app_, nombre = jid[2:].split(":", 1)
        st, b = nube("/enviar", uid, {"app": app_, "nombre": nombre, "texto": txt})
        if st != 200:
            return "la app no lo aceptó"
    elif es_ig(jid):
        try:
            ig_api(f'{user(uid)["ig_id"]}/messages', ig_tok(user(uid)), {"recipient": {"id": jid[3:]}, "message": {"text": txt}})
        except (urllib.error.URLError, ValueError):
            return "Instagram no lo aceptó: solo se puede contestar en las 24 h siguientes a su último mensaje"
    else:
        evo("message/sendText", user(uid)["inst"], {"number": jid, "text": txt})
    with db() as c:
        c.execute("INSERT INTO envios VALUES(?,?,?,?)", (uid, jid, txt, time.time()))
    return None


# ---------- Google ----------
def google_url(estado, scope, extra=None):
    p = {"client_id": ENV("GOOGLE_CLIENT_ID"), "redirect_uri": BASE + "/auth/callback", "response_type": "code",
         "scope": scope, "state": firmar(f"{estado}|{int(time.time())}"), "prompt": "select_account", **(extra or {})}
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(p)


def google_token(data):
    d = urllib.parse.urlencode({"client_id": ENV("GOOGLE_CLIENT_ID"), "client_secret": ENV("GOOGLE_CLIENT_SECRET"), **data}).encode()
    return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", d, timeout=20))


def id_claims(tok):
    """El id_token llega directo de Google por TLS (flujo de servidor), así que basta con validar iss/aud/exp/email."""
    p = tok.split(".")[1]
    c = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    ok = c.get("iss") in ("accounts.google.com", "https://accounts.google.com") and c.get("aud") == ENV("GOOGLE_CLIENT_ID") \
        and c.get("exp", 0) > time.time() and c.get("email_verified")
    return c if ok else None


def cal_token(u):
    return google_token({"refresh_token": fernet().decrypt(u["cal_rt"]).decode(), "grant_type": "refresh_token"})["access_token"]


def crear_cita(uid, nombre, cita):
    """Evento de 2 h «Cita con NOMBRE» en su calendario principal; devuelve el texto que se ve en «Mis citas»."""
    ini = cita["inicio"].replace(tzinfo=TZ)
    ev = {"summary": f"Cita con {nombre} (CelestIA)", "location": cita["lugar"], "colorId": "4",
          "start": {"dateTime": ini.isoformat()}, "end": {"dateTime": (ini + timedelta(hours=2)).isoformat()},
          "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 120}]}}
    r = urllib.request.Request("https://www.googleapis.com/calendar/v3/calendars/primary/events", data=json.dumps(ev).encode(),
                               headers={"Authorization": "Bearer " + cal_token(user(uid)), "Content-Type": "application/json"})
    urllib.request.urlopen(r, timeout=20).read()
    return ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"][ini.weekday()] + ini.strftime(" %d/%m %H:%M") + (f" · {cita['lugar']}" if cita["lugar"] else "")


def libres(uid, dias=7):
    """Huecos de 2 h entre las 19 y las 23 h según su free/busy (solo ocupado/libre; los títulos nunca salen)."""
    u = user(uid)
    if not u or not u["cal_rt"]:
        return []
    at = cal_token(u)
    ahora = datetime.now(TZ)
    franjas = [(datetime(d.year, d.month, d.day, 19, tzinfo=TZ), datetime(d.year, d.month, d.day, 23, tzinfo=TZ))
               for d in (ahora + timedelta(days=i) for i in range(dias))]
    franjas = [(max(a, ahora), b) for a, b in franjas if b > ahora]
    body = {"timeMin": franjas[0][0].isoformat(), "timeMax": franjas[-1][1].isoformat(), "items": [{"id": "primary"}]}
    r = urllib.request.Request("https://www.googleapis.com/calendar/v3/freeBusy", data=json.dumps(body).encode(),
                               headers={"Authorization": "Bearer " + at, "Content-Type": "application/json"})
    busy = [(datetime.fromisoformat(b["start"].replace("Z", "+00:00")), datetime.fromisoformat(b["end"].replace("Z", "+00:00")))
            for b in json.load(urllib.request.urlopen(r, timeout=20))["calendars"]["primary"]["busy"]]
    return [["lun", "mar", "mié", "jue", "vie", "sáb", "dom"][a.weekday()] + a.strftime(" %d/%m %H:%M") for a, b in franjas
            if (b - a) >= timedelta(hours=2) and not any(x < b and y > a for x, y in busy)]


# ---------- webhook ----------
def procesar(uid, data):
    u = user(uid)
    for m in data if isinstance(data, list) else [data]:
        k = m.get("key") or {}
        jid = k.get("remoteJid", "")
        if k.get("fromMe") or not jid.endswith(("@s.whatsapp.net", "@lid")):
            continue
        with db() as c:
            c.execute("INSERT INTO chats(uid,jid,nombre,ultimo) VALUES(?,?,?,?) ON CONFLICT(uid,jid) DO UPDATE SET ultimo=excluded.ultimo,"
                      " nombre=coalesce(chats.nombre, excluded.nombre)", (uid, jid, m.get("pushName") or jid.split("@")[0], texto(m)[:200]))
        def hist(jid=jid):
            try:
                return mensajes(u["inst"], jid)
            except Exception:  # sin historial (instancia caída): al menos el mensaje que llega
                return []
        sugerir(uid, jid, k.get("id"), texto(m), hist)


def sugerir(uid, jid, msg_id, entrada, hist):
    """Común a WhatsApp e Instagram: sugerencia de la IA, etapa, cita en Calendar y envío si el chat está en automático."""
    u, ch = user(uid), q("SELECT * FROM chats WHERE uid=? AND jid=?", uid, jid)[0]
    if not de_pago(u) or not ch["activo"] or q("SELECT 1 FROM sugerencias WHERE uid=? AND msg_id=?", uid, msg_id):
        return
    try:
        hs = libres(uid)
    except Exception:
        hs = []
    r = ia.proponer(hist() or [("otro", entrada)], u["perfil"], hs)
    with db() as c:
        c.execute("INSERT OR IGNORE INTO sugerencias(uid,jid,msg_id,entrada,texto,escalar,motivo,estado,creado) VALUES(?,?,?,?,?,?,?,?,?)",
                  (uid, jid, msg_id, entrada[:500], r["respuesta"], int(r["escalar"]), r["motivo"],
                   "escalada" if r["escalar"] else "pendiente", datetime.now(TZ).isoformat()))
    etapa, cita, pid = r["etapa"], ch["cita"], persona_de(uid, jid)
    if r["cita"] and not cita and u["cal_rt"]:
        try:
            cita = crear_cita(uid, ch["nombre"], r["cita"])
            anotar_cita(uid, pid, r["cita"]["inicio"].replace(tzinfo=TZ).isoformat(timespec="minutes"), r["cita"]["lugar"], cita)
        except Exception:
            etapa = "propuesta"  # sin evento no la damos por cerrada
    q("UPDATE chats SET etapa=?, cita=? WHERE uid=? AND jid=?", "cita" if cita else etapa, cita, uid, jid)  # columnas viejas: vuelta atrás
    avanzar(uid, pid, "cita_fijada" if cita else IA_ETAPA.get(etapa, "conversando"), "ia")
    if u["modo_auto"] and ch["auto"] and not r["escalar"]:
        time.sleep(random.randint(45, 180))  # ritmo humano
        if not enviar(uid, jid, r["respuesta"]):
            q("UPDATE sugerencias SET estado='enviada' WHERE uid=? AND msg_id=?", uid, msg_id)


# ---------- Instagram (API con inicio de sesión unificado: cuenta profesional, sin página de Facebook) ----------
def ig_api(path, tok, body=None, **qs):
    r = urllib.request.Request(f"{IGV}/{path}?" + urllib.parse.urlencode({**qs, "access_token": tok}),
                               data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=20))


ig_tok = lambda u: fernet().decrypt(u["ig_tok"]).decode()


def ig_url(uid):
    return "https://www.facebook.com/v23.0/dialog/oauth?" + urllib.parse.urlencode({
        "client_id": META_ID, "config_id": IG_CONFIG, "redirect_uri": BASE + "/ig/callback", "response_type": "code", "prompt": "login",
        "state": firmar(f"ig|{uid}|{int(time.time())}")})


def ig_conectar(uid, code):
    tok = json.load(urllib.request.urlopen(f"{IGV}/oauth/access_token?" + urllib.parse.urlencode(
        {"client_id": META_ID, "client_secret": META_SECRET, "redirect_uri": BASE + "/ig/callback", "code": code}), timeout=20))["access_token"]
    ig = ig_api("me/assigned_instagram_accounts", tok, fields="id,username")["data"][0]  # ponytail: la primera cuenta compartida
    q("UPDATE users SET ig_id=?, ig_user=?, ig_tok=? WHERE uid=?", str(ig["id"]), ig.get("username"), fernet().encrypt(tok.encode()), uid)
    ig_api(f'{ig["id"]}/subscribed_apps', tok, {}, subscribed_fields="messages")  # que Meta mande sus DMs a /ig/hook
    return ig.get("username")


def ig_firma_ok(raw, sig):  # Meta firma cada aviso con el secreto de la app
    return bool(META_SECRET) and hmac.compare_digest(sig or "", "sha256=" + hmac.new(META_SECRET.encode(), raw, "sha256").hexdigest())


def ig_procesar(data):
    for en in data.get("entry") or []:
        us = q("SELECT * FROM users WHERE ig_id=?", str(en.get("id")))
        if not us:
            continue
        u = us[0]
        evs = (en.get("messaging") or []) + [c.get("value") or {} for c in en.get("changes") or [] if c.get("field") == "messages"]
        for ev in evs:  # «messaging» en los avisos reales; «changes» en los de prueba del panel de Meta
            msg, sid = ev.get("message") or {}, str((ev.get("sender") or {}).get("id", ""))
            if msg.get("is_echo") or not msg.get("mid") or not sid.isdigit() or sid == u["ig_id"]:
                continue
            txt = msg.get("text") or ("[foto o vídeo]" if msg.get("attachments") else "")
            jid, tok = "ig:" + sid, ig_tok(u)
            try:
                nombre = "@" + ig_api(sid, tok, fields="username")["username"]
            except (urllib.error.URLError, KeyError, ValueError):
                nombre = "Instagram"
            with db() as c:
                c.execute("INSERT INTO chats(uid,jid,nombre,ultimo) VALUES(?,?,?,?) ON CONFLICT(uid,jid) DO UPDATE SET ultimo=excluded.ultimo,"
                          " nombre=excluded.nombre", (u["uid"], jid, nombre, txt[:200]))
            def hist(sid=sid, tok=tok, yo=u["ig_id"]):
                try:
                    cv = ig_api(f"{yo}/conversations", tok, platform="instagram", user_id=sid, fields="messages{message,from}")["data"][0]
                    return [("yo" if x["from"]["id"] == yo else "otro", x["message"]) for x in reversed(cv["messages"]["data"]) if x.get("message")]
                except (urllib.error.URLError, KeyError, IndexError, ValueError):
                    return []
            sugerir(u["uid"], jid, msg["mid"], txt, hist)


# ---------- puente de apps de citas (lector -> panel) ----------
def puente(data):
    """data = {"chats": [{app, id, nombre, ultimo, toca, hist: [[yo|otro, texto], ...]}]}. Devuelve cuántas sugerencias nuevas."""
    propio = bool(data.get("uid"))  # con uid: chats del Android en la nube de ese usuario (prefijo n-, envío manual)
    us = q("SELECT uid FROM users WHERE uid=?", str(data["uid"])) if propio else (q("SELECT uid FROM users WHERE email=?", BRIDGE_EMAIL) if BRIDGE_EMAIL else [])
    if not us:
        return -1
    uid, u, nuevas = us[0]["uid"], user(us[0]["uid"]), 0
    if not de_pago(u):
        return 0
    for c in (data.get("chats") or [])[:300]:
        app_, cid = str(c.get("app")), re.sub(r"[^\w.-]", "", str(c.get("id")))[:64]
        if app_ not in APPS or not cid:
            continue
        jid, nombre = ("n-" if propio else "") + f"{app_}:{cid}", f'{str(c.get("nombre") or "?")[:60]} · {app_.capitalize()}'
        with db() as d:
            d.execute("INSERT INTO chats(uid,jid,nombre,activo,ultimo) VALUES(?,?,?,1,?) ON CONFLICT(uid,jid) DO UPDATE SET "
                      "nombre=excluded.nombre, ultimo=excluded.ultimo", (uid, jid, nombre, str(c.get("ultimo") or "")[:200]))
        persona_de(uid, jid)
        hist = [("yo" if de == "yo" else "otro", str(t)[:500]) for de, t in (c.get("hist") or [])[-20:] if t]
        if not (c.get("toca") and hist and hist[-1][0] == "otro"):
            continue
        mid = jid + ":" + hashlib.sha1(hist[-1][1].encode()).hexdigest()[:12]
        if q("SELECT 1 FROM sugerencias WHERE uid=? AND msg_id=?", uid, mid):
            continue
        try:
            hs = libres(uid) if u["cal_rt"] else []
        except Exception:
            hs = []
        r = ia.proponer(hist, u["perfil"], hs)
        with db() as d:
            d.execute("INSERT OR IGNORE INTO sugerencias(uid,jid,msg_id,entrada,texto,escalar,motivo,estado,creado) VALUES(?,?,?,?,?,?,?,?,?)",
                      (uid, jid, mid, hist[-1][1][:500], r["respuesta"], int(r["escalar"]), r["motivo"],
                       "escalada" if r["escalar"] else "pendiente", datetime.now(TZ).isoformat()))
        q("UPDATE chats SET etapa=? WHERE uid=? AND jid=?", r["etapa"], uid, jid)
        avanzar(uid, persona_de(uid, jid), IA_ETAPA.get(r["etapa"], "conversando"), "ia")
        nuevas += 1
    return nuevas


# ---------- pago (Stripe): plan «CelestIA Nube» 29 €/mes + IVA, 3 días gratis ----------
STRIPE_KEY, STRIPE_WHSEC, STRIPE_PRICE, STRIPE_PORTAL = (ENV(k, "") for k in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE", "STRIPE_PORTAL_CONFIG"))
ESTADO_STRIPE = {"trialing": "prueba", "active": "activo", "past_due": "impago", "unpaid": "impago", "incomplete": "impago", "paused": "impago",
                 "canceled": "cancelado", "incomplete_expired": "cancelado"}
VIVAS = ("trialing", "active", "past_due")  # se gestionan en el portal; unpaid/paused/incomplete se cancelan y se empieza limpio
PERMITIDOS = {x.strip().lower() for x in ENV("ALLOWED_EMAILS", "").split(",") if x.strip()}  # autoalojado: solo estas cuentas de Google
permitido = lambda email: not PERMITIDOS or (email or "").lower() in PERMITIDOS
de_pago = lambda u: bool(u) and (not STRIPE_KEY or u["plan"] == "fundador" or u["estado"] in ("prueba", "activo"))  # sin Stripe (autoalojado) todo abierto


def stripe(path, datos=None, metodo=None):
    r = urllib.request.Request("https://api.stripe.com/v1/" + path, method=metodo, headers={"Authorization": "Bearer " + STRIPE_KEY},
                               data=urllib.parse.urlencode(datos).encode() if datos is not None else None)
    return json.load(urllib.request.urlopen(r, timeout=30))


def cliente_stripe(u):
    """Un solo cliente de Stripe de CelestIA por email, reutilizado también tras borrar la cuenta: la prueba gratis es una vez por persona."""
    if not u["stripe_cus"]:
        cs = [c for c in stripe("customers?" + urllib.parse.urlencode({"email": u["email"], "limit": 100}))["data"]
              if (c.get("metadata") or {}).get("app") == "celestia"]
        cus = cs[0]["id"] if cs else stripe("customers", {"email": u["email"], "name": u["nombre"] or "", "metadata[app]": "celestia"})["id"]
        q("UPDATE users SET stripe_cus=? WHERE uid=? AND stripe_cus IS NULL", cus, u["uid"])
    return user(u["uid"])["stripe_cus"]


def checkout(uid, cupon=None):
    """URL de Stripe Checkout, o del portal si ya tiene una suscripción viva: nunca dos. Prueba de 3 días solo si nunca tuvo suscripción.
    `cupon` (100 %) solo sirve para verificar el flujo sin cobrar: ninguna ruta lo expone."""
    u = user(uid)
    if u["plan"] == "fundador":
        return BASE + "/"
    cus = cliente_stripe(u)
    subs = [s for s in stripe(f"subscriptions?customer={cus}&status=all&limit=100")["data"] if (s.get("metadata") or {}).get("app") == "celestia"]
    if any(s["status"] in VIVAS for s in subs):
        return portal(uid)
    for s in subs:  # atascada sin cobro posible (unpaid/paused/incomplete): se cancela y se contrata de nuevo, sin prueba
        if s["status"] not in ("canceled", "incomplete_expired"):
            stripe(f"subscriptions/{s['id']}", metodo="DELETE")
    for c in stripe(f"checkout/sessions?customer={cus}&status=open&limit=100")["data"]:  # una sola caja abierta: dos pestañas no dan dos altas
        stripe(f"checkout/sessions/{c['id']}/expire", {})
    # ponytail: dos clics en el mismo milisegundo aún podrían abrir dos cajas; un candado por usuario si llegara a pasar
    d = {"mode": "subscription", "line_items[0][price]": STRIPE_PRICE, "line_items[0][quantity]": 1, "client_reference_id": uid,
         "metadata[uid]": uid, "metadata[app]": "celestia", "subscription_data[metadata][uid]": uid, "subscription_data[metadata][app]": "celestia",
         "automatic_tax[enabled]": "true", "locale": "es", "success_url": BASE + "/?ok=pago", "cancel_url": BASE + "/"}
    d.update({"customer": cus, "customer_update[address]": "auto", "customer_update[name]": "auto"})
    if not subs:
        d["subscription_data[trial_period_days]"] = 3
    d.update({"discounts[0][coupon]": cupon, "payment_method_collection": "if_required"} if cupon else {"allow_promotion_codes": "true"})
    return stripe("checkout/sessions", d)["url"]


def portal(uid):
    d = {"customer": user(uid)["stripe_cus"] or "", "return_url": BASE + "/"}
    return stripe("billing_portal/sessions", {**d, **({"configuration": STRIPE_PORTAL} if STRIPE_PORTAL else {})})["url"]


def stripe_firma_ok(raw, cab, t_=None):
    """Cabecera Stripe-Signature: t=<ts>,v1=<hmac>[,v1=…]; 5 min de tolerancia contra repeticiones."""
    kv = [x.split("=", 1) for x in (cab or "").split(",") if "=" in x]
    t = next((v for k, v in kv if k == "t"), "")
    if not STRIPE_WHSEC or not t.isdigit() or abs((t_ or time.time()) - int(t)) > 300:
        return False
    esp = hmac.new(STRIPE_WHSEC.encode(), t.encode() + b"." + raw, "sha256").hexdigest()
    return any(k == "v1" and hmac.compare_digest(esp, v) for k, v in kv)


def stripe_evento(ev):
    """Evento firmado -> users.estado (prueba/activo/impago/cancelado). Idempotente por id; un evento más viejo que el
    último aplicado no pisa el estado. Solo toca usuarios de CelestIA (la cuenta de Stripe es compartida)."""
    if q("SELECT 1 FROM stripe_eventos WHERE id=?", ev["id"]):
        return "repetido"
    o, t, uid, est, cus, sub = ev["data"]["object"], ev["type"], None, None, None, None
    if t == "checkout.session.completed" and (o.get("metadata") or {}).get("app") == "celestia" and o.get("subscription"):
        uid, cus, sub = o.get("client_reference_id"), o.get("customer"), o["subscription"]
        est = ESTADO_STRIPE.get(stripe(f"subscriptions/{sub}")["status"])
    elif t.startswith("customer.subscription.") and (o.get("metadata") or {}).get("app") == "celestia":
        uid, cus, sub = o["metadata"].get("uid"), o.get("customer"), o["id"]
        est = "cancelado" if t.endswith(".deleted") else ESTADO_STRIPE.get(o.get("status"))
        u = user(uid or "")
        if u and u["stripe_sub"] and u["stripe_sub"] != sub:  # aviso de una suscripción anterior: no pisa la actual
            est = None
    elif t == "invoice.payment_failed":  # solo la suscripción actual (API nueva: parent.subscription_details)
        sub = o.get("subscription") or ((o.get("parent") or {}).get("subscription_details") or {}).get("subscription")
        us = q("SELECT uid FROM users WHERE stripe_sub=?", sub or "-")
        uid, est = (us[0]["uid"], "impago") if us else (None, None)
    if uid and est:
        q("UPDATE users SET estado=?, stripe_cus=coalesce(?,stripe_cus), stripe_sub=coalesce(?,stripe_sub), estado_ts=? "
          "WHERE uid=? AND coalesce(estado_ts,0)<=?", est, cus, sub, ev["created"], uid, ev["created"])
        u = user(uid)
        if u and (u["estado"] == "cancelado" or (u["estado"] == "impago" and t.startswith("customer.subscription.") and o.get("status") in ("unpaid", "paused"))):
            liberar_nube(uid)  # sin plan no se le paga el Android ni el Chrome de Tinder (sus historias siguen en el panel)
    q("INSERT OR IGNORE INTO stripe_eventos(id,tipo,at) VALUES(?,?,?)", ev["id"], t, ahora())  # al final: si algo falla, Stripe reintenta
    return est or "ignorado"


# ---------- páginas («Historias»: Hoy · Historias · Agenda · Ajustes · ficha) ----------
from ui import (avatar, pill, ruta, nombre_vis, form, hidden, hoja_fase, tarjeta_resultado, tarjeta_respuesta, tarjeta_escalada,
                pagina, cabecera, FASES, RES, TEMP, DIAS)

AVISOS = {"fase": "Fase cambiada", "res": "Resultado anotado", "temp": "Temperatura cambiada", "nota": "Notas guardadas", "prox": "Próxima acción guardada",
          "arch": "Historia archivada", "reab": "Historia reabierta", "ia": "La IA vuelve a decidir la fase", "unir": "Historias unidas",
          "env": "Enviado", "luego": "Te lo recuerdo en 4 horas", "otra": "Nueva sugerencia", "desh": "Deshecho", "cop": "Copiado: pégalo en la app", "ig": "Instagram conectado"}


def fecha_larga():
    d = datetime.now(TZ)
    return f'{["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][d.weekday()]} {d.day} ' \
           f'{["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"][d.month - 1]}'


def pag(cuerpo, uid=None):
    """Páginas sueltas (legal, errores, alta, Android): misma marca, sin pestañas si no hay sesión."""
    return pagina(cabecera("CelestIA") + "</header>" + f'<div class="pad" style="padding-top:16px">{cuerpo}</div>', "ajustes" if uid else None)


def pag_entrar():
    return pagina('<header class="hero" style="padding-bottom:40px"><div class="top"><span class="marca"><img src="/logo.png" alt="">CelestIA</span></div>'
                  '<h1>De tu perfil<br>a tu cita.</h1><p>CelestIA lee tus chats, te propone qué contestar y, si quieres, contesta por ti '
                  'hasta cerrar la cita en tu calendario. Discreto: solo tú ves tus historias.</p></header>'
                  '<div class="pad" style="padding-top:24px"><a class="btn" style="width:100%" href="/auth/google">Entrar con Google</a>'
                  '<p class="mute" style="font-size:13px;text-align:center">Al entrar aceptas los <a href="/terminos">términos</a> y la '
                  '<a href="/privacidad">privacidad</a>.</p></div>')


def pag_consent(uid):
    return pag('<section><h2>Antes de empezar</h2><ul><li>CelestIA leerá los chats de WhatsApp que TÚ actives, para proponerte respuestas.</li>'
               '<li>La conexión de WhatsApp no es oficial de Meta: hay riesgo de que limiten tu número si se abusa. Vamos con ritmo humano y un tope diario.</li>'
               '<li>No guardamos tus mensajes: se leen al momento. Puedes borrar tu cuenta cuando quieras.</li>'
               '<li>Si te preguntan si eres una IA, CelestIA no contesta: te avisa a ti.</li></ul>'
               + form("/consent", "Entendido, empezar", "btn", '<p><label>Tu número de WhatsApp<br><input class="campo" name="tel" type="tel" '
                      'inputmode="tel" autocomplete="tel" required placeholder="+34 600 000 000" style="max-width:320px"></label></p>') + '</section>')


def volver_ok(v):
    return v if isinstance(v, str) and v.startswith("/") and not v.startswith("//") else "/"


def jids_de(uid, pid):
    return [r["jid"] for r in q("SELECT jid FROM chats WHERE uid=? AND persona_id=?", uid, pid)]


def personas(uid, where="1", *args):
    return q(f"SELECT p.*, (SELECT texto FROM citas c WHERE c.uid=p.uid AND c.persona_id=p.id ORDER BY c.id DESC LIMIT 1) cita_txt, "
             "(SELECT inicio FROM citas c WHERE c.uid=p.uid AND c.persona_id=p.id ORDER BY c.id DESC LIMIT 1) cita_ini, "
             f"(SELECT group_concat(jid,'|') FROM chats h WHERE h.uid=p.uid AND h.persona_id=p.id) jids FROM personas p WHERE p.uid=? AND {where} "
             "ORDER BY p.temperatura DESC, p.ultimo_at DESC", uid, *args)


SUG = ("SELECT s.*, coalesce(p.id,0) pid, coalesce(p.nombre, c.nombre, '?') pnombre, coalesce(p.etapa,'conversando') etapa, p.resultado, "
       "coalesce(p.temperatura,2) temperatura FROM sugerencias s LEFT JOIN chats c ON c.uid=s.uid AND c.jid=s.jid "
       "LEFT JOIN personas p ON p.id=c.persona_id WHERE s.uid=? AND s.estado=? AND (s.luego IS NULL OR s.luego<?) ")


def semana(uid):
    hoy = datetime.now(TZ).date()
    citas = {}
    for c in q("SELECT c.inicio, p.nombre FROM citas c JOIN personas p ON p.id=c.persona_id WHERE c.uid=? AND c.estado IN ('fijada','hecha') "
               "AND c.inicio>=?", uid, hoy.isoformat()):
        citas.setdefault(c["inicio"][:10], c["nombre"])
    out = []
    for i in range(7):
        d = hoy + timedelta(days=i)
        n = citas.get(d.isoformat())
        out.append(f'<a class="dia{" hoy" if i == 0 else ""}" href="/agenda#d{d.isoformat()}"><small>{DIAS[d.weekday()].capitalize()}</small>'
                   f'<b>{d.day}</b><span>{e(n) if n else "libre"}</span></a>')
    return '<nav class="semana" aria-label="Tu semana">' + "".join(out) + "</nav>"


def n_hoy(uid):
    t = ahora()
    return (len(q("SELECT 1 FROM personas WHERE uid=? AND etapa='cita_hecha' AND archivada=0", uid))
            + q("SELECT count(*) n FROM sugerencias WHERE uid=? AND estado IN ('pendiente','escalada') AND (luego IS NULL OR luego<?)", uid, t)[0]["n"])


def pag_hoy(uid, aviso=None, undo=None):
    u = user(uid)
    if not u["consent_at"]:
        return pag_consent(uid)
    t = ahora()
    res = personas(uid, "p.etapa='cita_hecha' AND p.archivada=0")
    sug = q(SUG + "ORDER BY coalesce(p.temperatura,2) DESC, s.id DESC LIMIT 30", uid, "pendiente", t)
    esc = q(SUG + "ORDER BY s.id DESC LIMIT 10", uid, "escalada", t)
    n = len(sug)
    hoy_cita = q("SELECT p.nombre, c.inicio FROM citas c JOIN personas p ON p.id=c.persona_id WHERE c.uid=? AND c.estado='fijada' AND c.inicio LIKE ?",
                 uid, datetime.now(TZ).date().isoformat() + "%")
    tit = (f"{n} respuesta{'s' if n != 1 else ''}<br>espera{'n' if n != 1 else ''} tu toque." if n else "Todo al día.")
    sub = (f'Y una cita hoy con <b>{e(hoy_cita[0]["nombre"])}</b>, a las {e(hoy_cita[0]["inicio"][11:16])}.' if hoy_cita else
           ("Tienes citas por anotar." if res else "Cuando te escriban, aquí tendrás la respuesta lista."))
    pausa = ('<div class="card oro" style="margin-top:16px"><b>CelestIA en pausa.</b> ' + form("/pausa", "Reanudar", "btn sec", hidden(v="/")) + '</div>'
             if u["pausa"] else "")
    cola = "".join(tarjeta_resultado(p, "/") for p in res) + "".join(tarjeta_respuesta(s, "/") for s in sug) + "".join(tarjeta_escalada(s, "/") for s in esc)
    if not cola:
        hay = q("SELECT 1 FROM chats WHERE uid=? LIMIT 1", uid)
        cola = ('<div class="vacio"><b>Todo al día</b>Las respuestas llegan solas cuando te escriben.<div class="acc" style="justify-content:center">'
                '<a class="btn sec" href="/historias">Ver historias</a></div></div>' if hay else
                '<div class="vacio"><b>Empecemos</b>Conecta tu WhatsApp o tus apps de citas y CelestIA hará el resto.'
                '<div class="acc" style="justify-content:center"><a class="btn" href="/ajustes">Conectar</a></div></div>')
    return pagina(cabecera(tit, sub, fecha_larga()) + semana(uid) + "</header>" + f'<div class="pad">{pausa}<div class="eti">Toca responder<span>por urgencia</span></div>{cola}</div>',
                  "hoy", n_hoy(uid), AVISOS.get(aviso), undo)


GRUPOS = {"activas": ("Activas", "p.archivada=0 AND (p.etapa<>'resultado' OR p.resultado IN ('repetir','relacion'))"),
          "cita": ("Con cita", "p.archivada=0 AND p.etapa IN ('cita_fijada','cita_hecha')"),
          "nuevas": ("Nuevas", "p.archivada=0 AND p.etapa IN ('match','conversando')"),
          "resultado": ("Resultado", "p.etapa='resultado'"), "archivo": ("Archivo", "p.archivada=1")}


def fila(p):
    jids = (p["jids"] or "").split("|")
    q_ = f'{p["nombre"]} {ruta(jids)} {p["notas"] or ""}'.lower()
    sub = p["proxima"] or (p["cita_txt"] if p["etapa"] in ("cita_fijada", "cita_hecha") else "") or ruta(jids)
    return (f'<div class="fila" data-q="{e(q_)}"><a href="/p/{p["id"]}" class="quien" style="flex:1;min-width:0">{avatar(p["nombre"], p["id"], p["temperatura"])}'
            f'<div class="txt"><h3>{e(nombre_vis(p["nombre"]))}</h3><p>{e(sub)}</p></div></a>{pill(p["etapa"], p["resultado"], p["id"])}</div>'
            + hoja_fase(p["id"], p["etapa"], "/historias"))


def pag_historias(uid, f="activas", txt="", aviso=None, undo=None):
    f = f if f in GRUPOS else "activas"
    todas = personas(uid, "p.archivada=0")
    k = lambda *xs: sum(1 for p in todas if p["etapa"] in xs)
    emb = [(k("match", "conversando", "plan", "contacto"), "#8B3DFF", "En conversación"), (k("cita_fijada", "cita_hecha"), "#E6C67A", "Citas"),
           (sum(1 for p in todas if p["resultado"] in ("repetir", "relacion")), "#FF5A6E", "Repetir o relación"),
           (sum(1 for p in todas if p["resultado"] == "sin_quimica"), "#9a93ab", "Cerradas")]
    tot = sum(x for x, _, _ in emb) or 1
    barra = "".join(f'<i style="width:{100 * x / tot:.1f}%;background:{c}" title="{t}: {x}"></i>' for x, c, t in emb)
    leyenda = " · ".join(f"{t} {x}" for x, _, t in emb)
    chips = "".join(f'<a href="/historias?f={k_}"{" aria-current=page" if k_ == f else ""}>{t}</a>' for k_, (t, _) in GRUPOS.items())
    ps = [p for p in personas(uid, GRUPOS[f][1]) if not txt or txt.lower() in f'{p["nombre"]} {p["notas"] or ""}'.lower()]
    grupos = ""
    for et in reversed(ORDEN):
        g = [p for p in ps if p["etapa"] == et]
        if g:
            grupos += f'<div class="eti">{FASES[et][0]}<span>{len(g)}</span></div><div class="card" style="padding:4px 16px">' + "".join(fila(p) for p in g) + "</div>"
    if not grupos:
        grupos = ('<div class="vacio"><b>Aún no hay historias</b>Llegan solas cuando hablas en WhatsApp o en tus apps.</div>' if not todas else
                  '<div class="vacio"><b>Nada con este filtro</b></div>')
    return pagina(cabecera("Tus historias", f"{len(todas)} activas · del match al resultado.", fecha_larga())
                  + f'<div class="embudo" role="img" aria-label="{e(leyenda)}">{barra}</div><p style="font-size:12px">{e(leyenda)}</p></header>'
                  f'<div class="pad"><form class="buscar" role="search" action="/historias"><input type="hidden" name="f" value="{f}">'
                  f'<input name="q" value="{e(txt)}" placeholder="Buscar por nombre, app o nota" aria-label="Buscar" oninput="filtrar(this.value)"></form>'
                  f'<div class="chips" style="margin-top:12px">{chips}</div>{grupos}</div>', "historias", n_hoy(uid), AVISOS.get(aviso), undo)


ACCION = {"match": ("plan", "Avanzar a plan propuesto"), "conversando": ("plan", "Avanzar a plan propuesto"), "plan": ("contacto", "Pasar a contacto"),
          "contacto": ("cita_fijada", "Fijar cita"), "cita_fijada": ("cita_hecha", "Marcar cita hecha")}
EVTXT = {"etapa": "Fase", "resultado": "Resultado", "union": "Historias unidas", "nota": "Nota", "envio": "Mensaje enviado"}


def pag_persona(uid, pid, aviso=None, undo=None):
    ps = personas(uid, "p.id=?", pid)
    if not ps:
        return None
    p = ps[0]
    jids = (p["jids"] or "").split("|") if p["jids"] else []
    i = ORDEN.index(p["etapa"])
    barra = "".join(f'<i class="{"on" if j <= i else ""}"></i>' for j in range(len(ORDEN)))
    fuente = "fijada por ti" if p["etapa_fuente"] == "usuario" else "sugerida por la IA"
    v = f"/p/{pid}"
    if p["etapa"] == "cita_hecha":
        prin = tarjeta_resultado(p, v)
    elif p["etapa"] == "resultado" and p["resultado"] == "repetir":
        prin = form(f"/p/{pid}/etapa", "Proponer segunda cita", "btn ink", hidden(e="plan", v=v))
    elif p["etapa"] in ACCION:
        a, t = ACCION[p["etapa"]]
        prin = form(f"/p/{pid}/etapa", t, "btn ink", hidden(e=a, v=v))
    else:
        prin = ""
    sug = q(SUG + "AND c.persona_id=? ORDER BY s.id DESC LIMIT 1", uid, "pendiente", ahora(), pid)
    temp = "".join(form(f"/p/{pid}/temp", TEMP[k], "", hidden(t=k, v=v), f' role="radio" aria-checked="{"true" if p["temperatura"] == k else "false"}"')
                   for k in (1, 2, 3))
    canales = "".join(f'<div class="fila"><div class="txt"><h3>{e(ruta([j]))}</h3><p>{e(nombre_vis(j.split("@")[0].split(":")[-1]))}</p></div></div>' for j in jids) \
        or '<p class="mute">Sin canales.</p>'
    otras = personas(uid, "p.id<>? AND p.archivada=0", pid)
    unir = ('<form method="post" action="/unir" class="acc">' + hidden(a=pid, v=v) +
            '<select class="campo" name="b" aria-label="Otra historia de la misma persona" style="flex:1">'
            + "".join(f'<option value="{o["id"]}">{e(nombre_vis(o["nombre"]))} · {e(ruta((o["jids"] or "").split("|")))}</option>' for o in otras)
            + '</select><button class="btn sec">Unir</button></form>') if otras else ""
    evs = q("SELECT * FROM eventos WHERE uid=? AND persona_id=? ORDER BY id DESC LIMIT 40", uid, pid)
    tl = "".join(f'<li data-n="{len(evs) - k}"><b>{e(EVTXT.get(x["tipo"], x["tipo"]))}: '
                 f'{e(FASES.get(x["a"], (RES.get(x["a"], x["a"]),))[0])}</b><small>{e(x["at"][:16].replace("T", " "))} · '
                 f'{"tú" if x["origen"] == "usuario" else "calendario" if x["origen"] == "calendar" else "IA"}{" · " + e(x["detalle"]) if x["detalle"] else ""}</small></li>'
                 for k, x in enumerate(evs))
    arch = form(f"/p/{pid}/archivar", "Reabrir" if p["archivada"] else "Archivar", "btn sec", hidden(v=v))
    libera = form(f"/p/{pid}/ia", "Que la IA decida", "btn sec", hidden(v=v)) if p["etapa_fuente"] == "usuario" else ""
    return pagina(
        cabecera("", "", "", "/historias", f'<button class="pill" style="background:rgba(255,255,255,.12)" onclick="hoja(\'fase{pid}\')">Cambiar fase</button>')
        + f'<div class="quien" style="margin-top:18px">{avatar(p["nombre"], pid, p["temperatura"], True)}<div><h1 style="margin:0">{e(nombre_vis(p["nombre"]))}</h1>'
        f'<p>{e(ruta(jids))}</p><p style="margin-top:6px">{pill(p["etapa"], p["resultado"])} <small>{fuente}</small></p></div></div>'
        f'<div class="barra" aria-label="Fase {i + 1} de {len(ORDEN)}">{barra}</div></header>{hoja_fase(pid, p["etapa"], v)}'
        f'<div class="pad"><div style="margin-top:16px">{prin}</div>'
        + ("".join(tarjeta_respuesta(s, v) for s in sug) and '<div class="eti">Sugerencia</div>' + "".join(tarjeta_respuesta(s, v) for s in sug))
        + f'<div class="eti">Próxima acción</div><form method="post" action="/p/{pid}/proxima" class="acc" style="margin:0">{hidden(v=v)}'
        f'<input class="campo" style="flex:1" name="t" maxlength="200" value="{e(p["proxima"] or "")}" placeholder="Ej.: escribirle el jueves" aria-label="Próxima acción">'
        '<button class="btn sec">Guardar</button></form>'
        f'<div class="eti">Temperatura</div><div class="temp" role="radiogroup" aria-label="Temperatura">{temp}</div>'
        f'<div class="eti">Dónde habláis</div><div class="card" style="padding:4px 16px">{canales}</div>{unir}'
        f'<div class="eti">La historia</div><ol class="tl">{tl or "<li data-n=1>Empieza aquí</li>"}</ol>'
        f'<div class="eti">Notas privadas<span>solo tú</span></div><form method="post" action="/p/{pid}/notas">{hidden(v=v)}'
        f'<textarea class="campo" name="t" maxlength="2000" rows="4" onchange="this.form.submit()" aria-label="Notas privadas">{e(p["notas"] or "")}</textarea></form>'
        f'<div class="acc">{arch}{libera}</div></div>', "historias", n_hoy(uid), AVISOS.get(aviso), undo)


def pag_agenda(uid, aviso=None, undo=None):
    hoy = datetime.now(TZ).date()
    cs = q("SELECT c.*, p.nombre, p.temperatura FROM citas c JOIN personas p ON p.id=c.persona_id WHERE c.uid=? AND c.estado='fijada' AND "
           "(c.inicio IS NULL OR c.inicio>=?) ORDER BY c.inicio", uid, hoy.isoformat())
    try:
        lib = libres(uid)
    except Exception:
        lib = []
    dias = ""
    prox = cs[0]["id"] if cs else None
    for i in range(7):
        d = hoy + timedelta(days=i)
        de = [c for c in cs if (c["inicio"] or "")[:10] == d.isoformat()]
        li = [x for x in lib if x[4:9] == d.strftime("%d/%m")]
        cuerpo = "".join(f'<a class="quien" href="/p/{c["persona_id"]}" style="margin-top:8px">{avatar(c["nombre"], c["persona_id"], c["temperatura"])}'
                         f'<div><h3>{e(c["inicio"][11:16])} · {e(c["nombre"])}</h3><div class="meta">{e(c["lugar"] or "")} · en Calendar</div></div></a>'
                         for c in de) or (f'<p class="mute" style="margin:6px 0 0">Tarde libre desde las {e(li[0][-5:])}</p>' if li else
                                          '<p class="mute" style="margin:6px 0 0">—</p>')
        oro = " oro" if any(c["id"] == prox for c in de) else ""
        dias += (f'<section id="d{d.isoformat()}" class="{oro.strip()}"><h2>{DIAS[d.weekday()].capitalize()} {d.day}'
                 f'{" · hoy" if i == 0 else ""}</h2>{cuerpo}</section>')
    sin = [c for c in cs if not c["inicio"]]
    if sin:
        dias += '<div class="eti">Sin fecha clara</div>' + "".join(f'<section><a href="/p/{c["persona_id"]}">{e(c["nombre"])}</a> · {e(c["texto"])}</section>' for c in sin)
    anotar = "".join(tarjeta_resultado(p, "/agenda") for p in personas(uid, "p.etapa='cita_hecha' AND p.archivada=0"))
    mes = hoy.strftime("%Y-%m")
    n_citas = q("SELECT count(*) n FROM citas WHERE uid=? AND inicio LIKE ? AND estado<>'cancelada'", uid, mes + "%")[0]["n"]
    rep = q("SELECT count(*) n FROM personas WHERE uid=? AND resultado IN ('repetir','relacion')", uid)[0]["n"]
    tot = q("SELECT count(*) n FROM personas WHERE uid=?", uid)[0]["n"]
    con = q("SELECT count(DISTINCT persona_id) n FROM citas WHERE uid=?", uid)[0]["n"]
    cifras = (f'<div class="card cifras"><div><b>{n_citas}</b><small>citas este mes</small></div><div><b>{rep}</b><small>repetirían</small></div>'
              f'<div><b>{round(100 * con / tot) if tot else 0}%</b><small>match → cita</small></div></div>')
    cal = "" if user(uid)["cal_rt"] else '<section><h2>Conecta Google Calendar</h2><p>Para ver tus tardes libres y crear las citas solas.</p><a class="btn" href="/cal/conectar">Conectar</a></section>'
    return pagina(cabecera("Tu semana", f"{len(cs)} cita{'s' if len(cs) != 1 else ''} por delante.", fecha_larga()) + semana(uid) + "</header>"
                  + f'<div class="pad">{cal}' + (f'<div class="eti">Por anotar</div>{anotar}' if anotar else "")
                  + f'<div class="eti">Próximos 7 días</div>{dias}<div class="eti">Este mes</div>{cifras}</div>', "agenda", n_hoy(uid), AVISOS.get(aviso), undo)


WA_JS = """async function qr(){const b=document.getElementById('qr');b.innerHTML='Generando…';for(let i=0;i<60;i++){
const r=await (await fetch('/wa/qr',{cache:'no-store'})).json();if(r.estado=='open'){location.reload();return}
if(r.qr)b.innerHTML='<img class="qr" alt="QR de WhatsApp" src="'+r.qr+'">';await new Promise(s=>setTimeout(s,5000))}}
async function codigo(){const b=document.getElementById('cod');b.textContent='Generando código…';
const r=await (await fetch('/wa/codigo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tel:document.getElementById('tel').value})})).json();
if(r.estado=='open'){location.reload();return}
if(!r.codigo){b.textContent=r.error||'No se pudo generar el código. Prueba otra vez.';return}
const c=r.codigo.slice(0,4)+'-'+r.codigo.slice(4);
b.innerHTML='<p style="font:800 34px Manrope,monospace;letter-spacing:4px;margin:12px 0" aria-live="polite">'+c+'</p><ol><li>Abre WhatsApp en tu móvil.</li>'
+'<li>Ajustes → Dispositivos vinculados → Vincular un dispositivo.</li><li>Toca «Vincular con el número de teléfono» y escribe este código.</li></ol>'
+'<p><small>Caduca en unos segundos. Si no entra, pide otro.</small></p><button class="btn sec" onclick="codigo()">Pedir otro código</button>';
for(let i=0;i<45;i++){await new Promise(s=>setTimeout(s,4000));const e=await (await fetch('/wa/estado',{cache:'no-store'})).json();if(e.estado=='open'){location.reload();return}}}"""


def pag_ajustes(uid, aviso=None, undo=None):
    u = user(uid)
    try:
        st = evo("instance/connectionState", u["inst"])["instance"]["state"]
    except Exception:
        st = "sin crear"
    wa = ('<p class="ok">Conectado</p>' if st == "open" else
          '<div class="wa"><div class="watel"><h3>Con número de teléfono</h3><p><small>Lo más fácil desde el móvil.</small></p>'
          f'<div class="acc"><input id="tel" class="campo" style="flex:1;min-width:180px" type="tel" inputmode="tel" autocomplete="tel" value="{e(u["tel"] or "")}" '
          'placeholder="+34 600 000 000" aria-label="Tu número de WhatsApp"><button class="btn" onclick="codigo()">Obtener código</button></div><div id="cod"></div></div>'
          '<div class="waqr"><h3>Con QR</h3><p><small>Desde el ordenador: escanéalo con el móvil en WhatsApp → Dispositivos vinculados → '
          'Vincular un dispositivo.</small></p><div id="qr"><button class="btn sec" onclick="qr()">Mostrar QR</button></div></div></div>')
    cal = '<p class="ok">Conectado</p>' if u["cal_rt"] else '<a class="btn sec" href="/cal/conectar">Conectar Google Calendar</a>'
    chats = "".join(
        f'<div class="fila"><div class="txt"><h3>{e(nombre_vis(c["nombre"]))}</h3><p>{e(c["ultimo"])}</p></div><div class="acc" style="margin:0">'
        + form("/chat/activo", "Quitar" if c["activo"] else "Activar", "btn sec" if c["activo"] else "btn", hidden(jid=c["jid"], v="/ajustes"))
        + (form("/chat/auto", "Auto ON" if c["auto"] else "Auto OFF", "btn" if c["auto"] else "btn sec", hidden(jid=c["jid"], v="/ajustes")) if c["activo"] else "")
        + "</div></div>" for c in q("SELECT * FROM chats WHERE uid=? AND (jid LIKE '%@%' OR jid LIKE 'ig:%') ORDER BY rowid DESC LIMIT 50", uid))
    return pagina(
        cabecera("Ajustes", "Conexiones, modo de respuesta y privacidad.", fecha_larga()) + "</header><div class=\"pad\" style=\"padding-top:16px\">"
        f'<section><h2>WhatsApp</h2>{wa}</section><section><h2>Google Calendar</h2>{cal}<p><small>Solo miramos si estás libre u ocupado y creamos la cita que acordéis.</small></p></section>'
        + ig_seccion(u) + apps_citas(uid) + tinder_seccion(uid) + plan_seccion(u)
        + f'<section><h2>Modo de respuesta</h2><p>{"Automático: contesta sola en los chats de WhatsApp con Auto ON (nunca a quien tiene relación contigo)." if u["modo_auto"] else "Sugerir: tú apruebas cada mensaje."}</p>'
        f'<div class="acc">{form("/auto", "Volver a sugerir" if u["modo_auto"] else "Activar automático", "btn sec", hidden(v="/ajustes"), " onclick=\"return confirm(" + chr(39) + "¿Seguro? Solo afecta a los chats con Auto ON." + chr(39) + ")\"" if not u["modo_auto"] else "")}'
        f'{form("/pausa", "Reanudar CelestIA" if u["pausa"] else "Pausar todo", "btn sec", hidden(v="/ajustes"))}</div></section>'
        f'<section><h2>Chats de WhatsApp</h2>{chats or "<p>Aparecerán cuando te escriban.</p>"}</section>'
        '<section id="instalar"><h2>Instálala en tu móvil</h2><p>Tenla como una app más, con su icono en la pantalla de inicio.</p>'
        '<button class="btn" id="bi" hidden onclick="window.pi&&pi.prompt()">Instalar CelestIA</button>'
        '<p id="ii"><small>iPhone: Compartir → «Añadir a pantalla de inicio». Android: menú ⋮ → «Instalar app».</small></p></section>'
        '<script>addEventListener("beforeinstallprompt",function(ev){ev.preventDefault();window.pi=ev;document.getElementById("bi").hidden=false});'
        'if(matchMedia("(display-mode: standalone)").matches)document.getElementById("instalar").hidden=true</script>'
        '<section class="rojo"><h2>Zona roja</h2><p>Borra tu cuenta, tus historias y desconecta WhatsApp, Calendar y tu Android en la nube.</p>'
        '<form method="post" action="/cuenta/borrar" class="acc"><input class="campo" style="flex:1" name="confirm" placeholder="Escribe BORRAR" '
        'aria-label="Escribe BORRAR para confirmar" autocomplete="off"><button class="btn sec">Borrar cuenta</button></form></section>'
        f'<p class="mute" style="text-align:center"><a href="/logout">Cerrar sesión</a> · <a href="/privacidad">Privacidad</a></p></div><script>{WA_JS}</script>',
        "ajustes", n_hoy(uid), AVISOS.get(aviso), undo)


def plan_seccion(u):
    if u["plan"] == "fundador":
        return '<section><h2>Tu plan</h2><p>Fundador: todo incluido, sin coste.</p></section>'
    est = {"prueba": "En prueba gratis", "activo": "Activo"}.get(u["estado"], u["estado"] or "")
    return (f'<section><h2>Tu plan</h2><p>CelestIA Nube · 29 €/mes + IVA · {e(est)}</p>'
            + form("/pago/portal", "Gestionar o cancelar", "btn sec", hidden(v="/ajustes")) + "</section>")


def ig_seccion(u):
    if u["ig_user"]:
        return f'<section><h2>Instagram</h2><p class="ok">Conectado como @{e(u["ig_user"])}</p><p><small>Activa abajo los chats que quieras que lleve CelestIA. Instagram solo deja contestar en las 24 h siguientes a su último mensaje.</small></p></section>'
    return ('<section><h2>Instagram</h2><p>Para que CelestIA lea y conteste tus mensajes directos, tu cuenta tiene que ser <b>de creador</b> (gratis; tu perfil queda público):</p>'
            '<ol><li>En Instagram: Perfil → ☰ → <b>Tipo de cuenta y herramientas</b> → <b>Cambiar a cuenta profesional</b> → elige <b>Creador</b>.</li>'
            '<li>Ajustes → Mensajes y respuestas a historias → Herramientas conectadas → activa <b>Permitir acceso a los mensajes</b>.</li>'
            '<li>Pulsa el botón, entra con tu Instagram y elige tu cuenta (si te pide un «portfolio empresarial», créalo: es gratis y tarda 1 minuto).</li></ol>'
            + ('<a class="btn" href="/ig/conectar">Conectar Instagram</a>' if META_ID and IG_CONFIG else '<p><small>Muy pronto.</small></p>') + '</section>')


pag_panel = pag_hoy


def apps_citas(uid):
    try:
        st = json.loads(nube("/estado", uid)[1] or b"{}") if NUBE_SECRET else {}
    except (OSError, ValueError):
        return '<section><h2>3 · Hinge y Bumble</h2><p>Tu Android en la nube no responde ahora mismo. Vuelve a intentarlo en un rato.</p></section>'
    e_ = st.get("estado", "ninguno")
    if e_ == "listo":
        return '<section><h2>3 · Hinge y Bumble</h2><p>Tu Android en la nube está listo.</p><a class="btn" href="/nube">Abrir mi Android</a></section>'
    if e_ == "creando":
        return f'<section><h2>3 · Hinge y Bumble</h2><p>Preparando tu Android… ({e(st.get("msg"))})</p><script>setTimeout(()=>location.reload(),15000)</script></section>'
    ops = "".join(f'<option>{e(c)}</option>' for c in CIUDADES)
    err = f'<p><small>No se pudo crear: {e(st.get("msg"))}</small></p>' if e_ == "error" else ""
    return ('<section><h2>3 · Hinge y Bumble</h2><p>Te creamos un móvil Android en la nube solo para ti. Entras tú en tus apps (el código SMS '
            'y cualquier verificación los pasas tú) y CelestIA lee tus chats y te propone respuestas.</p>' + err
            + form("/nube/crear", "Conectar Hinge / Bumble", "btn", '<label>Tu ciudad <select name="ciudad">' + ops + '</select></label> ')
            + '</section>')


def tinder_seccion(uid):
    try:
        st = json.loads(nube("/estado", uid, base=TINDER)[1] or b"{}") if NUBE_SECRET else {}
    except (OSError, ValueError):
        st = {"estado": "error", "msg": "no responde ahora mismo"}
    e_ = st.get("estado", "ninguno")
    if e_ == "listo":
        return '<section><h2>4 · Tinder</h2><p>Tu Tinder está listo.</p><a class="btn" href="/tinder">Abrir mi Tinder</a></section>'
    if e_ == "creando":
        return '<section><h2>4 · Tinder</h2><p>Preparando tu Tinder…</p><script>setTimeout(()=>location.reload(),10000)</script></section>'
    err = f'<p><small>No se pudo preparar: {e(st.get("msg"))}</small></p>' if e_ == "error" else ""
    return ('<section><h2>4 · Tinder</h2><p>Te abrimos Tinder en un navegador en la nube solo para ti, con una IP residencial propia. Entras tú con tu cuenta '
            '(el código SMS y cualquier verificación los pasas tú) y CelestIA lee tus chats y te propone respuestas.</p>' + err
            + form("/tinder/crear", "Conectar Tinder", "btn") + '</section>')


def pag_nube(uid, pre="/nube"):
    js = """let d=null,s=document.getElementById('s');
function xy(e){const r=s.getBoundingClientRect();return[Math.round((e.clientX-r.left)*s.naturalWidth/r.width),Math.round((e.clientY-r.top)*s.naturalHeight/r.height)]}
function p(b){return fetch('PRE/in',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}).then(()=>setTimeout(r,500))}
s.onpointerdown=e=>{d=xy(e);e.preventDefault()};s.onpointerup=e=>{const u=xy(e);p({a:d,b:u});d=null};
function k(c){p({k:c})}function t(){const v=prompt('Texto');if(v)p({t:v})}
function r(){const i=new Image();i.onload=()=>{s.src=i.src};i.src='PRE/shot.png?'+Date.now()}setInterval(r,1500);r()""".replace("PRE", pre)
    tw = pre == "/tinder"
    return pag(('<section><h2>Tu Tinder</h2><p><small>Pulsa «Inicia sesión» y entra con Google o con tu teléfono. El código SMS y cualquier verificación '
                if tw else '<section><h2>Tu Android en la nube</h2><p><small>Abre Hinge o Bumble y entra con tu cuenta. El código SMS y cualquier verificación ')
               + 'los pasas tú aquí mismo.</small></p><div class="row"><button class="btn sec" onclick="k(\'BACK\')">Atrás</button>'
               '<button class="btn sec" onclick="k(\'HOME\')">Inicio</button><button class="btn sec" onclick="t()">Escribir</button>'
               + ('<button class="btn sec" onclick="k(\'ENTER\')">Intro</button>' if tw else '') + '<a class="btn sec" href="/">Volver al panel</a></div>'
               f'<img id="s" alt="Pantalla" style="width:100%;max-width:{"500" if tw else "360"}px;display:block;margin:12px auto 96px;border-radius:18px;touch-action:none">'
               f'</section><script>{js}</script>', uid)


PLAN_INCLUYE = ("Tu Android en la nube con Hinge y Bumble, siempre encendido", "IP residencial propia: tus apps te ven como en casa",
                "IA que lee tus chats y te propone qué contestar (tokens incluidos)", "Modo automático con ritmo humano y tope diario",
                "Historias, agenda y citas directas a tu Google Calendar")


def pag_planes(uid, volviendo=False):
    """Usuario sin suscripción (o con impago/cancelada): solo planes, salir y borrar cuenta."""
    u = user(uid)
    aviso = {"impago": ("No pudimos cobrar tu último pago", "Actualiza tu tarjeta y todo vuelve a funcionar al momento."),
             "cancelado": ("Tu suscripción terminó", "Tus historias siguen aquí. Vuelve cuando quieras.")}.get(u["estado"])
    if volviendo:
        aviso = ("Confirmando tu pago…", "Tarda unos segundos. Esta página se actualiza sola.")
    nuevo = not u["estado"]
    cta = form("/pago/checkout", "Actualizar tarjeta" if u["estado"] == "impago" else "Empieza 3 días gratis" if nuevo else "Activar CelestIA Nube",
               "btn", extra=' style="width:100%"')
    if volviendo:  # el aviso del pago aún no llegó: sin botón, para no abrir otra caja
        cta = ""
    lista = "".join(f'<li><i aria-hidden="true"></i>{e(x)}</li>' for x in PLAN_INCLUYE)
    css = ("<style>.plan{position:relative;overflow:hidden;padding:22px 18px;border:0;background:var(--card);"
           "box-shadow:0 0 0 1.5px transparent,0 18px 40px -24px rgba(139,61,255,.55);background-image:linear-gradient(var(--card),var(--card)),var(--grad);"
           "background-origin:border-box;background-clip:padding-box,border-box;border:1.5px solid transparent}"
           ".plan .eti{margin:0 0 6px}.precio{display:flex;align-items:baseline;gap:6px;margin:4px 0 2px}.precio b{font:800 52px/1 Manrope,sans-serif;letter-spacing:-.04em}"
           ".precio span{font:700 15px Manrope,sans-serif;color:var(--mute)}.plan ul{list-style:none;padding:0;margin:18px 0}"
           ".plan li{display:flex;gap:10px;align-items:flex-start;padding:7px 0;color:var(--ink)}.plan li i{flex:0 0 18px;height:18px;margin-top:3px;border-radius:50%;background:var(--grad);"
           "-webkit-mask:radial-gradient(circle,#000 38%,transparent 40%),linear-gradient(#000,#000);-webkit-mask-composite:xor;mask-composite:exclude}"
           ".insignia{display:inline-block;border-radius:999px;padding:4px 10px;font:800 11px Manrope,sans-serif;letter-spacing:.12em;text-transform:uppercase;"
           "background:rgba(230,198,122,.18);color:#a8862f}@media(prefers-color-scheme:dark){.insignia{color:var(--d)}}</style>")
    return pagina(
        css + cabecera("Del match<br>a la cita, sin mover un dedo.", "Un plan, todo incluido. Pruébalo 3 días gratis y cancela en un toque.")
        + "</header><div class=\"pad\" style=\"padding-top:16px\">"
        + (f'<section class="rojo" role="status"><h2>{e(aviso[0])}</h2><p>{e(aviso[1])}</p></section>' if aviso else "")
        + '<section class="plan"><p class="eti"><span>CelestIA Nube</span>' + ('<span class="insignia">3 días gratis</span>' if nuevo else "") + "</p>"
        '<div class="precio"><b>29 €</b><span>/mes + IVA</span></div>'
        + ('<p style="margin:0">Hoy pagas 0 €. Si no cancelas, se cobra al acabar la prueba.</p>' if nuevo else "<p style=\"margin:0\">Cancela cuando quieras.</p>")
        + f"<ul>{lista}</ul>{cta}</section>"
        + ('<p class="mute" style="text-align:center;font-size:13px">' + (form("/pago/portal", "Gestionar mi suscripción", "btn sec") + "<br>" if u["stripe_cus"] else "")
           + 'Pago seguro con Stripe. IVA según tu país.</p>')
        + '<details class="mute" style="text-align:center"><summary>Salir o borrar mi cuenta</summary>'
        '<form method="post" action="/cuenta/borrar" class="acc"><input class="campo" style="flex:1" name="confirm" placeholder="Escribe BORRAR" '
        'aria-label="Escribe BORRAR para confirmar" autocomplete="off"><button class="btn sec">Borrar cuenta</button></form>'
        '<p><a href="/logout">Cerrar sesión</a> · <a href="/terminos">Términos</a> · <a href="/privacidad">Privacidad</a></p></details></div>'
        + ('<script>var n=0;try{n=+sessionStorage.getItem("pago")||0;sessionStorage.setItem("pago",n+1)}catch(_){}'
           'if(n<20)setTimeout(function(){location.replace("/?ok=pago")},3000)</script>' if volviendo else ""))


LEGAL = {"privacidad": ("Privacidad", "<p>Responsable: " + OPERADOR + ". Tratamos tu email y nombre de Google, "
                        "el estado ocupado/libre de tu calendario (si lo conectas) y los chats de WhatsApp e Instagram (por la API oficial de Meta, si la conectas) que actives, solo para proponerte y enviar respuestas. "
                        "No guardamos el contenido de tus mensajes salvo el último recibido y la propuesta, que se borran a los 90 días. "
                        "Encargados: tu proveedor de alojamiento, Google (inicio de sesión y calendario), Meta (mensajes de Instagram) y Anthropic (IA que redacta, sin entrenar con tus datos). "
                        "Puedes borrar tu cuenta y todos tus datos desde el panel; al hacerlo revocamos también el acceso a tu Google Calendar. Con tu calendario solo hacemos dos cosas: consultar si estás libre u ocupado (nunca leemos títulos ni detalles) y crear el evento de la cita que acuerdes. No vendemos ni compartimos tus datos de Google, no los usamos para publicidad ni para entrenar modelos de IA. El uso de datos de Google cumple la Google API Services User Data Policy, "
                        "incluidos los requisitos de uso limitado.</p>"),
         "terminos": ("Términos", "<p>CelestIA es un asistente: tú eres responsable de lo que se envía desde tu cuenta. Las apps y WhatsApp pueden "
                      "limitar cuentas automatizadas; el modo automático es opcional y lo activas tú. Servicio prestado por " + OPERADOR + ".</p>")}


class H(BaseHTTPRequestHandler):
    def uid(self):
        c = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        d = leer(c["s"].value) if "s" in c else None
        if d:
            u, exp = d.rsplit("|", 1)
            if int(exp) > time.time() and user(u):
                return u

    def out(self, code, body=b"", tipo="text/html; charset=utf-8", extra=()):
        self.send_response(code)
        for k, v in (("Content-Type", tipo), ("X-Frame-Options", "DENY"), ("Referrer-Policy", "same-origin"),
                     ("Cache-Control", "private, no-store"), ("X-Content-Type-Options", "nosniff"), *extra):
            self.send_header(k, v)
        self.end_headers(); self.wfile.write(body if isinstance(body, bytes) else body.encode())

    def ir(self, a, extra=()):
        self.out(303, extra=(("Location", a), *extra))

    def do_GET(self):
        p = urllib.parse.urlparse(self.path); a = urllib.parse.parse_qs(p.query); uid = self.uid()
        if p.path == "/logo.png":
            return self.out(200, open(f"{D}/static/logo.png", "rb").read(), "image/png")
        if p.path in ("/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"):
            f_ = "icon-180.png" if "apple" in p.path else p.path[1:]
            return self.out(200, open(f"{D}/static/{f_}", "rb").read(), "image/png")
        if p.path == "/manifest.webmanifest":
            return self.out(200, json.dumps(MANIFEST, ensure_ascii=False), "application/manifest+json")
        if p.path == "/robots.txt":
            return self.out(200, "User-agent: *\nDisallow: /\n", "text/plain")
        if p.path.strip("/") in LEGAL:
            t, b = LEGAL[p.path.strip("/")]
            return self.out(200, pag(f"<section><h1>{t}</h1>{b}</section>", uid))
        if p.path == "/auth/google":
            return self.ir(google_url("login", "openid email profile"))
        if p.path == "/auth/callback":
            return self.callback(a, uid)
        if p.path == "/ig/hook":  # verificación del webhook de Meta
            ok_ = IG_VERIFY and a.get("hub.mode", [""])[0] == "subscribe" and hmac.compare_digest(a.get("hub.verify_token", [""])[0], IG_VERIFY)
            return self.out(200, a.get("hub.challenge", [""])[0], "text/plain") if ok_ else self.out(403, "no")
        if p.path == "/logout":
            return self.ir("/", (("Set-Cookie", "s=; Path=/; Max-Age=0"),))
        if not uid:
            return self.out(200, pag_entrar())
        if not de_pago(user(uid)):
            return self.out(200, pag_planes(uid, a.get("ok", [""])[0] == "pago"))
        if p.path == "/cal/conectar":
            return self.ir(google_url("cal", "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.freebusy",
                                      {"access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "login_hint": user(uid)["email"]}))
        if p.path in ("/nube", "/tinder"):
            return self.out(200, pag_nube(uid, p.path))
        if p.path == "/ig/conectar":
            return self.ir(ig_url(uid)) if META_ID and IG_CONFIG else self.ir("/ajustes")
        if p.path == "/ig/callback":
            st = leer(a.get("state", [""])[0]) or ""
            if not st.startswith(f"ig|{uid}|") or int(st.split("|")[2]) < time.time() - 600 or "code" not in a:
                return self.out(400, pag("<section><h2>Enlace caducado</h2><a class='btn' href='/ajustes'>Volver</a></section>", uid))
            try:
                ig_conectar(uid, a["code"][0])
            except (urllib.error.URLError, KeyError, ValueError):
                return self.out(400, pag("<section><h2>Instagram no aceptó la conexión. ¿Es una cuenta profesional (creador o empresa)?</h2>"
                                         "<a class='btn' href='/ajustes'>Volver</a></section>", uid))
            return self.ir("/ajustes?ok=ig")
        if p.path in ("/nube/shot.png", "/tinder/shot.png"):
            tw = p.path.startswith("/tinder")
            st, b = nube("/shot", uid, base=TINDER) if tw else nube("/shot", uid)
            return self.out(200, b, "image/jpeg" if tw else "image/png") if st == 200 else self.out(404, "")
        if p.path == "/wa/estado":
            try:
                return self.out(200, json.dumps({"estado": wa_estado(uid) or "sin crear"}), "application/json")
            except Exception:
                return self.out(502, json.dumps({"estado": "error"}), "application/json")
        if p.path == "/wa/qr":
            try:
                return self.out(200, json.dumps(wa_qr(uid)), "application/json")
            except Exception as x:
                return self.out(502, json.dumps({"estado": "error", "error": type(x).__name__}), "application/json")
        av, ud = a.get("ok", [None])[0], a.get("undo", [None])[0]
        ud = int(ud) if ud and ud.isdigit() else None
        if p.path != "/" and not user(uid)["consent_at"]:
            return self.ir("/")
        if p.path == "/historias":
            return self.out(200, pag_historias(uid, a.get("f", ["activas"])[0], a.get("q", [""])[0][:60], av, ud))
        if p.path == "/agenda":
            return self.out(200, pag_agenda(uid, av, ud))
        if p.path == "/ajustes":
            return self.out(200, pag_ajustes(uid, av, ud))
        if m := re.fullmatch(r"/p/(\d+)", p.path):
            h = pag_persona(uid, int(m[1]), av, ud)
            return self.out(200, h) if h else self.out(404, pag("<section><h2>No encontrada</h2><a class='btn' href='/historias'>Volver</a></section>", uid))
        self.out(200, pag_hoy(uid, av, ud))

    def callback(self, a, uid):
        st = leer(a.get("state", [""])[0])
        if not st or "code" not in a or int(st.split("|")[1]) < time.time() - 600:
            return self.out(400, pag("<section><h2>Enlace caducado</h2><a class='btn' href='/'>Volver</a></section>"))
        try:
            tok = google_token({"code": a["code"][0], "redirect_uri": BASE + "/auth/callback", "grant_type": "authorization_code"})
        except Exception:
            return self.out(400, pag("<section><h2>Google no aceptó el inicio de sesión. Prueba otra vez.</h2><a class='btn' href='/'>Volver</a></section>"))
        c = id_claims(tok.get("id_token", ""))
        if not c:
            return self.out(403, "no")
        if st.startswith("cal|"):
            if c["sub"] != uid or not tok.get("refresh_token"):
                return self.out(403, pag("<section><h2>Usa la misma cuenta de Google con la que entraste.</h2><a class='btn' href='/'>Volver</a></section>"))
            q("UPDATE users SET cal_rt=? WHERE uid=?", fernet().encrypt(tok["refresh_token"].encode()), uid)
            return self.ir("/")
        if not permitido(c.get("email")):
            return self.out(403, pag("<section><h2>Esta cuenta de Google no tiene acceso a este panel.</h2><a class='btn' href='/'>Volver</a></section>"))
        with db() as d:
            d.execute("INSERT INTO users(uid,email,nombre,inst,hook,creado) VALUES(?,?,?,?,?,?) ON CONFLICT(uid) DO UPDATE SET email=excluded.email",
                      (c["sub"], c["email"], c.get("name") or c["email"], inst_de(c["sub"]), os.urandom(16).hex(), datetime.now(TZ).isoformat()))
        ck = f"s={firmar(c['sub'] + '|' + str(int(time.time()) + 30 * 86400))}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={30 * 86400}"
        self.ir("/", (("Set-Cookie", ck),))

    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        n = min(int(self.headers.get("Content-Length", 0) or 0), 2_000_000)
        raw = self.rfile.read(n)
        if p.path.startswith("/hook/"):
            return self.hook(p.path, raw)
        if p.path == "/ig/hook":
            ok_ = ig_firma_ok(raw, self.headers.get("X-Hub-Signature-256"))
            print(f"ig/hook firma={'ok' if ok_ else 'mal'} bytes={len(raw)}", flush=True)  # sin contenido: solo para saber que Meta llega
            if not ok_:
                return self.out(403, "no")
            try:
                ev = json.loads(raw)
            except ValueError:
                return self.out(400, "json")
            self.out(200, "ok")
            return threading.Thread(target=ig_procesar, args=(ev,), daemon=True).start()
        if p.path == "/stripe/hook":
            if not stripe_firma_ok(raw, self.headers.get("Stripe-Signature")):
                return self.out(400, "firma")
            try:
                r = stripe_evento(json.loads(raw))
            except (ValueError, KeyError, TypeError, urllib.error.URLError) as x:
                print(f"stripe/hook error {type(x).__name__}", flush=True)
                return self.out(500, "error")  # Stripe reintenta
            print(f"stripe/hook {r}", flush=True)
            return self.out(200, "ok")
        if p.path == "/bridge/citas":
            if not BRIDGE_SECRET or not hmac.compare_digest(self.headers.get("X-Bridge-Secret", ""), BRIDGE_SECRET):
                return self.out(403, "no")
            try:
                n = puente(json.loads(raw))
            except ValueError:
                return self.out(400, "json")
            return self.out(200 if n >= 0 else 404, json.dumps({"sugerencias_nuevas": n}), "application/json")
        uid = self.uid()
        if not uid or self.headers.get("Origin") != BASE:  # CSRF: solo formularios de nuestro propio origen
            return self.out(403, "no")
        if p.path in ("/pago/checkout", "/pago/portal"):
            try:
                return self.ir(checkout(uid) if p.path == "/pago/checkout" else portal(uid))
            except (urllib.error.URLError, KeyError, ValueError):
                return self.out(502, pag("<section><h2>El pago no responde ahora. Prueba en un minuto.</h2><a class='btn' href='/'>Volver</a></section>"))
        if not de_pago(user(uid)) and p.path != "/cuenta/borrar":
            return self.ir("/")
        if p.path in ("/nube/in", "/tinder/in"):
            tw = p.path == "/tinder/in"
            try:
                j = json.loads(raw)
                b = {"k": j["k"]} if j.get("k") in (("BACK", "HOME", "ENTER") if tw else ("BACK", "HOME")) else {"t": str(j["t"])[:500]} if "t" in j else \
                    {"a": [int(v) for v in j["a"]][:2], "b": [int(v) for v in j["b"]][:2]}
            except (ValueError, KeyError, TypeError):
                return self.out(400, "json")
            return self.out((nube("/in", uid, b, base=TINDER) if tw else nube("/in", uid, b))[0], "")
        if p.path == "/wa/codigo":
            try:
                tel = tel_ok(json.loads(raw).get("tel"))
            except (ValueError, AttributeError):
                tel = None
            if not tel:
                return self.out(400, json.dumps({"estado": "error", "error": "Escribe tu número con prefijo, por ejemplo +34 600 000 000."}), "application/json")
            q("UPDATE users SET tel=? WHERE uid=?", tel, uid)
            try:
                return self.out(200, json.dumps(wa_codigo(uid, tel)), "application/json")
            except Exception:
                return self.out(502, json.dumps({"estado": "error", "error": "WhatsApp no responde ahora. Prueba en un minuto."}), "application/json")
        f = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode()).items()}
        jid, aviso, undo = f.get("jid", ""), None, None
        if p.path == "/nube/crear":
            lat, lon = CIUDADES.get(f.get("ciudad"), CIUDADES["Madrid"])
            nube("/crear", uid, {"lat": lat, "lon": lon})
        elif p.path == "/tinder/crear":
            nube("/crear", uid, {}, base=TINDER)
        elif p.path == "/consent":
            tel = tel_ok(f.get("tel"))
            if not tel:
                return self.out(400, pag("<section><h2>Revisa tu número de WhatsApp (con prefijo, p. ej. +34 600 000 000).</h2>"
                                         "<a class='btn' href='/'>Volver</a></section>", uid))
            q("UPDATE users SET consent_at=?, tel=? WHERE uid=?", datetime.now(TZ).isoformat(), tel, uid)
        elif p.path == "/auto":
            q("UPDATE users SET modo_auto=1-modo_auto WHERE uid=?", uid)
        elif p.path == "/pausa":
            q("UPDATE users SET pausa=1-pausa WHERE uid=?", uid)
        elif p.path == "/chat/activo":
            q("UPDATE chats SET activo=1-activo, auto=0 WHERE uid=? AND jid=?", uid, jid)
            persona_de(uid, jid)
        elif p.path == "/chat/auto":
            q("UPDATE chats SET auto=1-auto WHERE uid=? AND jid=? AND activo=1", uid, jid)
        elif m := re.fullmatch(r"/sug/(\d+)/(enviar|descartar|luego|otra|copiada)", p.path):
            s = q("SELECT * FROM sugerencias WHERE id=? AND uid=?", int(m[1]), uid)
            if not s:
                return self.ir(volver_ok(f.get("v")))
            s, sid = s[0], int(m[1])
            if m[2] == "enviar" and not s["escalar"]:
                err = enviar(uid, s["jid"], (f.get("t") or s["texto"])[:600])
                if err:
                    return self.out(429, pag(f"<section><h2>Ahora no se puede enviar ({e(err)}).</h2><a class='btn' href='/'>Volver</a></section>", uid))
                q("UPDATE sugerencias SET estado='enviada' WHERE id=? AND uid=?", sid, uid)
                aviso = "env"
            elif m[2] == "luego":
                q("UPDATE sugerencias SET luego=? WHERE id=? AND uid=?", (datetime.now(TZ) + timedelta(hours=4)).isoformat(timespec="seconds"), sid, uid)
                aviso = "luego"
            elif m[2] == "otra":
                try:
                    hist = mensajes(user(uid)["inst"], s["jid"]) if es_wa(s["jid"]) else []
                except Exception:
                    hist = []
                r = ia.proponer(hist or [("otro", s["entrada"])], user(uid)["perfil"], [])
                if r["respuesta"]:
                    q("UPDATE sugerencias SET texto=? WHERE id=? AND uid=?", r["respuesta"], sid, uid)
                aviso = "otra"
            else:  # descartar o copiada (la manda él desde la app)
                q("UPDATE sugerencias SET estado=? WHERE id=? AND uid=?", "enviada" if m[2] == "copiada" else "descartada", sid, uid)
        elif m := re.fullmatch(r"/p/(\d+)/(etapa|resultado|temp|proxima|notas|archivar|ia)", p.path):
            pid, acc = int(m[1]), m[2]
            if not q("SELECT 1 FROM personas WHERE id=? AND uid=?", pid, uid):
                return self.out(404, "no")
            if acc == "etapa":
                undo, aviso = avanzar(uid, pid, f.get("e", ""), "usuario"), "fase"
            elif acc == "resultado":
                undo, aviso = poner_resultado(uid, pid, f.get("r", "")), "res"
            elif acc == "temp":
                t = int(f["t"]) if f.get("t", "").isdigit() and f["t"] in "123" else 2
                q("UPDATE personas SET temperatura=? WHERE id=? AND uid=?", t, pid, uid); aviso = "temp"
            elif acc == "proxima":
                q("UPDATE personas SET proxima=? WHERE id=? AND uid=?", (f.get("t") or "").strip()[:200] or None, pid, uid); aviso = "prox"
            elif acc == "notas":
                q("UPDATE personas SET notas=? WHERE id=? AND uid=?", (f.get("t") or "")[:2000], pid, uid); aviso = "nota"
            elif acc == "archivar":
                a_ = q("SELECT archivada FROM personas WHERE id=?", pid)[0]["archivada"]
                q("UPDATE personas SET archivada=? WHERE id=? AND uid=?", 1 - a_, pid, uid); aviso = "reab" if a_ else "arch"
            else:
                q("UPDATE personas SET etapa_fuente='ia' WHERE id=? AND uid=?", pid, uid); aviso = "ia"
        elif p.path == "/unir":
            a_, b_ = (int(f[k]) if f.get(k, "").isdigit() else 0 for k in ("a", "b"))
            if unir(uid, a_, b_):
                aviso = "unir"
        elif p.path == "/deshacer":
            if f.get("ev", "").isdigit():
                deshacer(uid, int(f["ev"]))
            aviso = "desh"
        elif p.path == "/cuenta/borrar":
            if f.get("confirm", "").strip().upper() != "BORRAR":
                return self.ir("/ajustes")
            try:
                borrar(uid)
            except urllib.error.URLError:
                return self.out(502, pag("<section><h2>No pudimos cancelar tu suscripción ahora, así que no hemos borrado nada. Prueba en un minuto.</h2>"
                                         "<a class='btn' href='/'>Volver</a></section>"))
            return self.ir("/", (("Set-Cookie", "s=; Path=/; Max-Age=0"),))
        v = volver_ok(f.get("v"))
        if aviso:
            v += ("&" if "?" in v else "?") + "ok=" + aviso + (f"&undo={undo}" if undo else "")
        self.ir(v)

    def hook(self, path, raw):
        parts = path.split("/")
        u = user(parts[2]) if len(parts) == 4 else None
        if not u or not hmac.compare_digest(u["hook"], parts[3]):
            return self.out(403, "no")
        try:
            ev = json.loads(raw)
        except ValueError:
            return self.out(400, "json")
        self.out(200, "ok")
        if ev.get("instance") == u["inst"] and str(ev.get("event", "")).lower().replace("_", ".") == "messages.upsert":
            threading.Thread(target=procesar, args=(u["uid"], ev.get("data")), daemon=True).start()

    def log_message(self, *a):
        pass


def liberar_nube(uid):
    if NUBE_SECRET:
        for base in (None, TINDER):  # su Android y su disco; su Chrome de Tinder y su perfil (uno caído no salva al otro)
            try:
                nube("/borrar", uid, {}, base=base)
            except Exception as x:
                print("liberar_nube", uid, base, x, flush=True)


def borrar(uid):
    u = user(uid)
    if not u:
        return
    if u["stripe_sub"] and u["estado"] != "cancelado":
        try:  # primero que no se le siga cobrando; si Stripe no responde, no se borra nada (lanza)
            stripe(f"subscriptions/{u['stripe_sub']}", metodo="DELETE")
        except urllib.error.HTTPError as x:
            if x.code != 404:
                raise
    try:
        evo("instance/logout", u["inst"], metodo="DELETE"); evo("instance/delete", u["inst"], metodo="DELETE")
    except Exception:
        pass
    if u["cal_rt"]:
        try:  # quitar también el permiso de Google Calendar
            urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/revoke",
                                   data=urllib.parse.urlencode({"token": fernet().decrypt(u["cal_rt"]).decode()}).encode()), timeout=20)
        except Exception:
            pass
    liberar_nube(uid)
    with db() as c:
        for t in ("sugerencias", "chats", "envios", "personas", "eventos", "citas", "users"):
            c.execute(f"DELETE FROM {t} WHERE uid=?", (uid,))


def purga():
    while True:
        lim = (datetime.now(TZ) - timedelta(days=90)).isoformat()
        q("DELETE FROM sugerencias WHERE creado<?", lim); q("DELETE FROM envios WHERE ts<?", time.time() - 90 * 86400)
        try:
            barrido()
        except Exception:
            pass
        time.sleep(3600)


def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL"); c.executescript(ESQUEMA)
        cols = {r[1] for r in c.execute("PRAGMA table_info(chats)")}
        for col, tipo in (("etapa", "TEXT DEFAULT 'conversando'"), ("cita", "TEXT")):
            if col not in cols:
                c.execute(f"ALTER TABLE chats ADD COLUMN {col} {tipo}")
        for col, tipo in (("persona_id", "INT"), ("desde", "TEXT")):
            if col not in cols:
                c.execute(f"ALTER TABLE chats ADD COLUMN {col} {tipo}")
        if "tel" not in {r[1] for r in c.execute("PRAGMA table_info(users)")}:
            c.execute("ALTER TABLE users ADD COLUMN tel TEXT")
        ucols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
        for col in ("ig_id TEXT", "ig_user TEXT", "ig_tok BLOB"):
            if col.split()[0] not in ucols:
                c.execute(f"ALTER TABLE users ADD COLUMN {col}")
        if "plan" not in ucols:  # pago: quien ya estaba antes de cobrar queda como fundador (exento), sin tocar nada más
            for col in ("plan TEXT", "estado TEXT", "stripe_cus TEXT", "stripe_sub TEXT", "estado_ts INT"):
                c.execute(f"ALTER TABLE users ADD COLUMN {col}")
            c.execute("UPDATE users SET plan='fundador'")
        if "luego" not in {r[1] for r in c.execute("PRAGMA table_info(sugerencias)")}:
            c.execute("ALTER TABLE sugerencias ADD COLUMN luego TEXT")
    migrar()


def fallos_config():
    """Lo que impide arrancar con seguridad: el código es público, así que nada de claves por defecto ni panel abierto a todo internet."""
    f = []
    if len(SKEY) < 32 or SKEY == b"dev-only-key":
        f.append("SESSION_KEY: pon 32+ caracteres al azar (python3 -c \"import secrets;print(secrets.token_urlsafe(32))\")")
    try:
        fernet()
    except Exception:
        f.append("FERNET_KEY: falta o no es válida (python3 -c \"import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())\")")
    if not STRIPE_KEY and not PERMITIDOS:
        f.append("ALLOWED_EMAILS: sin Stripe, di qué cuentas de Google pueden entrar (tu email, separados por comas)")
    if BRIDGE_SECRET and len(BRIDGE_SECRET) < 32:
        f.append("BRIDGE_SECRET: vacío o 32+ caracteres al azar")
    return f


if __name__ == "__main__":
    if fallos_config():
        raise SystemExit("No arranco, revisa config.env:\n- " + "\n- ".join(fallos_config()))
    init()
    threading.Thread(target=purga, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(ENV("PORT", "8990"))), H).serve_forever()
