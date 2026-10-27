#!/usr/bin/env bash
# Arranca el copiloto: sesión de Claude Code con HOME aislado + canal de Telegram.
# Uso: tmux new -s copiloto '/ruta/al/HOME_AISLADO/launch.sh'
set -e
export HOME="$(cd "$(dirname "$0")" && pwd)"   # este directorio ES el HOME aislado (CLAUDE.md, citas/, .claude/)
set -a; . "$HOME/config.env"; set +a
export DISABLE_AUTOUPDATER=1
cd "$HOME"
# --dangerously-skip-permissions: el bot trabaja desatendido. Úsalo SOLO en una máquina/usuario dedicado
# y con los hooks de helpers/ activos (ver docs/INSTALL.md §1). Sin él, tendrás que aprobar cada comando.
exec claude --channels plugin:telegram@claude-plugins-official --dangerously-skip-permissions
