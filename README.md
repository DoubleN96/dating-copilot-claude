# dating-copilot-claude

**Tu copiloto de citas con Claude Code.** Lee tus matches de Tinder, Hinge y Bumble, contesta con *tu* estilo,
propone planes en *tus* sitios y solo en *tus* huecos libres, los apunta en tu Google Calendar y te lo cuenta
todo por Telegram. Tú decides si propone y esperas tu «ok», o si va solo con límites y botón de pausa.

> ⚠️ **Léelo antes.** Los términos de uso de Tinder, Hinge y Bumble **prohíben la automatización**. Usar esto
> puede hacer que **te baneen la cuenta**. Úsalo solo con tu propia cuenta y bajo tu responsabilidad. Al otro
> lado hay personas: el bot está configurado para **no negar nunca que es una IA**, no mentir sobre ti, no
> presionar y respetar un no. Si eso no te encaja, este repo no es para ti.

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
| Estilo y técnicas | `citas/estilo.md`, `citas/tecnicas_videos.md`, `citas/tecnicas_dani_ribelles.md`, `citas/rutas_ejemplo.md` |
| Pantalla remota del Android | `tools/pantalla.py` |

Todo lo personal va en `config.env` (a partir de `config.example.env`) y en `citas/rutas.md`; ninguno se sube a git.

## Empezar

Guía completa, con lo que falla y por qué: **[docs/INSTALL.md](docs/INSTALL.md)**.

```bash
git clone https://github.com/DoubleN96/dating-copilot-claude.git ~/copiloto && cd ~/copiloto
cp config.example.env config.env && cp citas/rutas_ejemplo.md citas/rutas.md   # rellena los dos
# edita CLAUDE.md (tu nombre, filtros, modo) y personaliza estilo.md §3 con tu voz
tmux new -s copiloto ./launch.sh
```

Requisitos: Claude Code, un bot de Telegram, Linux con Docker (≥3 GB de RAM libres para el Android), una máquina
en casa para la IP residencial y Python 3.9+ (`pip install websockets`).

## Limitaciones honestas

- Los conectores de Android leen la pantalla por coordenadas (pantalla de 720 px): **una actualización de la app
  puede romperlos**. `ui.sh dump` es tu amigo.
- Captchas, logins, 2FA y pagos los haces tú. El bot no paga nada nunca.
- Los SMS con «<#>» (Bumble/Hinge) a menudo no llegan al reenviador.
- El estilo de ejemplo es de una persona concreta en español de España: **cámbialo por el tuyo** o sonarás a otro.

---

## English summary

**dating-copilot-claude** turns Claude Code into a dating assistant driven from Telegram. It reads your Tinder
(web, via Chrome DevTools Protocol), Hinge and Bumble (Android 13 in Docker via redroid + adb) matches, drafts or
sends replies in your own style using technique manuals distilled from dating-advice videos (with manipulative
techniques explicitly excluded), proposes dates only at your venues and free calendar slots, books them in Google
Calendar and moves the conversation to WhatsApp/Instagram; on WhatsApp (optional, self-hosted Evolution API) it keeps
chatting until the date is locked in, only in handed-over chats, and steps aside as soon as you write there yourself. Traffic goes out through your home IP.
Safeguards: Telegram "pause" kill switch, per-minute and per-day caps, a send log, a daily summary and
human-like timing. The bot is instructed to never deny being an AI.

**Warning:** Tinder, Hinge and Bumble Terms of Service forbid automation; your account may be banned.
Automating a personal WhatsApp also breaches WhatsApp's Terms and may get your number banned. Use it only
with your own account, at your own risk, and treat the people on the other side with respect.
Setup guide (Spanish): [docs/INSTALL.md](docs/INSTALL.md). License: MIT.
