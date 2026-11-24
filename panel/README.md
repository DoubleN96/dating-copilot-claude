# Panel web (núcleo de CelestIA)

Python solo con la librería estándar (+ `cryptography`) y SQLite. Entrar con Google, conectar WhatsApp (Evolution API propia,
QR o código de 8), Instagram (API oficial de Meta), Google Calendar (libre/ocupado y crear la cita) y una bandeja donde la IA
propone respuestas y tú decides. CRM por persona («Historias»), topes diarios, ritmo humano, pausa, escalado de temas delicados.

```bash
cp config.example.env config.env   # rellena: KEY=valor, sin comillas ni comentarios en la misma línea
python3 test_celestia.py               # en verde antes de desplegar
DB_PATH=./celestia.db python3 app.py   # lee config.env solo; http://localhost:8990
# o: docker build -t celestia-panel . && docker run --env-file config.env -v celestia:/data -p 8990:8990 celestia-panel
```

`app.py` no arranca si `SESSION_KEY` (32+ caracteres) o `FERNET_KEY` faltan o son débiles. Sin `STRIPE_SECRET_KEY` no hay
cobro, y **solo entran las cuentas de Google de `ALLOWED_EMAILS`** (obligatorio en ese caso): así nadie que encuentre tu URL
gasta tu clave de IA ni usa tu WhatsApp, y no guardas datos de desconocidos.

Este panel lee WhatsApp e Instagram. **Los chats de Tinder, Hinge y Bumble no llegan solos a la bandeja**: el lector que los
manda (`POST /bridge/citas` con `BRIDGE_SECRET`) y el Android/Chrome en la nube (`NUBE_URL`, `TINDER_URL`) son piezas del plan
alojado y no están en este repo. Para esas apps usa el copiloto de terminal (`../citas/`, `launch.sh` o `launch-codex.sh`).

Self-hosted web panel: Google sign-in, WhatsApp (own Evolution API), Instagram (official Meta API), Google Calendar and an inbox
where the AI drafts and you approve. Stdlib Python + SQLite. Without Stripe keys there is no billing and only the Google accounts
in `ALLOWED_EMAILS` can sign in (required). It refuses to start with a missing or weak `SESSION_KEY`/`FERNET_KEY`. Dating-app chats
(Tinder/Hinge/Bumble) are not fed into this inbox by this repo; use the terminal copilot in `../citas/` for those.
