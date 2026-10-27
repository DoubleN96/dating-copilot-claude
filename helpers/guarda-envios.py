#!/usr/bin/env python3
"""PreToolUse(Bash) del copiloto (modo autónomo): los envíos salen solo por tinder.py /
hinge.py / bumble.py / whatsapp.py, que aplican PAUSA, 45 s entre mensajes, 40/día y registro. Aquí solo se bloquean
los atajos que se saltan esas salvaguardas: API de Tinder fuera de tinder.py, API de Evolution (WhatsApp) fuera de whatsapp.py y tocar ficheros de estado.
ponytail: regex contra deriva/inyeccion, no contra un agente decidido con el mismo uid."""
import json, re, sys

REGLAS = [
    (r"(>|\btee\b|\brm\b|\bmv\b|\bcp\b|truncate|sed\s+-i)[^|;&\n]*(enviados\.jsonl|aprobacion_citas|whatsapp_contactos)",
     "el registro de envíos solo lo escriben los scripts de envío"),
    (r"\b(rm|mv)\b[^|;&\n]*citas/PAUSA", "la PAUSA solo la quita el dueño diciendo «sigue»"),
    (r"gotinder\.com|/user/matches/", "a la API de Tinder solo se entra con tinder.py"),
    (r"EVOLUTION_URL|EVOLUTION_API_KEY|/message/sendText|/chat/find(Messages|Chats)", "a WhatsApp solo se entra con whatsapp.py"),
]

try:
    cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
except Exception:
    sys.exit(0)
for pat, why in REGLAS:
    if re.search(pat, cmd, re.I):
        print(f"BLOQUEADO por guarda-envios: {why}. Si hace falta de verdad, pídeselo al dueño.", file=sys.stderr)
        sys.exit(2)
