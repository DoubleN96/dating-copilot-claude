# Cómo colaborar · Contributing

¡Gracias por echar una mano! / Thanks for helping out!

## Antes de abrir un PR

1. **Nada personal en el repo.** Ni nombres reales, ni teléfonos, ni capturas de chats, ni IPs, rutas de tu máquina,
   dominios propios o claves. Lo tuyo va en `config.env`, `citas/rutas.md` y `panel/config.env`, que están en `.gitignore`.
   Si una captura es imprescindible, usa datos inventados.
2. **Pasa el escáner de secretos:** `gitleaks dir . && gitleaks git .` sin hallazgos.
3. **Tests en verde:** `cd panel && python3 test_celestia.py`.
4. **Sin dependencias nuevas** si la librería estándar de Python lo resuelve.
5. Commits cortos y en presente (`feat: …`, `fix: …`, `docs: …`).

## Qué no aceptamos

- Técnicas manipuladoras (negging, falsa urgencia, insistir tras un no) o cualquier cambio que haga que el bot **niegue ser una IA**,
  mienta sobre su dueño o escriba a quien no ha dado match.
- Evasión de captchas, de verificaciones o de bloqueos de las apps, compra de cuentas o rotación de IPs para esquivar baneos.
- Contenido copiado de cursos o creadores: resume con tus palabras y cita la fuente pública.

## Conectores que se rompen

Las apps cambian su interfaz a menudo. Si un conector de Android falla, adjunta la salida de `citas/ui.sh dump`
**con los nombres y textos de otras personas borrados**.

## Fallos de seguridad

No abras un issue público: usa «Report a vulnerability» (GitHub Security Advisories) del repo.

---

**English, short version:** no personal data in commits (names, phone numbers, chat screenshots, IPs, keys); run
`gitleaks dir . && gitleaks git .` and `cd panel && python3 test_celestia.py`; no new dependencies when the stdlib does it.
We do not accept manipulative techniques, anything that makes the bot deny being an AI, or captcha/ban evasion.
Report security issues privately through GitHub Security Advisories. By contributing you agree your work is MIT-licensed.
