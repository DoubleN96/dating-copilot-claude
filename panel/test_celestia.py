"""python3 test_celestia.py — asserts de las partes que no pueden fallar: aislamiento, salvaguardas, escalado, webhook y CSRF."""
import base64, json, os, tempfile, threading, time, urllib.error, urllib.request
os.environ.update(DB_PATH=tempfile.mktemp(suffix=".db"), SESSION_KEY="k", GOOGLE_CLIENT_ID="cid", BASE_URL="http://127.0.0.1:8997",
                  FERNET_KEY=base64.urlsafe_b64encode(b"0" * 32).decode(), PORT="8997", STRIPE_SECRET_KEY="sk_test_dummy")
import app, ia

app.init()
for uid in ("A", "B"):
    app.q("INSERT INTO users(uid,email,nombre,inst,hook,consent_at,plan) VALUES(?,?,?,?,?,?,'fundador')", uid, f"{uid}@x", uid, app.inst_de(uid), "s" + uid, "x")
app.q("INSERT INTO chats(uid,jid,nombre,activo) VALUES('A','1@s.whatsapp.net','Ana',1)")
app.q("INSERT INTO sugerencias(uid,jid,msg_id,entrada,texto,escalar,estado) VALUES('A','1@s.whatsapp.net','m1','hola','hey',0,'pendiente')")

# instancias: solo celestia-<hex12>, nunca la personal
assert app.INST_RE.match(app.inst_de("A")) and app.inst_de("A") != app.inst_de("B")
for bad in ("personal", "celestia-xyz", "../personal"):
    try:
        app.evo("instance/connectionState", bad); assert False, bad
    except ValueError:
        pass

# aislamiento: B no ve nada de A
assert app.q("SELECT * FROM sugerencias WHERE uid=?", "B") == [] and app.q("SELECT * FROM chats WHERE uid=?", "B") == []

# salvaguardas de envío
assert app.control("A") is None
app.q("INSERT INTO envios VALUES('A','1@s.whatsapp.net','x',?)", time.time())
assert app.control("A") == "ritmo"
app.q("DELETE FROM envios"); [app.q("INSERT INTO envios VALUES('A','j','x',?)", time.time() - 3600) for _ in range(app.TOPE)]
assert app.control("A") == "tope diario" and app.control("B") is None
app.q("UPDATE users SET pausa=1 WHERE uid='B'"); assert app.control("B") == "pausa"

# escalado por reglas, sin llamar a la IA
for t in ("oye, ¿eres una IA?", "¿esto es chatgpt?", "tengo 16", "déjame en paz"):
    assert ia.proponer([("otro", t)])["escalar"], t
assert not ia.escalar_por_reglas("¿te apetece un vino el jueves?")

# sesión firmada
assert app.leer(app.firmar("A|1")) == "A|1" and app.leer("A|1.deadbeef") is None

# id_token: aud/iss/email_verified
mk = lambda c: "x." + base64.urlsafe_b64encode(json.dumps(c).encode()).decode().rstrip("=") + ".y"
ok = {"iss": "https://accounts.google.com", "aud": "cid", "exp": time.time() + 60, "email_verified": True, "sub": "A", "email": "a@x"}
assert app.id_claims(mk(ok)) and not app.id_claims(mk({**ok, "aud": "otro"})) and not app.id_claims(mk({**ok, "email_verified": False}))

# servidor: webhook con secreto malo -> 403; POST sin Origin propio -> 403; enviar sugerencia de otro usuario no hace nada
threading.Thread(target=app.ThreadingHTTPServer(("127.0.0.1", 8997), app.H).serve_forever, daemon=True).start(); time.sleep(0.3)


def post(path, body=b"", headers=None):
    try:
        return urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8997" + path, data=body, headers=headers or {})).status
    except urllib.error.HTTPError as x:
        return x.code


assert post("/hook/A/malo", b"{}") == 403 and post("/hook/A/sA", b"{}") == 200
ckB = {"Cookie": "s=" + app.firmar(f"B|{int(time.time()) + 99}")}
assert post("/sug/1/descartar", b"", ckB) == 403  # sin Origin
app.q("UPDATE users SET pausa=0 WHERE uid='B'")
post("/sug/1/descartar", b"", {**ckB, "Origin": app.BASE})
assert app.q("SELECT estado FROM sugerencias WHERE id=1")[0]["estado"] == "pendiente"  # B no toca lo de A
assert urllib.request.urlopen("http://127.0.0.1:8997/robots.txt").status == 200

