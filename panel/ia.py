"""Propuesta de respuesta para un chat (API de Claude con prompt caching). Cambiar de modelo = variable IA_MODEL."""
import json, os, re, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
MAD = ZoneInfo("Europe/Madrid")

MODEL = os.environ.get("IA_MODEL", "claude-haiku-5-5")
SYSTEM = """Eres CelestIA, el copiloto de citas del usuario. Redactas el SIGUIENTE mensaje que él/ella enviaría en un chat
con alguien que ha conocido en una app de citas. Objetivo: conversación natural y con chispa que lleve a una cita real.
Reglas:
- Escribe como el usuario (su tono y forma de escribir), en el idioma del chat, corto (1-2 frases), sin emojis en exceso.
- Nada de manipulación, presión, mentiras ni técnicas de «seducción» agresivas. Respeta siempre un «no».
- Si la conversación va bien y hay confianza, propón un plan concreto usando sus huecos libres y lugares preferidos.
- ESCALA (escalar=true, sin respuesta) si: preguntan si eres una IA o un bot, temas sexuales explícitos, dinero, menores,
  la otra persona dice que no o pide parar, o hay algo delicado (salud, duelo, conflicto).
Además clasifica la conversación:
- etapa: "conversando" (aún se conocen), "propuesta" (hay un plan o fecha sobre la mesa) o "cita" (AMBOS han aceptado día y hora concretos).
- cita: SOLO si etapa es "cita", {"inicio": "AAAA-MM-DDTHH:MM" (hora de Madrid), "lugar": "..."}; si no, null.
Responde SOLO con JSON: {"respuesta": "...", "escalar": false, "motivo": "", "etapa": "conversando", "cita": null}"""
ETAPAS = ("conversando", "propuesta", "cita")
# red de seguridad en código: aunque el modelo falle, estas entradas nunca se contestan solas
PELIGRO = re.compile(r"\b(eres (una )?(ia|bot|robot|m[aá]quina)|chat ?gpt|inteligencia artificial|menor de edad|tengo 1[0-7]\b|dinero|"
                     r"bizum|transferencia|d[eé]jame en paz|no me escribas|para ya)\b", re.I)


def cita_valida(c):
    """{'inicio': datetime naive (hora de Madrid), 'lugar': str} o None; descarta fechas mal formadas o pasadas."""
    try:
        ini = datetime.strptime(str(c["inicio"])[:16], "%Y-%m-%dT%H:%M")
    except (TypeError, KeyError, ValueError):
        return None
    return {"inicio": ini, "lugar": str(c.get("lugar") or "")[:120]} if ini > datetime.now(MAD).replace(tzinfo=None) else None


def escalar_por_reglas(texto):
    return bool(PELIGRO.search(texto or ""))


def proponer(mensajes, perfil="", libres=()):
    """mensajes: [(de, texto)] con de in {'yo','ella/él'}; devuelve dict respuesta/escalar/motivo."""
    ultimo = next((t for d, t in reversed(mensajes) if d != "yo"), "")
    if escalar_por_reglas(ultimo):
        return {"respuesta": "", "escalar": True, "motivo": "regla de seguridad", "etapa": "conversando", "cita": None}
    chat = "\n".join(f"{'YO' if d == 'yo' else 'ELLA/ÉL'}: {t[:500]}" for d, t in mensajes[-20:])
    hoy = datetime.now(MAD).strftime("%Y-%m-%d %H:%M")
    user = f"Hoy (hora de Madrid): {hoy}\nPerfil y estilo del usuario:\n{perfil[:1500]}\n\nHuecos libres para quedar: {', '.join(libres) or 'desconocidos'}\n\nChat:\n{chat}"
    body = {"model": MODEL, "max_tokens": 400, "thinking": {"type": "disabled"},
            "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                 headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    txt = "".join(b.get("text", "") for b in json.load(urllib.request.urlopen(req, timeout=60))["content"] if b.get("type") == "text")
    m = re.search(r"\{.*\}", txt, re.S)
    try:
        r = json.loads(m.group(0)) if m else {}
    except ValueError:
        r = {}
    r = {"respuesta": str(r.get("respuesta") or "")[:600], "escalar": bool(r.get("escalar")), "motivo": str(r.get("motivo") or "")[:200],
         "etapa": r.get("etapa") if r.get("etapa") in ETAPAS else "conversando", "cita": cita_valida(r.get("cita"))}
    if r["etapa"] != "cita":
        r["cita"] = None
    if not r["respuesta"] and not r["escalar"]:
        r.update(escalar=True, motivo="la IA no devolvió respuesta válida")
    return r
