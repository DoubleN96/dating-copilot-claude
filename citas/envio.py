#!/usr/bin/env python3
"""Salvaguardas de envío del copiloto (modo autónomo).
  envio.py estado            -> pausa sí/no, enviados hoy / límite
  envio.py resumen           -> manda al dueño (OWNER_CHAT_ID) por Telegram el resumen de envíos de hoy (cron diario)
  envio.py avisar "texto"    -> manda ese texto al dueño por Telegram
Límites: PAUSA (fichero citas/PAUSA) bloquea todo; máx 1 envío cada MIN_SECONDS (45) y MAX_PER_DAY (40) al día. Registro en estado/enviados.jsonl."""
import json, os, sys, time, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
PAUSA, LOG = f"{BASE}/PAUSA", f"{BASE}/estado/enviados.jsonl"
E = os.environ
MIN_SEG, MAX_DIA, TZ = int(E.get("MIN_SECONDS", 45)), int(E.get("MAX_PER_DAY", 40)), ZoneInfo(E.get("TZ_NAME", "Europe/Madrid"))
OWNER = E.get("OWNER_CHAT_ID", "")  # tu chat_id de Telegram (config.env)
ENV = os.path.expanduser("~/.claude/channels/telegram/.env")  # token del bot que guarda el plugin telegram


def _hoy():
    d = datetime.now(TZ).date().isoformat()
    try:
        return [x for x in map(json.loads, open(LOG)) if x["fecha"].startswith(d)]
    except FileNotFoundError:
        return []


def control():
    """Antes de enviar: sale si hay PAUSA o se pasó el tope diario; espera si el último envío fue hace <45 s."""
    if os.path.exists(PAUSA):
        sys.exit("PAUSA: el dueño ha pausado los envíos (dirá «sigue» para reanudar)")
    hoy = _hoy()
    if len(hoy) >= MAX_DIA:
        sys.exit(f"LIMITE: ya van {len(hoy)} mensajes hoy (máx {MAX_DIA})")
    if hoy:
        falta = MIN_SEG - (time.time() - datetime.fromisoformat(hoy[-1]["fecha"]).timestamp())
        if falta > 0:
            time.sleep(falta)


def registrar(app, match, texto):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps({"fecha": datetime.now(TZ).isoformat(timespec="seconds"), "app": app,
                            "match": match, "texto": texto}, ensure_ascii=False) + "\n")


def avisar(texto):
    tok = next(l.split("=", 1)[1].strip().strip("\"'") for l in open(ENV) if l.startswith("TELEGRAM_BOT_TOKEN="))
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"chat_id": OWNER, "text": texto[:4000]}).encode())
    return json.load(urllib.request.urlopen(req, timeout=15)).get("ok")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "estado"
    hoy = _hoy()
    if cmd == "estado":
        print(f"pausa={'SI' if os.path.exists(PAUSA) else 'no'} enviados_hoy={len(hoy)}/{MAX_DIA}")
    elif cmd == "resumen":
        lineas = [f"{x['fecha'][11:16]} {x['app']} · {x['match']}: {x['texto'][:80]}" for x in hoy]
        print(avisar(f"📋 Copiloto hoy: {len(hoy)} mensajes enviados" + ("\n" + "\n".join(lineas) if lineas else "")))
    elif cmd == "avisar":
        print(avisar(" ".join(sys.argv[2:])))
    else:
        sys.exit(__doc__)
