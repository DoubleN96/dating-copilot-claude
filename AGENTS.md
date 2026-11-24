# Instrucciones para Codex CLI (modo gratis con «Iniciar sesión con ChatGPT»)

Lee `CLAUDE.md` entero: quién eres, herramientas, flujo y reglas duras valen igual. Lo que cambia con Codex manda sobre `CLAUDE.md`:

1. **Sin Telegram.** No tienes la herramienta `reply` ni el canal: contesta al dueño aquí, en la terminal.
   Donde `CLAUDE.md` dice «por Telegram» o «con `reply`», entiende «en esta terminal».
2. **Siempre en modo APROBACIÓN.** Con Codex no hay hooks de seguridad (`guarda-envios.py`, `telegram-ack.py` solo
   existen en Claude Code), así que no hay modo autónomo: propones y solo envías cuando el dueño escribe «ok» aquí.
   Una ronda sin dueño delante deja las propuestas en la terminal y no envía nada.
3. **Envíos solo con los scripts de `citas/`** (`tinder.py enviar`, `hinge.py enviar`, `bumble.py enviar`,
   `whatsapp.py enviar`), que aplican PAUSA, topes y la lista de contactos dados de alta. Nunca `curl` ni llamadas
   a mano a la API de Evolution, de Tinder o de Meta, ni `adb` para escribir y enviar mensajes.
4. **Skills.** Codex no carga `skills/` solo: cuando te digan «usa la skill X», lee `skills/X/SKILL.md` y síguela.
5. **Likes.** La skill `likes-diarios` también requiere el «ok» del dueño en cada tanda.