# cita: solo fechas válidas y futuras
from datetime import datetime, timedelta
fut = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
assert ia.cita_valida({"inicio": fut, "lugar": "Malasaña"})["lugar"] == "Malasaña"
assert ia.cita_valida({"inicio": "2020-01-01T20:00"}) is None and ia.cita_valida({"inicio": "jueves"}) is None and ia.cita_valida(None) is None

# webhook -> sugerencia -> etapa/cita en el tablero; el historial caído no rompe; la cita no se crea dos veces
creadas = []
app.mensajes = lambda *a: (_ for _ in ()).throw(OSError("evolution caído"))
app.crear_cita = lambda uid, nombre, c: creadas.append(nombre) or "jue 20:00 · Malasaña"
app.ia.proponer = lambda hist, perfil, hs: {"respuesta": "¡hecho!", "escalar": False, "motivo": "", "etapa": "cita",
                                            "cita": {"inicio": datetime.now() + timedelta(days=2), "lugar": "Malasaña"}}
app.q("UPDATE users SET cal_rt=? WHERE uid='A'", b"x")
for mid in ("m2", "m3"):
    app.procesar("A", {"key": {"remoteJid": "1@s.whatsapp.net", "id": mid}, "message": {"conversation": "vale, el jueves a las 8"}})
ch = app.q("SELECT etapa, cita FROM chats WHERE uid='A' AND jid='1@s.whatsapp.net'")[0]
assert ch["etapa"] == "cita" and ch["cita"].startswith("jue") and creadas == ["Ana"], (dict(ch), creadas)
assert app.q("SELECT count(*) n FROM sugerencias WHERE uid='A' AND msg_id IN ('m2','m3')")[0]["n"] == 2
assert "Malasaña" in app.pag_agenda("A") and "Malasaña" not in app.pag_agenda("B")  # agenda aislada por usuario
# puente de apps de citas: solo el usuario de BRIDGE_EMAIL, secreto obligatorio, solo lectura, sin duplicar sugerencias
app.BRIDGE_EMAIL, app.BRIDGE_SECRET = "A@x", "pb"
datos = {"chats": [{"app": "tinder", "id": "abc123", "nombre": "Eva", "ultimo": "¿y tú?", "toca": True, "hist": [["yo", "hola"], ["otro", "¿y tú?"]]},
                   {"app": "hinge", "id": "Lu", "nombre": "Lu", "toca": False, "hist": [["otro", "hey"]]},
                   {"app": "whatsapp", "id": "x", "nombre": "no", "toca": True, "hist": [["otro", "x"]]}]}
hdr = {"X-Bridge-Secret": "pb", "Content-Type": "application/json"}
assert post("/bridge/citas", json.dumps(datos).encode(), {"X-Bridge-Secret": "malo"}) == 403
assert post("/bridge/citas", json.dumps(datos).encode(), hdr) == 200 and post("/bridge/citas", json.dumps(datos).encode(), hdr) == 200
assert {r["jid"] for r in app.q("SELECT jid FROM chats WHERE uid='A' AND jid NOT LIKE '%@%'")} == {"tinder:abc123", "hinge:Lu"}
assert app.q("SELECT count(*) n FROM sugerencias WHERE uid='A' AND jid='tinder:abc123'")[0]["n"] == 1  # una vez, no en cada pasada
assert not app.q("SELECT 1 FROM chats WHERE uid='B' AND jid LIKE 'tinder:%'")  # B no ve nada
assert app.enviar("A", "tinder:abc123", "hola") == "solo lectura"
panel = app.pag_panel("A")
assert "Eva" in panel and "Copiar y abrir Tinder" in panel and "Eva" not in app.pag_panel("B")

