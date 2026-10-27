#!/usr/bin/env python3
"""Último código SMS de Tinder/Hinge/Bumble (ejecuciones del workflow n8n que recibe el SMS Forwarder). SOLO logins.
usage: sms_codigo.py [minutos=15]   -> imprime solo SMS cuyo remitente/texto mencione tinder|hinge|bumble.
Nunca imprime otros SMS. Necesita N8N_API_URL, N8N_API_KEY y N8N_SMS_WORKFLOW_ID (config.env)."""
import json, os, re, sys, time, urllib.request
from datetime import datetime, timezone

WF = os.environ["N8N_SMS_WORKFLOW_ID"]
APPS = re.compile(r"tinder|hinge|bumble", re.I)
BASE = os.environ["N8N_API_URL"].rstrip("/")
if not BASE.endswith("/api/v1"):
    BASE += "/api/v1"
HDR = {"X-N8N-API-KEY": os.environ["N8N_API_KEY"], "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/130"}


def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(BASE + path, headers=HDR), timeout=20))


def body_of(ex):
    for runs in ex.get("data", {}).get("resultData", {}).get("runData", {}).values():
        for r in runs:
            for item in (r.get("data", {}).get("main") or [[]])[0] or []:
                b = item.get("json", {}).get("body")
                if isinstance(b, dict) and "text" in b:
                    return b
    return None


def main(minutes=15):
    since = time.time() - minutes * 60
    found = 0
    for e in get(f"/executions?workflowId={WF}&limit=20")["data"]:
        t = datetime.fromisoformat(e["startedAt"].replace("Z", "+00:00")).timestamp()
        if t < since:
            continue
        b = body_of(get(f"/executions/{e['id']}?includeData=true"))
        if b and APPS.search(f"{b.get('from', '')} {b.get('text', '')}"):
            found += 1
            print(datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds"), b.get("from"), "|", b.get("text"))
    if not found:
        print(f"sin codigos de Tinder/Hinge/Bumble en los ultimos {minutes} min")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 15)
