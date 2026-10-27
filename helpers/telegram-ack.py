#!/usr/bin/env python3
"""UserPromptSubmit hook: react 👀 to every inbound Telegram message as a
'received' acknowledgement. Best-effort, never blocks the prompt.

Parses the <channel source="...telegram..." chat_id=".." message_id=".."> tags
from the submitted prompt, reads this session's bot token from
$HOME/.claude/channels/telegram/.env, and calls Telegram setMessageReaction.
"""
import sys, os, re, json, urllib.request

EMOJI = "👀"

def main():
    try:
        raw = sys.stdin.read()
    except Exception:
        return
    prompt = raw
    if raw.strip().startswith("{"):
        try:
            prompt = json.loads(raw).get("prompt", raw)
        except Exception:
            prompt = raw

    try:
        pausa_sigue(prompt)
    except Exception:
        pass

    # token for THIS session (HOME-relative so it works for isolated sessions)
    token = None
    env_path = os.path.expanduser("~/.claude/channels/telegram/.env")
    try:
        for line in open(env_path):
            if "TELEGRAM_BOT_TOKEN" in line and "=" in line:
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    except Exception:
        return
    if not token:
        return

    seen = set()
    for m in re.finditer(r"<channel\b[^>]*>", prompt):
        tag = m.group(0)
        if "telegram" not in tag:
            continue
        cid = re.search(r'chat_id="([^"]+)"', tag)
        mid = re.search(r'message_id="([^"]+)"', tag)
        if not (cid and mid):
            continue
        key = (cid.group(1), mid.group(1))
        if key in seen:
            continue
        seen.add(key)
        try:
            body = json.dumps({
                "chat_id": cid.group(1),
                "message_id": int(mid.group(1)),
                "reaction": [{"type": "emoji", "emoji": EMOJI}],
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/setMessageReaction",
                data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:
            pass


# --- Interruptor de pausa (modo autónomo) ------------------------------------------
# Solo un prompt REAL de Telegram del chat del dueño (OWNER_CHAT_ID): "pausa"/"stop" crea citas/PAUSA (no sale ningún
# mensaje a las chicas) y "sigue" lo quita. El texto de los matches llega como salida de herramientas y nunca pasa por aqui.
OWNER = os.environ.get("OWNER_CHAT_ID", "")
PAUSA = os.path.join(os.environ.get("COPILOTO_DIR", os.path.expanduser("~/citas")), "PAUSA")


def pausa_sigue(prompt):
    for m in re.finditer(r"<channel\b([^>]*)>(.*?)</channel>", prompt, re.S):
        if not OWNER or "telegram" not in m.group(1) or f'chat_id="{OWNER}"' not in m.group(1):
            continue
        t = m.group(2).strip().lower().strip(".!¡ ")
        if t in ("pausa", "stop", "para"):
            open(PAUSA, "w").write("pausado por el dueño desde Telegram\n")
        elif t in ("sigue", "continua", "continúa", "reanuda") and os.path.exists(PAUSA):
            os.remove(PAUSA)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