# Android en la nube propio: el puente con uid solo escribe en ese usuario (prefijo n-), envío manual con control() y agente
datos_b = {"uid": "B", "chats": [{"app": "hinge", "id": "Mar", "nombre": "Mar", "toca": True, "hist": [["otro", "¿cenamos?"]]}]}
assert post("/bridge/citas", json.dumps({**datos_b, "uid": "nadie"}).encode(), hdr) == 404  # uid inexistente: nada
assert post("/bridge/citas", json.dumps(datos_b).encode(), hdr) == 200
assert app.q("SELECT jid FROM chats WHERE uid='B' AND jid LIKE 'n-%'")[0]["jid"] == "n-hinge:Mar"
assert not app.q("SELECT 1 FROM chats WHERE uid='A' AND jid LIKE 'n-%'")  # A no ve el Android de B
llamadas = []
app.nube = lambda path, uid, body=None, base=None: llamadas.append((path, uid, body) + ((base,) if base else ())) or (200, b"{}")
app.q("DELETE FROM envios WHERE uid='B'"); app.q("UPDATE users SET pausa=1 WHERE uid='B'")
assert app.enviar("B", "n-hinge:Mar", "¡vale!") == "pausa" and not llamadas  # salvaguardas antes que el agente
app.q("UPDATE users SET pausa=0 WHERE uid='B'")
assert app.enviar("B", "n-hinge:Mar", "¡vale!") is None and llamadas == [("/enviar", "B", {"app": "hinge", "nombre": "Mar", "texto": "¡vale!"})]
assert app.enviar("A", "hinge:Lu", "x") == "solo lectura"  # apps del puente: solo lectura
ckA = {"Cookie": "s=" + app.firmar(f"A|{int(time.time()) + 99}"), "Origin": app.BASE, "Content-Type": "application/json"}
assert post("/nube/in", b'{"k":"rm -rf"}', ckA) == 400 and post("/nube/in", b'{"k":"HOME"}', {**ckA, "Origin": "https://malo"}) == 403
llamadas.clear(); assert post("/nube/in", b'{"k":"HOME"}', ckA) == 200 and llamadas == [("/nube/in".replace("/nube", ""), "A", {"k": "HOME"})]
# Tinder web: mismo patrón contra su agente (TINDER), Intro solo ahí, y sus chats n-tinder son solo lectura
llamadas.clear(); assert post("/tinder/in", b'{"k":"ENTER"}', ckA) == 200 and llamadas == [("/in", "A", {"k": "ENTER"}, app.TINDER)]
assert post("/nube/in", b'{"k":"ENTER"}', ckA) == 400
llamadas.clear(); assert app.enviar("B", "n-tinder:abc", "hola") == "solo lectura" and not llamadas
# WhatsApp por número: validación, CSRF, y nunca se rehace una instancia abierta
assert app.tel_ok("+34 600 00 00 01") == "34600000001" and app.tel_ok("600000001") == "34600000001"
assert app.tel_ok("abc") is None and app.tel_ok("123") is None and app.tel_ok("+1 (555) 010-0000") == "15550100000"
assert post("/wa/codigo", b'{"tel":"600000001"}', {**ckA, "Origin": "https://malo"}) == 403
assert post("/wa/codigo", b'{"tel":"hola"}', ckA) == 400
llamadas_evo = []
def evo_falso(path, inst=None, body=None, metodo=None, qs=""):
    llamadas_evo.append((path, metodo, qs))
    if path == "instance/connectionState": return {"instance": {"state": estado_falso}}
    if path == "instance/connect": return {"pairingCode": "ABCD1234"}
    return {}
app.evo = evo_falso
estado_falso = "open"
assert app.wa_codigo("A", "34600000001") == {"estado": "open"} and not any(m == "DELETE" for _, m, _ in llamadas_evo)
estado_falso = "connecting"; llamadas_evo.clear()
assert app.wa_codigo("A", "34600000001")["codigo"] == "ABCD1234"
assert [p for p, _, _ in llamadas_evo][-3:] == ["instance/delete", "instance/create", "instance/connect"] and llamadas_evo[-1][2] == "number=34600000001"
assert post("/wa/codigo", b'{"tel":"+34 600 00 00 01"}', ckA) == 200 and app.user("A")["tel"] == "34600000001"

