# Panel web (núcleo de CelestIA)

Python solo con la librería estándar (+ `cryptography`) y SQLite. Entrar con Google, conectar WhatsApp (Evolution API propia,
QR o código de 8), Instagram (API oficial de Meta), Google Calendar (libre/ocupado y crear la cita) y una bandeja donde la IA
propone respuestas y tú decides. CRM por persona («Historias»), topes diarios, ritmo humano, pausa, escalado de temas delicados.

```bash
cp config.example.env config.env   # rellena
python3 test_celestia.py               # en verde antes de desplegar
set -a; . ./config.env; set +a; DB_PATH=./celestia.db python3 app.py   # http://localhost:8990
# o: docker build -t celestia-panel . && docker run --env-file config.env -v celestia:/data -p 8990:8990 celestia-panel
```

Sin `STRIPE_SECRET_KEY` no hay cobro: todo queda abierto para tu uso personal. El Android en la nube y el Chrome de Tinder por
usuario (`NUBE_URL`, `TINDER_URL`) son agentes del servidor del plan alojado y no forman parte de este repo; para las apps de
citas usa los conectores de `../citas/` (puente de lectura con `BRIDGE_SECRET`).

Self-hosted web panel: Google sign-in, WhatsApp (own Evolution API), Instagram (official Meta API), Google Calendar and an inbox
where the AI drafts and you approve. Stdlib Python + SQLite. Without Stripe keys everything is unlocked for personal use.
