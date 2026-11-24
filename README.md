# dating-copilot-claude · núcleo abierto de CelestIA

**Tu copiloto de citas con IA.** Lee tus matches de Tinder, Hinge y Bumble (y WhatsApp/Instagram), contesta con *tu* estilo,
propone planes en *tus* sitios y solo en *tus* huecos libres, los apunta en tu Google Calendar y te lo cuenta todo.
Tú decides si propone y espera tu «ok», o si va solo con límites y botón de pausa.

> ⚠️ **Aviso legal. Léelo antes.** Los términos de uso de Tinder, Hinge, Bumble, Instagram y WhatsApp **prohíben o limitan
> la automatización**. Usar esto puede hacer que **te suspendan o baneen la cuenta** o el número. Úsalo solo con tu propia
> cuenta, bajo tu responsabilidad, y cumpliendo la ley de tu país (en la UE, el RGPD: los chats contienen datos de otras
> personas). Al otro lado hay personas: el bot está configurado para **no negar nunca que es una IA**, no mentir sobre ti,
> no presionar y respetar un no. Este software se da «tal cual», sin garantía (licencia MIT). Si eso no te encaja, no lo uses.

## Dos formas de usarlo

| | **Gratis (este repo)** | **CelestIA Nube** |
|---|---|---|
| Dónde corre | En tu ordenador o servidor (Linux/macOS/WSL) con tu Android en Docker o tu móvil | En nuestros servidores |
| La IA | **Tu propia cuenta**: el **Claude Code oficial** con tu suscripción (`claude` y su propio inicio de sesión) **o** el **Codex CLI oficial** con «**Iniciar sesión con ChatGPT**». Nunca vemos ni guardamos tus credenciales | Incluida |
| Android e IP | Los montas tú (redroid + tu IP de casa) | Android en la nube propio e IP residencial propia, incluidos |
| Precio | 0 € | **29 €/mes + IVA**, 3 días gratis, cancelas cuando quieras: [app.celestia.meetqiu.com](https://app.celestia.meetqiu.com) |

### Modo gratis en 4 pasos

```bash
git clone https://github.com/DoubleN96/dating-copilot-claude.git ~/copiloto && cd ~/copiloto
cp config.example.env config.env && cp citas/rutas_ejemplo.md citas/rutas.md   # rellena los dos
# edita CLAUDE.md (tu nombre, filtros, modo) y personaliza estilo.md §3 con tu voz
tmux new -s copiloto ./launch.sh          # Claude Code oficial: inicia sesión con tu cuenta (claude /login)
# o bien
tmux new -s copiloto ./launch-codex.sh    # Codex CLI oficial: «Sign in with ChatGPT» (lee AGENTS.md)
```

Con Claude Code tienes además el canal de Telegram, los hooks de seguridad y las skills; con Codex le hablas en la terminal
y `citas/ronda.sh` le lanza las rondas igual. ¿Prefieres una web? El **panel** (`panel/`) es el núcleo de CelestIA para
autoalojar: entrar con Google, WhatsApp, Instagram, Calendar y bandeja de propuestas ([panel/README.md](panel/README.md)).

## Qué hace

- **Tinder** por la web (tinder.com) en un Chromium aparte, vía CDP, con la sesión que tú inicias.
- **Hinge y Bumble** en un Android 13 en Docker ([redroid](https://github.com/remote-android/redroid-doc) + MindTheGapps), manejado con `adb` y uiautomator.
- Sale a Internet por **tu IP de casa** (Raspberry Pi + túnel SSH + tinyproxy), no por la de un servidor.
- **Redacta** con manuales de técnicas sacados de cientos de vídeos de consejos de citas, con una lista explícita
  de técnicas **descartadas** por manipuladoras (negging, falsa urgencia, insistir tras un no...).
- **Agenda** citas en Google Calendar solo en las franjas que tú marques, con un resumen de la conversación.
- **Pasa la conversación a WhatsApp/Instagram** cuando hay plan. En WhatsApp (opcional, vía Evolution API) la sigue
  el bot hasta cerrar la cita, solo en los chats traspasados; si escribes tú en ese chat, se aparta.
- **Salvaguardas**: «pausa» por Telegram corta todos los envíos, tope por día y por minuto, registro de cada
  mensaje, resumen diario y ritmo de respuesta humano e impredecible.

## Cómo está hecho

| Pieza | Fichero |
|---|---|
| Instrucciones del bot (plantilla) | `CLAUDE.md` |
| Conector Tinder (CDP + fetch dentro de la pestaña) | `citas/tinder.py`, `citas/cdp.py` |
| Conector Hinge/Bumble (adb + uiautomator + ADBKeyboard) | `citas/android_enviar.py`, `citas/hinge.py`, `citas/bumble.py`, `citas/ui.sh` |
| Límites, pausa, registro, avisos | `citas/envio.py` |
| Calendario | `citas/cal.py` |
| WhatsApp tras el traspaso (Evolution API, opcional) | `citas/whatsapp.py` |
| Rondas por cron | `citas/ronda.sh` |
| Códigos SMS (opcional, vía n8n) | `citas/sms_codigo.py`, `n8n/sms-webhook.example.json` |
| Skills (flujo de trabajo) | `skills/*/SKILL.md` |
| Hooks (👀, pausa, bloqueo de atajos) | `helpers/*.py` |
| Estilo y técnicas | `citas/estilo.md`, `citas/tecnicas_videos.md`, `citas/rutas_ejemplo.md` |
| Pantalla remota del Android | `tools/pantalla.py` |
| Panel web autoalojado (núcleo de CelestIA) | `panel/` |

Todo lo personal va en `config.env` (a partir de `config.example.env`) y en `citas/rutas.md`; ninguno se sube a git.

## Empezar

Guía completa, con lo que falla y por qué: **[docs/INSTALL.md](docs/INSTALL.md)**.

Requisitos: Claude Code o Codex CLI (oficiales, con tu propia cuenta), un bot de Telegram, Linux con Docker (≥3 GB de RAM libres para el Android), una máquina
en casa para la IP residencial y Python 3.9+ (`pip install websockets`).

## Limitaciones honestas

- Los conectores de Android leen la pantalla por coordenadas (pantalla de 720 px): **una actualización de la app
  puede romperlos**. `ui.sh dump` es tu amigo.
- Captchas, logins, 2FA y pagos los haces tú. El bot no paga nada nunca.
- Los SMS con «<#>» (Bumble/Hinge) a menudo no llegan al reenviador.
- El estilo de ejemplo es de una persona concreta en español de España: **cámbialo por el tuyo** o sonarás a otro.

---

## English

**dating-copilot-claude** is the open-source core of **CelestIA**, an AI dating copilot. It reads your Tinder (web, via
Chrome DevTools Protocol), Hinge and Bumble (Android 13 in Docker via redroid + adb), WhatsApp and Instagram chats, drafts
or sends replies in your own style using technique manuals distilled from dating-advice videos (manipulative techniques
explicitly excluded), proposes dates only at your venues and free calendar slots, and books them in Google Calendar.
Safeguards: "pause" kill switch, per-minute and per-day caps, a send log, a daily summary and human-like timing. The bot is
instructed to never deny being an AI.

**Two ways to use it**

- **Free, self-hosted (this repo):** runs on your own computer/server with your own AI account — the **official Claude Code**
  binary signed in with your own subscription (`./launch.sh`), or the **official Codex CLI** with "**Sign in with ChatGPT**"
  (`./launch-codex.sh`, reads `AGENTS.md`). We never see or store your credentials. Optional self-hosted web panel in `panel/`.
- **CelestIA Cloud:** €29/month + VAT, 3-day free trial, cloud Android and residential IP included —
  [app.celestia.meetqiu.com](https://app.celestia.meetqiu.com).

**Legal notice:** Tinder, Hinge, Bumble, Instagram and WhatsApp Terms of Service forbid or restrict automation; your
account or number may be suspended or banned. Use it only with your own accounts, at your own risk, and in compliance with
your local law (GDPR in the EU: chats contain other people's data). Provided "as is", without warranty. Treat the people on
the other side with respect.

Setup guide (Spanish): [docs/INSTALL.md](docs/INSTALL.md). License: MIT.
