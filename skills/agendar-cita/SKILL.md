---
name: agendar-cita
description: Cuando una chica acepta plan, crea el evento en el Google Calendar del dueño (cal.py crear) con un resumen de su perfil y avisa al dueño por Telegram.
---
# Agendar cita

1. Comprueba que el hueco sigue libre: `python3 ~/citas/cal.py huecos` (y que no se solapa con otra cita: `cal.py proximas`).
2. Crea el evento (hora local, TZ_NAME; por defecto 3 h):
   `python3 ~/citas/cal.py crear "Cita con NOMBRE (APP)" 2026-10-29T20:00 2026-10-29T23:00 "Ruta N: primera parada" "RESUMEN"`
   El RESUMEN (en varias líneas) lleva: **Nombre · edad · app**, **trabajo/estudios**, **zona**, **intereses y prompts destacados**, **de qué habéis hablado** (bromas internas incluidas), **plan/ruta acordada**, **cómo contactar** (chat de la app, su WhatsApp/IG si lo dio) y algo para no olvidar (p. ej. "es alérgica al kiwi").
3. `cal.py crear` ya avisa al dueño por Telegram con el enlace. Además contéstale tú con 2-3 líneas: con quién, cuándo, dónde.
4. Confirma a ella en el chat (corto) y pasa a la skill `pasar-a-whatsapp-instagram`.
