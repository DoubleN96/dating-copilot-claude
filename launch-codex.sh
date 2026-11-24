#!/usr/bin/env bash
# Igual que launch.sh pero con Codex CLI oficial de OpenAI e «Iniciar sesión con ChatGPT» (lee AGENTS.md -> CLAUDE.md).
# Primera vez: npm i -g @openai/codex && HOME=$(pwd) codex login   (elige «Sign in with ChatGPT»)
# Sin canal de Telegram: le hablas en la propia terminal (tmux) y ronda.sh le teclea las rondas igual.
set -e
export HOME="$(cd "$(dirname "$0")" && pwd)"
set -a; . "$HOME/config.env"; set +a
cd "$HOME"
exec codex
