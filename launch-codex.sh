#!/usr/bin/env bash
# Igual que launch.sh pero con Codex CLI oficial de OpenAI e «Iniciar sesión con ChatGPT» (lee AGENTS.md).
# Primera vez: npm i -g @openai/codex && HOME=$(pwd) codex login   (elige «Sign in with ChatGPT»)
# El inicio de sesión queda en ./.codex/ (está en .gitignore: no lo subas nunca).
# Sin Telegram ni hooks: le hablas en la terminal (tmux) y SIEMPRE propone y espera tu «ok» (ver AGENTS.md).
# Escribe solo dentro de esta carpeta, con red (navegador CDP, adb, Evolution) y sin pedir permiso por cada comando.
set -e
export HOME="$(cd "$(dirname "$0")" && pwd)"
set -a; . "$HOME/config.env"; set +a
cd "$HOME"
exec codex --sandbox workspace-write -c sandbox_workspace_write.network_access=true --ask-for-approval never