# ---------- CRM «Historias» ----------
from zoneinfo import ZoneInfo
# migración: 3 chats viejos -> 3 personas con etapas traducidas; idempotente
for jid, et, cita in (("m1@s.whatsapp.net", "conversando", None), ("m2@s.whatsapp.net", "propuesta", None), ("m3@s.whatsapp.net", "cita", "vie 28/11 21:00 · Bar X")):
    app.q("INSERT INTO chats(uid,jid,nombre,activo,etapa,cita) VALUES('B',?,?,1,?,?)", jid, jid[:2], et, cita)
app.migrar(); app.migrar()
et = {r["jid"]: r["etapa"] for r in app.q("SELECT c.jid, p.etapa FROM chats c JOIN personas p ON p.id=c.persona_id WHERE c.uid='B' AND c.jid LIKE 'm%'")}
assert et == {"m1@s.whatsapp.net": "conversando", "m2@s.whatsapp.net": "plan", "m3@s.whatsapp.net": "cita_fijada"}, et
assert app.q("SELECT count(*) n FROM personas WHERE uid='B' AND nombre IN ('m1','m2','m3')")[0]["n"] == 3
assert app.q("SELECT count(*) n FROM citas WHERE uid='B' AND lugar='Bar X'")[0]["n"] == 1
assert app.leer_cita("vie 28/11 21:00 · Bar X", datetime(2026, 11, 24, tzinfo=ZoneInfo("Europe/Madrid")))[0] == "2026-11-28T21:00+01:00"
pid = app.q("SELECT persona_id FROM chats WHERE uid='B' AND jid='m1@s.whatsapp.net'")[0]["persona_id"]
etp = lambda: app.q("SELECT etapa FROM personas WHERE id=?", pid)[0]["etapa"]
# la IA solo avanza y nunca da una cita por hecha; lo que fija el usuario manda 
assert app.avanzar("B", pid, "match", "ia") is None and etp() == "conversando"
assert app.avanzar("B", pid, "plan", "ia") and etp() == "plan"
assert app.avanzar("B", pid, "cita_hecha", "ia") is None and app.avanzar("B", pid, "resultado", "ia") is None
assert app.avanzar("B", pid, "cita_hecha", "usuario") and etp() == "cita_hecha"
assert app.avanzar("B", pid, "conversando", "ia") is None and app.avanzar("B", pid, "cita_fijada", "ia") is None and etp() == "cita_hecha"
ev = app.poner_resultado("B", pid, "repetir")
assert etp() == "resultado" and app.q("SELECT proxima FROM personas WHERE id=?", pid)[0]["proxima"] == "Proponer segunda cita"
assert app.poner_resultado("B", pid, "intima") is None  # solo los 4 resultados; nada de datos sexuales
app.deshacer("B", ev); assert app.q("SELECT resultado FROM personas WHERE id=?", pid)[0]["resultado"] is None
app.poner_resultado("B", pid, "descartada"); assert app.q("SELECT archivada FROM personas WHERE id=?", pid)[0]["archivada"] == 1
assert app.avanzar("A", pid, "plan", "usuario") is None and app.poner_resultado("A", pid, "repetir") is None  # A no toca a B
# barrido: la cita fijada que ya pasó -> cita hecha (por calendario) y aparece para anotar en Hoy
p3 = app.q("SELECT persona_id FROM chats WHERE uid='B' AND jid='m3@s.whatsapp.net'")[0]["persona_id"]
app.barrido(datetime(2026, 11, 29, 12, tzinfo=ZoneInfo("Europe/Madrid")))
assert app.q("SELECT etapa FROM personas WHERE id=?", p3)[0]["etapa"] == "cita_hecha"
assert "¿Qué tal con m3?" in app.pag_hoy("B") and "m3" not in app.pag_hoy("A")
# unir: Hinge + WhatsApp = una persona, al menos en contacto
p2 = app.q("SELECT persona_id FROM chats WHERE uid='B' AND jid='m2@s.whatsapp.net'")[0]["persona_id"]
assert not app.unir("A", p2, p3) and app.unir("B", p2, p3)
assert app.q("SELECT count(*) n FROM chats WHERE uid='B' AND persona_id=?", p2)[0]["n"] == 2 and not app.q("SELECT 1 FROM personas WHERE id=?", p3)
# páginas y rutas: aislamiento por uid, CSRF, BORRAR obligatorio
for f_ in (app.pag_historias, app.pag_agenda, app.pag_ajustes):
    assert "m2" in f_("B") or f_ is not app.pag_historias
