---
name: likes-diarios
description: Rutina diaria de likes/swipes en Tinder, Hinge y Bumble con ritmo humano y filtros razonables, sin pagar nunca nada.
---
# Likes diarios

Ritmo humano: por ronda, como mucho **15 perfiles por app**, con 4-12 s aleatorios entre uno y otro; máximo ~50 likes al día en total entre las tres. Si una app muestra límite de likes, para (no pagues).

Filtros razonables (si el perfil lo dice): los que el dueño haya puesto en su CLAUDE.md (edad, zona, etc.), con al menos 2 fotos y algo de bio o prompts; descarta perfiles vacíos, sospechosos de bot/scam (enlaces, "sígueme en...", OnlyFans), o que pidan dinero. Like a quien encaje, NOPE al resto (no likes a todo).

- **Tinder**: pestaña tinder.com del Chromium por CDP, `cdp.py` (`clickxy` en LIKE/NOPE o `key ArrowRight/ArrowLeft`). Nunca Super Like ni Boost.
- **Hinge**: `ui.sh dump` para leer el perfil en Discover; like al corazón de un prompt o foto (sin comentario o con uno corto, ver `primer-mensaje`); "Skip" para descartar. Nunca Rose ni Standouts de pago.
- **Bumble**: Discover; `adb -s $ANDROID_SERIAL shell input swipe` derecha (like) / izquierda (no). Nunca SuperSwipe, Spotlight ni Extend.

Cualquier pantalla de pago, captcha o verificación: sal con Back y avisa al dueño.
