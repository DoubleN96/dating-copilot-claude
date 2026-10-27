#!/usr/bin/env python3
"""Google Calendar del dueño para el copiloto (credenciales OAuth en $GOOGLE_CALENDAR_CREDS).
  cal.py huecos [semanas=2]                     -> huecos libres de citas (CALENDAR_SLOTS, p. ej. mié y jue 18:00-24:00)
  cal.py crear "Título" INICIO FIN ["lugar"] ["notas"]  -> crea evento (ISO local, p.ej. 2026-10-28T20:00)
  cal.py proximas [n=10]                        -> próximos eventos"""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
TZN = os.environ.get("TZ_NAME", "Europe/Madrid"); TZ = ZoneInfo(TZN)
# CALENDAR_SLOTS="2:18-24,3:18-24" -> weekday (0=lunes) : hora inicio-fin
HUECOS = {int(d): tuple(map(int, h.split("-"))) for d, h in (x.split(":") for x in os.environ.get("CALENDAR_SLOTS", "2:18-24,3:18-24").split(","))}
C = json.load(open(os.path.expanduser(os.environ.get("GOOGLE_CALENDAR_CREDS", "~/.secrets/google_calendar.json"))))  # {client_id, client_secret, refresh_token}

def token():
    d = urllib.parse.urlencode({"client_id": C["client_id"], "client_secret": C["client_secret"],
                                "refresh_token": C["refresh_token"], "grant_type": "refresh_token"}).encode()
    return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", d, timeout=20))["access_token"]

def api(path, body=None):
    r = urllib.request.Request("https://www.googleapis.com/calendar/v3" + path, data=json.dumps(body).encode() if body else None,
                               headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=20))

def huecos(semanas=2):
    hoy = datetime.now(TZ).replace(minute=0, second=0, microsecond=0)
    franjas = []
    for d in range(semanas * 7):
        dia = (hoy + timedelta(days=d)).date()
        if dia.weekday() in HUECOS:
            a, b = HUECOS[dia.weekday()]
            ini = datetime(dia.year, dia.month, dia.day, a, tzinfo=TZ)
            fin = datetime(dia.year, dia.month, dia.day, tzinfo=TZ) + timedelta(hours=b)
            if fin > hoy: franjas.append((max(ini, hoy), fin))
    if not franjas: return []
    fb = api("/freeBusy", {"timeMin": franjas[0][0].isoformat(), "timeMax": franjas[-1][1].isoformat(), "items": [{"id": "primary"}]})
    ocupado = [(datetime.fromisoformat(x["start"].replace("Z", "+00:00")).astimezone(TZ), datetime.fromisoformat(x["end"].replace("Z", "+00:00")).astimezone(TZ)) for x in fb["calendars"]["primary"]["busy"]]
    libres = []
    for ini, fin in franjas:
        t = ini
        for o1, o2 in sorted(ocupado):
            if o2 <= t or o1 >= fin: continue
            if o1 > t: libres.append((t, o1))
            t = max(t, o2)
        if t < fin: libres.append((t, fin))
    return [(a.strftime("%a %d/%m %H:%M"), b.strftime("%H:%M")) for a, b in libres if (b - a) >= timedelta(hours=2)]

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "huecos"
    if cmd == "huecos":
        for a, b in huecos(int(sys.argv[2]) if len(sys.argv) > 2 else 2): print(f"{a} - {b}")
    elif cmd == "proximas":
        n = sys.argv[2] if len(sys.argv) > 2 else "10"
        for e in api(f"/calendars/primary/events?maxResults={n}&singleEvents=true&orderBy=startTime&timeMin={urllib.parse.quote(datetime.now(TZ).isoformat())}").get("items", []):
            print(e["start"].get("dateTime", e["start"].get("date")), "|", e.get("summary", ""))
    elif cmd == "crear":
        t, ini, fin = sys.argv[2:5]
        ev = {"summary": t, "start": {"dateTime": ini, "timeZone": TZN}, "end": {"dateTime": fin, "timeZone": TZN}}
        if len(sys.argv) > 5: ev["location"] = sys.argv[5]
        if len(sys.argv) > 6: ev["description"] = sys.argv[6]
        link = api("/calendars/primary/events", ev).get("htmlLink")
        print(link)
        try:  # aviso automático al dueño cada vez que se agenda una cita
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import envio
            envio.avisar(f"📅 Cita agendada: {t}\n🕗 {ini} → {fin[-5:]}\n📍 {ev.get('location', '')}\n\n{ev.get('description', '')}\n{link}")
        except Exception as e:
            print("aviso Telegram falló:", type(e).__name__)
    else:
        sys.exit(__doc__)