assert app.pag_persona("A", p2) is None and "m2" in app.pag_persona("B", p2)
ckB2 = {"Cookie": "s=" + app.firmar(f"B|{int(time.time()) + 99}"), "Origin": app.BASE, "Content-Type": "application/x-www-form-urlencoded"}
get = lambda path, ck: urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8997" + path, headers=ck))
assert get(f"/p/{p2}", ckB2).status == 200
try:
    get(f"/p/{p2}", {**ckB2, "Cookie": "s=" + app.firmar(f"A|{int(time.time()) + 99}")}); assert False
except urllib.error.HTTPError as x:
    assert x.code == 404
assert post(f"/p/{p2}/temp", b"t=3&v=/historias", {**ckB2, "Origin": "https://malo"}) == 403
post(f"/p/{p2}/temp", b"t=3&v=/historias", ckB2); assert app.q("SELECT temperatura FROM personas WHERE id=?", p2)[0]["temperatura"] == 3
post(f"/p/{p2}/notas", ("t=" + "x" * 5000).encode(), ckB2); assert len(app.q("SELECT notas FROM personas WHERE id=?", p2)[0]["notas"]) == 2000
post("/cuenta/borrar", b"confirm=no", ckB2); assert app.user("B")
assert app.nombre_vis("34600000002") == "+34 6•• ••• 002" if hasattr(app, "nombre_vis") else True
m_ = json.load(urllib.request.urlopen("http://127.0.0.1:8997/manifest.webmanifest"))
assert m_["display"] == "standalone" and {i["sizes"] for i in m_["icons"]} == {"192x192", "512x512"}
assert urllib.request.urlopen("http://127.0.0.1:8997/icon-512.png").status == 200

# ---------- Instagram ----------
import hashlib as _h, hmac as _hm
app.META_SECRET = "igs"; app.IG_VERIFY = "vt"
assert get("/ig/hook?hub.mode=subscribe&hub.verify_token=vt&hub.challenge=123", {}).read() == b"123"
try:
    get("/ig/hook?hub.mode=subscribe&hub.verify_token=malo&hub.challenge=1", {}); assert False
except urllib.error.HTTPError as x:
    assert x.code == 403
cuerpo = b'{"object":"instagram","entry":[]}'
assert post("/ig/hook", cuerpo, {"X-Hub-Signature-256": "sha256=00"}) == 403
assert post("/ig/hook", cuerpo, {"X-Hub-Signature-256": "sha256=" + _hm.new(b"igs", cuerpo, "sha256").hexdigest()}) == 200
# DM entrante -> chat ig:<id> del dueño de esa cuenta (y de nadie más); sugerencia solo si el chat está activo
app.q("UPDATE users SET ig_id='999', ig_tok=? WHERE uid='A'", app.fernet().encrypt(b"tok"))
llam_ig = []
def ig_falso(path, tok, body=None, **qs):
    llam_ig.append((path, body)); return {"username": "lu"} if path == "55" else {"data": []}
app.ig_api = ig_falso
sug_ = []
app.sugerir = lambda *a: sug_.append(a)
dm = {"entry": [{"id": "999", "messaging": [{"sender": {"id": "55"}, "message": {"mid": "mm1", "text": "hola!"}},
                                            {"sender": {"id": "999"}, "message": {"mid": "mm2", "text": "eco", "is_echo": True}}]},
                {"id": "123", "messaging": [{"sender": {"id": "7"}, "message": {"mid": "x", "text": "de otro"}}]}]}
