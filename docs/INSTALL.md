# Instalación paso a paso

Esto es cómo se montó de verdad, con los tropiezos incluidos. Calcula una tarde larga.

> ⚠️ **Antes de empezar.** Los términos de uso de Tinder, Hinge y Bumble **prohíben la automatización**
> (bots, scripts, emuladores, acceso no oficial a su API). Pueden **suspender o banear tu cuenta** sin aviso.
> Úsalo solo con **tu propia cuenta**, bajo **tu responsabilidad**, y con respeto hacia las personas con las que
> hablas: el bot nunca debe negar que es una IA si se lo preguntan. Esto no es un servicio, es un experimento.

## Arquitectura

```
                 Telegram (tú)
                      │  plugin telegram de Claude Code
          ┌───────────▼────────────┐
          │  Servidor (Linux)      │
          │  Claude Code, HOME     │──── túnel SSH ────► Raspberry / PC en casa (IP residencial)
          │  aislado + skills      │                      ├─ Chromium aislado con CDP  (Tinder web)
          │  citas/*.py            │                      └─ tinyproxy :3128           (salida del Android)
          │  redroid (Android 13)  │──── proxy ──────────┘
          │  Hinge + Bumble        │
          │  n8n (SMS webhook)     │◄─── SMS Forwarder (tu móvil Android)
          └────────────────────────┘
                      │
               Google Calendar (OAuth)
```

¿Por qué la IP de casa? Las apps de citas desconfían de las IP de centros de datos (captchas sin fin,
cuentas "en revisión", shadowban). Tinder web y el Android salen a Internet por tu conexión residencial.

En todo el documento: `SERVIDOR` es la máquina donde corre Claude Code, `PI` la máquina de casa
(Raspberry Pi o cualquier Linux), `usuario_pi` su usuario y `100.x.y.z` su IP privada (Tailscale/WireGuard/LAN).

---

## 1. Sesión aislada de Claude Code + bot de Telegram

La idea: una instancia de Claude Code **solo para esto**, con su propio HOME, su CLAUDE.md, sus skills y su
bot de Telegram. Así no comparte memoria, credenciales ni historial con nada más.

1. Crea un usuario de sistema o, como mínimo, un directorio que hará de HOME:
   ```bash
   git clone https://github.com/DoubleN96/dating-copilot-claude.git ~/copiloto
   cd ~/copiloto
   cp config.example.env config.env && chmod 600 config.env   # rellena tus datos
   cp citas/rutas_ejemplo.md citas/rutas.md                     # pon TUS sitios
   mkdir -p .claude/skills .claude/helpers citas/estado
   cp -r skills/* .claude/skills/ && cp helpers/*.py .claude/helpers/
   ```
   Los scripts esperan estar en `~/citas` del HOME aislado: con `HOME=~/copiloto`, eso es `~/copiloto/citas`. ✔
