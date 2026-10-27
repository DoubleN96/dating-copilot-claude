---
name: pasar-a-whatsapp-instagram
description: Cuándo y cómo pasar la conversación a WhatsApp (preferido, $OWNER_WHATSAPP) o a Instagram ($OWNER_INSTAGRAM); tras pasarla, el copiloto deja ese chat y avisa al dueño con un resumen.
---
# Pasar a WhatsApp o Instagram

**Cuándo**: solo cuando ella ya ha aceptado un plan o muestra interés claro (pregunta cuándo os veis, propone ella, lleva varios mensajes con ganas). Nunca en el primer o segundo mensaje.

**Cómo** (`tecnicas_videos.md` §5): primero el plan, luego el contacto "para cuadrarlo", con seguridad:
- WhatsApp (mejor): `Hecho. Te dejo mi WhatsApp y lo cuadramos por ahí: <OWNER_WHATSAPP>` (el valor real sale de `echo $OWNER_WHATSAPP`)
- Si ella prefiere Instagram o no quiere dar número: `Sin problema, búscame en Insta: <OWNER_INSTAGRAM>` (`echo $OWNER_INSTAGRAM`)
- Si es ella quien da su número/IG: agradécelo corto y di que le escribes tú desde allí (lo hará el dueño).
Acepta el canal que ofrezca ella; no insistas con el teléfono.

**Después**: El copiloto ya NO lleva esa conversación (WhatsApp/IG los lleva el dueño). Puedes mandar 1-2 mensajes más de charla en la app para que no parezca que desaparece, y nada más.
Avisa al dueño (reply a su chat, `$OWNER_CHAT_ID`) con: nombre, app, canal (su número/IG si lo dio, o "le di tu WhatsApp"), resumen del perfil y de la conversación, plan y fecha si la hay, y el primer mensaje sugerido para WhatsApp (`Soy <OWNER_NAME>, el del vino pendiente 🍷`).
Apunta el traspaso en `~/citas/estado/traspasados.jsonl` (`{"fecha","app","match","canal"}`) para no volver a escribirle en la app.