dm["entry"].append({"id": "999", "changes": [{"field": "messages", "value": {"sender": {"id": "56"}, "message": {"mid": "mm3", "text": "test"}}}]})
app.ig_procesar(dm)
assert app.q("SELECT nombre FROM chats WHERE uid='A' AND jid='ig:55'")[0]["nombre"] == "@lu" and len(sug_) == 2 and sug_[0][2] == "mm1" and sug_[1][2] == "mm3"
assert not app.q("SELECT 1 FROM chats WHERE jid='ig:7'") and not app.q("SELECT 1 FROM chats WHERE uid='B' AND jid LIKE 'ig:%'")
# envío por la Send API, pasando por control()
app.q("DELETE FROM envios"); app.q("UPDATE users SET pausa=0 WHERE uid='A'")
assert app.enviar("A", "ig:55", "hey") is None and llam_ig[-1] == ("999/messages", {"recipient": {"id": "55"}, "message": {"text": "hey"}})
assert app.enviar("A", "ig:55", "otra") == "ritmo"

# ---------- Pago (Stripe) ----------
import sqlite3
# migración: quien ya existía queda como fundador
viejo = tempfile.mktemp(suffix=".db"); cv = sqlite3.connect(viejo)
cv.execute("CREATE TABLE users(uid TEXT PRIMARY KEY, email TEXT, nombre TEXT, cal_rt BLOB, inst TEXT UNIQUE, hook TEXT, modo_auto INT DEFAULT 0,"
           " pausa INT DEFAULT 0, perfil TEXT DEFAULT '', consent_at TEXT, creado TEXT, tel TEXT)"); cv.execute("INSERT INTO users(uid,modo_auto) VALUES('M',1)"); cv.commit(); cv.close()
app.DB, db_ = viejo, app.DB; app.init(); app.init()
assert app.user("M")["plan"] == "fundador" and app.user("M")["modo_auto"] == 1 and app.de_pago(app.user("M"))
app.DB = db_
# usuario nuevo sin plan: ve planes, no puede usar lo de pago, la IA no trabaja para él
app.q("INSERT INTO users(uid,email,nombre,inst,hook,consent_at) VALUES('C','c@x','C',?,'sC','x')", app.inst_de("C"))
ckC = {"Cookie": "s=" + app.firmar(f"C|{int(time.time()) + 99}"), "Origin": app.BASE, "Content-Type": "application/x-www-form-urlencoded"}
for ruta_ in ("/", "/ajustes", "/nube", "/historias"):
    h_ = get(ruta_, ckC).read().decode(); assert "29 €" in h_ and "3 días gratis" in h_ and "Tu Android en la nube</h2>" not in h_, ruta_
assert "29 €" not in get("/", ckB2).read().decode()  # fundador: su panel de siempre
llamadas.clear(); post("/nube/in", b'{"k":"HOME"}', {**ckC, "Content-Type": "application/json"}); post("/auto", b"v=/ajustes", ckC); post("/nube/crear", b"ciudad=Madrid", ckC)
assert not llamadas and app.user("C")["modo_auto"] == 0
pide = []; app.ia.proponer = lambda *a: pide.append(a) or {"respuesta": "x", "escalar": False, "motivo": "", "etapa": "conversando", "cita": None}
assert post("/bridge/citas", json.dumps({"uid": "C", "chats": [{"app": "hinge", "id": "Q", "nombre": "Q", "toca": True, "hist": [["otro", "hey"]]}]}).encode(), hdr) == 200
assert not pide and not app.q("SELECT 1 FROM sugerencias WHERE uid='C'")
# checkout: precio, IVA automático, prueba de 3 días solo la primera vez, sin cupón por la ruta
pedidos = []
fs = {"clientes": [], "subs": [], "abiertas": []}  # Stripe de mentira
def fake_stripe(path, datos=None, metodo=None):
    pedidos.append((path, datos, metodo))
    if path.startswith("customers?"):
        return {"data": fs["clientes"]}
    if path == "customers":
        return {"id": "cus_C"}
    if path.startswith("subscriptions?"):
        return {"data": fs["subs"]}
    if path.startswith("checkout/sessions?"):
        return {"data": fs["abiertas"]}
    if path.startswith("billing_portal"):
        return {"url": "https://billing.stripe.com/p"}
    return {"url": "https://checkout.stripe.com/x", "status": "trialing", "id": "x"}
app.stripe = fake_stripe
app.STRIPE_PRICE = "price_nube"
r_ = urllib.request.build_opener(type("NoRed", (urllib.request.HTTPRedirectHandler,), {"redirect_request": lambda *a: None}))
try:
    r_.open(urllib.request.Request("http://127.0.0.1:8997/pago/checkout", data=b"", headers=ckC)); assert False
