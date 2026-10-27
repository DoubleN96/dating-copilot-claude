---
name: proponer-cita
description: Cuando la conversación da pie, propone a la chica una cita concreta usando una de las rutas del dueño (rutas.md) y SOLO sus huecos libres (CALENDAR_SLOTS) según cal.py.
---
# Proponer cita

1. ¿Toca ya? (`tecnicas_videos.md` §4.1): hay 4-7 mensajes con chispa, ella responde con ganas o da señales de interés (§3.8). Si no, sigue charlando.
2. Huecos: `python3 ~/citas/cal.py huecos` (franjas de CALENDAR_SLOTS libres en su calendario). Propón solo esos, nunca otro día/hora sin que el dueño lo diga.
3. Ruta: elige UNA de `rutas.md` (copia de `rutas_ejemplo.md` con TUS sitios) que encaje con lo que ella ha dicho (zona, gustos, presupuesto). No inventes sitios fuera de sus rutas.
4. Siembra antes y propone con seguridad (§4.2-4.3), un día concreto: p. ej. `¿El jueves te viene bien un vino por [barrio]? Conozco un sitio que te va a gustar`. Si pone un obstáculo de agenda, ofrece el otro hueco (§4.5); si dice que no, respétalo.
5. Envía con el script de la app. Cuando acepte día+plan → skill `agendar-cita`.
