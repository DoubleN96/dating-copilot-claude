#!/usr/bin/env python3
"""WhatsApp del dueño (Evolution API) SOLO para los contactos traspasados desde las apps.
  whatsapp.py nuevos [HORAS]             -> chats nuevos de números no guardados (posibles matches que escriben)
  whatsapp.py alta NUMERO "Nombre (app)" -> da de alta un contacto; sin alta no se lee ni se escribe
  whatsapp.py chats                      -> los dados de alta y si su último mensaje está sin contestar
  whatsapp.py leer NUMERO [N]            -> últimos N mensajes (YO = enviado por el copiloto, DUEÑO = escrito por él a mano)
  whatsapp.py enviar NUMERO TEXTO        -> envía (respeta envio.py: PAUSA, MIN_SECONDS, MAX_PER_DAY, registro)
El resto de su WhatsApp (amigos, familia, grupos, trabajo) NO se toca.
Config (config.env): EVOLUTION_URL, EVOLUTION_INSTANCE, EVOLUTION_API_KEY, WA_DEFAULT_PREFIX (34), WA_LOCAL_DIGITS (9)."""
import json, os, re, sys, time, urllib.request
import envio

E = os.environ
URL, INST, KEY = E.get("EVOLUTION_URL", "").rstrip("/"), E.get("EVOLUTION_INSTANCE", ""), E.get("EVOLUTION_API_KEY", "")
PREFIJO, LOCAL = E.get("WA_DEFAULT_PREFIX", "34"), int(E.get("WA_LOCAL_DIGITS", 9))
REG = f"{envio.BASE}/estado/whatsapp_contactos.json"


def api(path, body):
    if not (URL and INST and KEY):
        sys.exit("Falta EVOLUTION_URL / EVOLUTION_INSTANCE / EVOLUTION_API_KEY en config.env")
    req = urllib.request.Request(f"{URL}/{path}/{INST}", data=json.dumps(body).encode(),
                                 headers={"apikey": KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def registro():
    try:
        return json.load(open(REG))
    except FileNotFoundError:
        return {}


def jid(numero):
    """'6XX XX XX XX' / '+34 6XX…' / jid completo -> jid. Con LOCAL dígitos o menos se antepone WA_DEFAULT_PREFIX."""
    if "@" in numero:
        return numero
    n = re.sub(r"\D", "", numero)
    return f"{PREFIJO + n if len(n) <= LOCAL else n}@s.whatsapp.net"


def mensajes(j, n=20):
    return api("chat/findMessages", {"where": {"key": {"remoteJid": j}}, "limit": n})["messages"]


def texto(m):
    msg = m.get("message") or {}
    return msg.get("conversation") or (msg.get("extendedTextMessage") or {}).get("text") or f"[{m.get('messageType')}]"


def enviados_por_copiloto():
    try:
        return {x["texto"] for x in map(json.loads, open(envio.LOG)) if x.get("app") == "whatsapp"}
    except FileNotFoundError:
        return set()


def de_alta(numero):
    j = jid(numero)
    if j not in registro():
        sys.exit(f"{j} no está dado de alta: usa `alta` solo si es un contacto traspasado desde las apps")
    return j


def main(a):
    cmd = a[0] if a else ""
    if cmd == "nuevos":
        desde, reg = time.time() - 3600 * float(a[1] if len(a) > 1 else 48), registro()
        for c in api("chat/findChats", {"where": {}}):
            j, ult = c.get("remoteJid", ""), int((c.get("lastMessage") or {}).get("messageTimestamp") or 0)
            if j.endswith("@g.us") or j.endswith("@broadcast") or j in reg or c.get("isSaved") or ult < desde:
                continue
            hist = mensajes(j, 50)["records"]
            primero = min(hist, key=lambda x: int(x["messageTimestamp"]), default=None)
            if primero and int(primero["messageTimestamp"]) >= desde:  # ponytail: "nuevo" = sin historial anterior
                print(j, "|", c.get("pushName", ""), "|", texto(primero)[:120])
    elif cmd == "alta" and len(a) > 2:
        reg = registro()
        reg[jid(a[1])] = {"nombre": " ".join(a[2:]), "alta": time.strftime("%Y-%m-%dT%H:%M")}
        os.makedirs(os.path.dirname(REG), exist_ok=True)
        json.dump(reg, open(REG, "w"), ensure_ascii=False, indent=1)
        print("alta", jid(a[1]))
    elif cmd == "chats":
        for j, d in registro().items():
            r = mensajes(j, 1)["records"]
            pend = "SIN CONTESTAR" if r and not r[0]["key"].get("fromMe") else "ok"
            print(j, "|", d["nombre"], "|", pend, "|", texto(r[0])[:80] if r else "(sin mensajes)")
    elif cmd == "leer" and len(a) > 1:
        r, mios = mensajes(de_alta(a[1]), int(a[2]) if len(a) > 2 else 20)["records"], enviados_por_copiloto()
        for m in reversed(r):
            quien = ("YO" if texto(m) in mios else "DUEÑO") if m["key"].get("fromMe") else "ELLA"
            print(time.strftime("%d/%m %H:%M", time.localtime(int(m["messageTimestamp"]))), quien, ":", texto(m))
    elif cmd == "enviar" and len(a) > 2:
        j, t = de_alta(a[1]), " ".join(a[2:])
        envio.control()
        r = api("message/sendText", {"number": j, "text": t})
        envio.registrar("whatsapp", registro()[j]["nombre"], t)
        print("enviado", r.get("key", {}).get("id"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
