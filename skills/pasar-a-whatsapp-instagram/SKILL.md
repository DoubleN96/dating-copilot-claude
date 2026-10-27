---
name: pasar-a-whatsapp-instagram
description: Cuándo y cómo pasar la conversación a WhatsApp (preferido, $OWNER_WHATSAPP) o a Instagram ($OWNER_INSTAGRAM); WhatsApp lo sigue el copiloto con whatsapp.py hasta cerrar la cita; Instagram lo lleva el dueño.
---
# Pasar a WhatsApp o Instagram

**Cuándo**: solo cuando ella ya ha aceptado un plan o muestra interés claro (pregunta cuándo os veis, propone ella, lleva varios mensajes con ganas). Nunca en el primer o segundo mensaje.

**Cómo** (`tecnicas_videos.md` §5): primero el plan, luego el contacto "para cuadrarlo", con seguridad:
- WhatsApp (mejor): `Hecho. Te dejo mi WhatsApp y lo cuadramos por ahí: <OWNER_WHATSAPP>` (el valor real sale de `echo $OWNER_WHATSAPP`)
- Si ella prefiere Instagram o no quiere dar número: `Sin problema, búscame en Insta: <OWNER_INSTAGRAM>` (`echo $OWNER_INSTAGRAM`)
- Si es ella quien da su número: agradécelo corto y di que le escribes por WhatsApp. Si da su IG: lo hará el dueño.
Acepta el canal que ofrezca ella; no insistas con el teléfono.

**Después (WhatsApp)**: la conversación la sigues TÚ desde su WhatsApp con `whatsapp.py` (ver CLAUDE.md). Sin `EVOLUTION_URL` configurado, la lleva el dueño como Instagram.
- Si ella te dio su número: `whatsapp.py alta NUMERO "Nombre (app)"` y le escribes tú primero, retomando algo de la app (`ey, soy <OWNER_NAME>, el del vino pendiente 🍷`).
- Si le diste el del dueño: en cada ronda mira `whatsapp.py nuevos`; cuando aparezca ella, `alta` y contestas al ritmo de siempre.
- En la app ya no escribes más (como mucho 1-2 mensajes para no desaparecer de golpe).
- Objetivo en WhatsApp: cerrar día, hora y sitio y agendarlo (`agendar-cita`).
- Si el dueño escribe él en ese chat (`leer` lo marca `DUEÑO`), ese chat es suyo hasta que te lo devuelva.
**Instagram**: lo lleva el dueño.
Avisa al dueño (reply a su chat, `$OWNER_CHAT_ID`) del traspaso con: nombre, app, canal (su número/IG si lo dio, o "le di tu WhatsApp"), resumen del perfil y de la conversación, plan y fecha si la hay.
Apunta el traspaso en `~/citas/estado/traspasados.jsonl` (`{"fecha","app","match","canal","numero"}`) para no volver a escribirle en la app.