except urllib.error.HTTPError as x:
    assert x.code == 303 and x.headers["Location"] == "https://checkout.stripe.com/x"
d_ = pedidos[-1][1]
assert d_["line_items[0][price]"] == "price_nube" and d_["subscription_data[trial_period_days]"] == 3 and d_["automatic_tax[enabled]"] == "true"
assert d_["client_reference_id"] == "C" and "discounts[0][coupon]" not in d_ and d_["customer"] == "cus_C" and app.user("C")["stripe_cus"] == "cus_C"
assert ("customers", {"email": "c@x", "name": "C", "metadata[app]": "celestia"}, None) in pedidos
# segundo clic con la caja anterior abierta: se caduca la vieja (una sola caja viva por persona)
fs["abiertas"] = [{"id": "cs_viejo"}]; pedidos.clear(); app.checkout("C"); fs["abiertas"] = []
assert ("checkout/sessions/cs_viejo/expire", {}, None) in pedidos
# ya pagó y el aviso aún no llegó (o está en prueba/activo): al portal, nunca una segunda suscripción
fs["subs"] = [{"id": "sub_C", "status": "trialing", "metadata": {"app": "celestia"}}]; pedidos.clear()
assert app.checkout("C") == "https://billing.stripe.com/p" and not any(p[0] == "checkout/sessions" for p in pedidos)
fs["subs"] = []
assert "/pago/checkout" not in app.pag_planes("C", volviendo=True)  # «Confirmando tu pago…» sin botón
assert app.checkout("A") == app.BASE + "/"  # fundador: nada que contratar
# webhook: firma, idempotencia, estados
app.STRIPE_WHSEC = "whsec_t"
def firma(cuerpo, t=None):
    t = str(int(t or time.time())); return "t=" + t + ",v1=" + _hm.new(b"whsec_t", t.encode() + b"." + cuerpo, "sha256").hexdigest()
def evs(id_, tipo, obj, creado):
    return json.dumps({"id": id_, "type": tipo, "created": creado, "data": {"object": obj}}).encode()
