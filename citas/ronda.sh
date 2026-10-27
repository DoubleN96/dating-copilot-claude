#!/bin/bash
# Bucle del copiloto (cron horario; la hora local la decide aquí TZ_NAME porque el cron suele ir en UTC).
#   ronda.sh          -> a las 10,12,14,16,18,20,22 h (hora local) le teclea la ronda si está libre
#   ronda.sh ya       -> igual pero sin mirar la hora (pruebas)
#   ronda.sh resumen  -> a las 23 h (hora local) manda al dueño el resumen del día
C=$(cd "$(dirname "$0")" && pwd); [ -f "$C/../config.env" ] && { set -a; . "$C/../config.env"; set +a; }
S=${TMUX_SESSION:-copiloto}; PY=${PYTHON:-python3}; H=$(TZ=${TZ_NAME:-Europe/Madrid} date +%H); log(){ echo "$(date -Is) $*"; }
if [ "$1" = resumen ]; then [ "$H" = 23 ] && $PY $C/envio.py resumen; exit 0; fi
[ "$1" = ya ] || case $H in 10|12|14|16|18|20|22) ;; *) exit 0;; esac
[ -e $C/PAUSA ] && { log "en PAUSA, sin ronda"; exit 0; }
exec 9>/tmp/copiloto-ronda.lock; flock -n 9 || { log "otra ronda.sh en marcha"; exit 0; }
P=$(tmux capture-pane -p -t $S 2>/dev/null) || { log "no hay tmux $S"; exit 0; }
echo "$P" | grep -q "esc to interrupt" && { log "ocupada (ronda u otra tarea en curso)"; exit 0; }
echo "$P" | grep -E '^❯ .+' | grep -vq '^❯ Try "' && { log "hay texto a medio escribir en su prompt"; exit 0; }
tmux send-keys -t $S -l "Ronda: usa la skill revisar-y-responder (apps y WhatsApp: whatsapp.py nuevos y chats) y likes-diarios"; sleep 1
tmux send-keys -t $S Enter
log "ronda lanzada"