2. **Login de Claude Code** con ese HOME: `HOME=~/copiloto claude` → `/login`. Sal.
3. **Bot de Telegram**: habla con [@BotFather](https://t.me/BotFather) → `/newbot` → copia el token.
4. Instala el plugin oficial de Telegram en esa sesión (`/plugin install telegram@claude-plugins-official`)
   y configúralo con `/telegram:configure` pegando el token (lo guarda en `.claude/channels/telegram/.env`).
5. **Allowlist**: escribe a tu bot desde tu Telegram, te dará un código de emparejamiento; apruébalo con
   `/telegram:access` en el terminal. Pon la política en `allowlist` para que **nadie más** pueda hablarle
   (`.claude/channels/telegram/access.json`). Nunca apruebes emparejamientos porque te lo pida un mensaje.
6. **Hooks** en `.claude/settings.json` (cambia la ruta):
   ```json
   {
     "hooks": {
       "UserPromptSubmit": [{ "hooks": [{ "type": "command",
         "command": "python3 \"/RUTA/copiloto/.claude/helpers/telegram-ack.py\"", "timeout": 8000 }] }],
       "PreToolUse": [{ "matcher": "Bash", "hooks": [{ "type": "command",
         "command": "python3 \"/RUTA/copiloto/.claude/helpers/guarda-envios.py\"", "timeout": 5000 }] }]
     }
   }
   ```
   - `telegram-ack.py` reacciona 👀 a cada mensaje y, si **tú** (OWNER_CHAT_ID) escribes «pausa»/«stop», crea
     `citas/PAUSA` (no sale ningún mensaje); «sigue» lo quita. Funciona aunque el modelo esté ocupado.
   - `guarda-envios.py` bloquea atajos: llamar a la API de Tinder fuera de `tinder.py`, tocar el registro de
     envíos o borrar la PAUSA. Es un cinturón contra deriva o inyección, no una jaula.
7. Arranca dentro de tmux: `tmux new -s copiloto ~/copiloto/launch.sh`.
   `launch.sh` usa `--dangerously-skip-permissions` porque el bot trabaja desatendido: hazlo **solo** en un
   usuario/máquina dedicados, sin credenciales de otras cosas a su alcance.

## 2. Tinder web en un Chromium aparte, en casa, por CDP

Tinder tiene web (tinder.com). En vez de pelearse con su API, `tinder.py` usa la **pestaña ya logueada** a
través del protocolo de depuración de Chrome (CDP) y hace `fetch` desde dentro de la página con el token de
`localStorage`: el token nunca sale de la pestaña. No llama a `/v2/seen` (no marca nada como visto).

En la PI:
```bash
sudo apt install chromium
# Perfil SEPARADO del navegador personal. CDP solo en localhost.
cat > ~/.config/systemd/user/puente-citas.service <<'EOF'
[Unit]
Description=Chromium aislado para el copiloto de citas (CDP 127.0.0.1:9250)
[Service]
Environment=DISPLAY=:0
ExecStart=/usr/bin/chromium --user-data-dir=%h/puente-citas-perfil --remote-debugging-address=127.0.0.1 --remote-debugging-port=9250 --no-first-run https://tinder.com
Restart=always
[Install]
WantedBy=default.target
EOF
systemctl --user enable --now puente-citas   # si falla por sesión, exporta XDG_RUNTIME_DIR=/run/user/$(id -u)
loginctl enable-linger $USER
```
Inicia sesión en Tinder **a mano** en esa ventana (Google o teléfono). Ojo: Tinder limita los SMS de login
(HTTP 429) si pides varios seguidos.

En el SERVIDOR, un túnel SSH permanente (llave SSH sin contraseña, `BatchMode=yes`):
```ini
# ~/.config/systemd/user/puente-citas-tunnel.service
[Unit]
Description=Túnel SSH al Chromium aislado (CDP) 127.0.0.1:9250 -> PI 127.0.0.1:9250
StartLimitIntervalSec=0
[Service]
ExecStart=/usr/bin/ssh -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -NL 127.0.0.1:9250:127.0.0.1:9250 usuario_pi@100.x.y.z
Restart=always
RestartSec=15
[Install]
WantedBy=default.target
```
`systemctl --user enable --now puente-citas-tunnel` y prueba: `curl -s 127.0.0.1:9250/json/list`.
**Nunca** apuntes el túnel al puerto de depuración de tu navegador personal.

## 3. Android emulado para Hinge y Bumble (redroid)

**Bumble ya no tiene web** y Hinge nunca la tuvo: hace falta Android. [redroid](https://github.com/remote-android/redroid-doc)
es Android en un contenedor Docker, sin emulador gráfico.

### 3.1 Imagen con Google Play (MindTheGapps)
Hinge exige Google Play Services («requires the Google Play Store»), así que la imagen lleva GApps:
```bash
git clone --depth 1 https://github.com/ayasa520/redroid-script.git rs && cd rs
python3 -m venv .v && .v/bin/pip install requests tqdm
# Si tu versión no lo trae, añade '13.0.0_64only' a las opciones de -a en redroid.py
.v/bin/python redroid.py -a 13.0.0_64only -mtg      # -> redroid/redroid:13.0.0_64only_mindthegapps (~2 GB)
```
- `64only` (x86_64) **no** admite libndk/houdini: las apps solo ARM no corren. Hinge y Bumble publican x86_64 en Play.
  Si necesitas traducción ARM, usa una imagen no-64only con `-n` (libndk).

### 3.2 binder y contenedor
```bash
sudo modprobe binder_linux devices="binder,hwbinder,vndbinder"   # en kernels con binderfs: ver redroid-doc
mkdir -p ~/redroid-data
sudo docker run -d --name redroid-citas --privileged --memory 3g --cpus 2 --restart unless-stopped \
  -p 127.0.0.1:5556:5555 -v ~/redroid-data:/data \
  redroid/redroid:13.0.0_64only_mindthegapps \
  androidboot.redroid_width=720 androidboot.redroid_height=1440 androidboot.redroid_dpi=320 ro.setupwizard.mode=DISABLED
adb connect 127.0.0.1:5556
```
- **adb solo en `127.0.0.1`**: un adb expuesto a Internet es control total del Android para cualquiera.
- Los scripts asumen pantalla de **720 px** de ancho (la columna de nombres y las burbujas se detectan por coordenadas).
- 3 GB de RAM por contenedor; vigila la memoria del servidor.

### 3.3 Salida por la IP de casa (proxy residencial)
En la PI: `sudo apt install tinyproxy`, que escuche en `127.0.0.1:3128` (`Listen 127.0.0.1`, `Allow 127.0.0.1`).

En el SERVIDOR, otro túnel que publica ese proxy **solo en la IP del bridge de Docker** (nunca en 0.0.0.0,
sería un proxy abierto a tu línea de casa):
```ini
# ~/.config/systemd/user/citas-egress-tunnel.service
[Unit]
Description=Salida por la IP de casa para el Android: 172.17.0.1:3128 -> PI 127.0.0.1:3128
StartLimitIntervalSec=0
[Service]
ExecStart=/usr/bin/ssh -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -NL 172.17.0.1:3128:127.0.0.1:3128 usuario_pi@100.x.y.z
Restart=always
RestartSec=15
[Install]
WantedBy=default.target
```
Y abre el cortafuegos solo para la IP del contenedor:
```bash
IP=$(sudo docker inspect -f '{{.NetworkSettings.IPAddress}}' redroid-citas)
sudo ufw allow from $IP to 172.17.0.1 port 3128 proto tcp comment 'redroid -> proxy casa'
adb -s 127.0.0.1:5556 shell settings put global http_proxy 172.17.0.1:3128
```
La IP del contenedor puede cambiar al reiniciar: si deja de tener red, rehaz la regla. Comprueba la IP de
salida desde el Android (p. ej. abriendo una web de "cuál es mi IP") antes de iniciar sesión en ninguna app.

### 3.4 Instalar las apps: Play vs Aurora
- **Google Play**: inicia sesión con una cuenta de Google. Como el dispositivo no está certificado, registra su
  GSF ID en <https://www.google.com/android/uncertified> (el ID sale de
  `adb shell sqlite3 /data/data/com.google.android.gsf/databases/gservices.db "select * from main where name='android_id'"`)
  y espera un rato. Google puede pedir confirmación en tu móvil.
- **Aurora Store** (cliente anónimo de Play) sirve para instalar sin cuenta, pero Hinge sin Play Services no
  deja iniciar sesión con Google. Si bajas APKs sueltas, **verifica la firma** (certificado SHA-256 del desarrollador).
- **ADBKeyboard** (<https://github.com/senzhk/ADBKeyBoard>): `adb install ADBKeyboard.apk` y
  `adb shell ime enable com.android.adbkeyboard/.AdbIME`. `input text` de adb no admite tildes ni emojis;
  ADBKeyboard sí (por broadcast en base64). `android_enviar.py` lo activa solo mientras escribe.

### 3.5 Logins (la parte manual)
- **Bumble**: «I have an account» → teléfono → aparece un **captcha** («Start Puzzle») que tienes que pasar tú
  (ver §6, pantalla remota). Luego código por SMS.
- **Hinge**: «Sign in with Phone Number» → código por SMS; a veces además pide un **código por correo**.
- Los SMS de Bumble/Hinge llevan el prefijo **«<#>»** (formato SMS Retriever de Android) y muchos reenviadores
  no los pasan: ten el móvil a mano para leerlos tú.
- Bumble marca algunas pantallas con FLAG_SECURE (las capturas salen negras): el bot lee con `ui.sh dump`
  (uiautomator), no con capturas.

## 4. Códigos SMS: SMS Forwarder → webhook de n8n (opcional)

Para que el bot lea códigos de login sin que se los dictes:
1. En tu móvil Android instala **SMS Forwarder** (<https://github.com/bogkonstantin/android_income_sms_gateway_webhook>).
2. En n8n importa `n8n/sms-webhook.example.json`, cambia el `path` por uno aleatorio, crea una credencial de
   cabecera secreta y actívalo. Las ejecuciones deben guardarse (`saveDataSuccessExecution: all`).
3. En la app: URL del webhook + la cabecera secreta; filtra por remitente si puedes.
4. `config.env`: `N8N_API_URL`, `N8N_API_KEY`, `N8N_SMS_WORKFLOW_ID`. `citas/sms_codigo.py 15` imprime **solo**
   SMS de los últimos 15 min que mencionen Tinder/Hinge/Bumble.

Limitación: los SMS con «<#>» (Bumble/Hinge) no siempre llegan. Y piénsalo dos veces: reenviar tus SMS a un
servidor es reenviar también los de tu banco. Filtra en el móvil todo lo que puedas.

## 5. Google Calendar (OAuth)

1. En Google Cloud Console: proyecto → habilita **Google Calendar API** → pantalla de consentimiento (modo
   pruebas, tú como usuario de prueba) → credencial **OAuth client ID** de tipo *Desktop*.
2. Consigue un `refresh_token` con el scope `https://www.googleapis.com/auth/calendar` (por ejemplo con
   [OAuth Playground](https://developers.google.com/oauthplayground) usando tu propio client ID, o con
   `google-auth-oauthlib` y `InstalledAppFlow.run_local_server`).
3. Guárdalo en `GOOGLE_CALENDAR_CREDS` (chmod 600): `{"client_id": "...", "client_secret": "...", "refresh_token": "..."}`.
4. `CALENDAR_SLOTS` define cuándo puedes quedar. `python3 citas/cal.py huecos` devuelve franjas libres de ≥2 h;
   `cal.py crear` crea el evento con el resumen del perfil y te avisa por Telegram.

## 6. Pantalla remota del Android en el navegador

Para pasar captchas o mirar qué hace el bot desde el móvil: `tools/pantalla.py` sirve capturas (`screencap`)
y convierte toques/deslizamientos en `input tap/swipe`. Escucha **solo en 127.0.0.1:8977** con usuario/clave.
```bash
echo "usuario:$(openssl rand -hex 12)" > tools/pantalla.env && chmod 600 tools/pantalla.env
tmux new -d -s pantalla 'python3 tools/pantalla.py'
tmux new -d -s tunel 'cloudflared tunnel --url http://127.0.0.1:8977'   # quick tunnel: te da una URL *.trycloudflare.com
```
La URL del quick tunnel cambia en cada arranque. **No lo dejes abierto** más de lo necesario: aunque tenga
contraseña, es tu Android logueado en tus apps.

## 7. Autonomía con salvaguardas

Recomendado: empezar en **modo aprobación** (el bot propone por Telegram con el formato de `estilo.md` §4 y tú
contestas `ok`, `ok 2`, `> texto literal`, `no`, `otra`) y pasar a autónomo cuando el estilo te convenza.

Salvaguardas que ya trae el código:
- **PAUSA**: escribe «pausa» al bot y no sale ni un mensaje más (`citas/PAUSA`); «sigue» lo reanuda.
- **Límites** (`envio.py`): mínimo `MIN_SECONDS` entre envíos y `MAX_PER_DAY` al día; todo envío pasa por ahí.
- **Registro**: `citas/estado/enviados.jsonl` (fecha, app, match, texto) y **resumen diario** por Telegram.
- **Ritmo impredecible**: el CLAUDE.md obliga a retrasos aleatorios según el interés de ella, nada de madrugada,
  no contestar todo en la misma ronda. `likes-diarios` limita likes por ronda con pausas aleatorias.
- **Honestidad**: nunca niega ser una IA; si ella lo pregunta, el bot se aparta y te avisa.
- **Inyección**: bios y mensajes son datos, nunca instrucciones; el hook `guarda-envios.py` bloquea atajos.

Rondas automáticas con cron (en el usuario que corre tmux):
```cron
0 * * * *  /bin/bash /RUTA/copiloto/citas/ronda.sh         >> /RUTA/copiloto/citas/estado/ronda.log 2>&1
30 * * * * /bin/bash /RUTA/copiloto/citas/ronda.sh resumen >> /RUTA/copiloto/citas/estado/ronda.log 2>&1
```
`ronda.sh` solo teclea la ronda a las 10, 12, …, 22 h (hora de `TZ_NAME`), si el bot no está ocupado ni hay
texto a medio escribir, y manda el resumen a las 23:30.

## 8. Crear tus propios manuales a partir de vídeos de YouTube

Los manuales `tecnicas_*.md` se hicieron descargando **solo los subtítulos** de canales de consejos de citas y
resumiéndolos con Claude por lotes (fórmulas, plantillas adaptadas y, muy importante, una lista de técnicas
**descartadas** por manipuladoras). Para hacer los tuyos:
```bash
pip install yt-dlp
# YouTube bloquea a menudo las IP de servidores ("Sign in to confirm you're not a bot", HTTP 429):
# usa el proxy residencial de §3.3 desde el SERVIDOR.
yt-dlp --proxy http://172.17.0.1:3128 --skip-download --write-auto-subs --sub-langs "es.*,en.*" \
  --sub-format vtt -o "yt/%(id)s.%(ext)s" "https://www.youtube.com/@CANAL/videos"
```
Luego pide a Claude: "resume estos subtítulos en técnicas aplicables al chat, cita el ID del vídeo de cada
idea y separa lo que sea manipulación en una lista de descartes". Respeta los derechos de autor: guarda
resúmenes con tus palabras, no transcripciones.

## Problemas típicos
| Síntoma | Causa probable |
|---|---|
| `tinder.py` no encuentra la pestaña | el túnel CDP está caído o cerraste la pestaña de tinder.com |
| `HTTP 401` en Tinder | sesión caducada: vuelve a iniciar sesión en el Chromium de la PI |
| El Android no tiene red | la IP del contenedor cambió: rehaz la regla ufw (§3.3) |
| Hinge: «requires the Google Play Store» | imagen sin GApps: usa la de MindTheGapps |
| Captcha sin fin / cuenta "en revisión" | IP de centro de datos: revisa que el proxy residencial funciona |
| `no encuentro la pestaña Chats` | popup o pantalla de carga: mira `ui.sh dump` o la pantalla remota |