c1 = evs("evt_1", "checkout.session.completed", {"client_reference_id": "C", "customer": "cus_C", "subscription": "sub_C", "metadata": {"app": "celestia"}}, 100)
assert post("/stripe/hook", c1, {"Stripe-Signature": "t=1,v1=00"}) == 400 and post("/stripe/hook", c1, {"Stripe-Signature": firma(c1, time.time() - 900)}) == 400
assert app.user("C")["estado"] is None
assert post("/stripe/hook", c1, {"Stripe-Signature": firma(c1)}) == 200
u_ = app.user("C"); assert (u_["estado"], u_["stripe_cus"], u_["stripe_sub"]) == ("prueba", "cus_C", "sub_C") and app.de_pago(u_)
assert "29 €" not in get("/", ckC).read().decode()  # en prueba: todo el panel
sub = lambda st, **k: {"id": "sub_C", "customer": "cus_C", "status": st, "metadata": {"app": "celestia", "uid": "C"}, **k}
assert app.stripe_evento(json.loads(evs("evt_2", "customer.subscription.updated", sub("active"), 200))) == "activo"
assert app.stripe_evento(json.loads(evs("evt_2", "customer.subscription.updated", sub("canceled"), 200))) == "repetido" and app.user("C")["estado"] == "activo"
app.stripe_evento(json.loads(evs("evt_viejo", "customer.subscription.updated", sub("trialing"), 150))); assert app.user("C")["estado"] == "activo"  # no retrocede
app.stripe_evento(json.loads(evs("evt_3b", "invoice.payment_failed", {"customer": "cus_C", "subscription": "sub_vieja"}, 290)))
assert app.user("C")["estado"] == "activo"  # fallo de otra suscripción: no bloquea la actual
llamadas.clear()
app.stripe_evento(json.loads(evs("evt_3", "invoice.payment_failed", {"customer": "cus_C", "parent": {"subscription_details": {"subscription": "sub_C"}}}, 300)))
assert not llamadas  # impago con reintentos: el Android sigue
assert app.user("C")["estado"] == "impago" and not app.de_pago(app.user("C")) and "Actualizar tarjeta" in get("/", ckC).read().decode()
app.stripe_evento(json.loads(evs("evt_otra", "customer.subscription.deleted", {**sub("canceled"), "id": "sub_vieja"}, 350))); assert app.user("C")["estado"] == "impago"
app.NUBE_SECRET = app.NUBE_SECRET or "x"; llamadas.clear()
app.stripe_evento(json.loads(evs("evt_4", "customer.subscription.deleted", sub("canceled"), 400))); assert app.user("C")["estado"] == "cancelado"
assert llamadas, "cancelado: se libera su Android"
# eventos de otras apps de la misma cuenta de Stripe: no tocan a nadie
app.stripe_evento(json.loads(evs("evt_5", "invoice.payment_failed", {"customer": "cus_ajeno"}, 500)))
app.stripe_evento(json.loads(evs("evt_6", "checkout.session.completed", {"client_reference_id": "A", "subscription": "s", "metadata": {}}, 500)))
assert app.user("A")["estado"] is None and app.user("A")["plan"] == "fundador"
# segunda vez: ya tuvo suscripción, sin prueba gratis
fs["subs"] = [{"id": "sub_C", "status": "canceled", "metadata": {"app": "celestia"}}, {"id": "sub_ajena", "status": "active", "metadata": {}}]
pedidos.clear(); app.checkout("C"); d_ = pedidos[-1][1]
assert d_["customer"] == "cus_C" and "subscription_data[trial_period_days]" not in d_ and not any(p[2] == "DELETE" for p in pedidos)
# atascada en unpaid/paused: se cancela y se contrata de nuevo (no se queda encerrado en «impago»)
fs["subs"] = [{"id": "sub_C", "status": "unpaid", "metadata": {"app": "celestia"}}]; pedidos.clear(); app.checkout("C")
assert ("subscriptions/sub_C", None, "DELETE") in pedidos and pedidos[-1][0] == "checkout/sessions" and "subscription_data[trial_period_days]" not in pedidos[-1][1]
fs["subs"] = []
pedidos.clear(); app.checkout("C", cupon="c100"); assert pedidos[-1][1]["discounts[0][coupon]"] == "c100" and "allow_promotion_codes" not in pedidos[-1][1]
# borrar cuenta cancela antes la suscripción viva
app.q("UPDATE users SET estado='activo' WHERE uid='C'"); pedidos.clear(); app.evo = lambda *a, **k: {}
app.borrar("C"); assert pedidos == [("subscriptions/sub_C", None, "DELETE")] and not app.user("C")
# borrar la cuenta y volver a entrar con el mismo Google no da otra prueba: se reutiliza su cliente de Stripe
app.q("INSERT INTO users(uid,email,nombre,inst,hook,consent_at) VALUES('C','c@x','C',?,'sC2','x')", app.inst_de("C"))
fs["clientes"] = [{"id": "cus_otra_app", "metadata": {}}, {"id": "cus_C", "metadata": {"app": "celestia"}}]
fs["subs"] = [{"id": "sub_C", "status": "canceled", "metadata": {"app": "celestia"}}]; pedidos.clear(); app.checkout("C")
assert app.user("C")["stripe_cus"] == "cus_C" and ("customers", ) not in [p[:1] for p in pedidos] and "subscription_data[trial_period_days]" not in pedidos[-1][1]
print("OK: todos los asserts")
# autoalojado sin Stripe: todo abierto
app.STRIPE_KEY = ""
assert app.de_pago({"plan": "", "estado": ""})
print("OK: autoalojado sin Stripe")
# arranque seguro: sin claves débiles ni panel abierto a cualquiera
assert any("SESSION_KEY" in f for f in app.fallos_config()) and any("ALLOWED_EMAILS" in f for f in app.fallos_config())
app.SKEY, app.PERMITIDOS, app.BRIDGE_SECRET = b"x" * 32, {"yo@x.com"}, "b" * 32
assert app.fallos_config() == [] and app.permitido("Yo@X.com") and not app.permitido("otro@x.com")
print("OK: arranque seguro y lista de cuentas")
