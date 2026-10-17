#!/bin/bash
# Nextfix per Doppelklick starten (macOS): Server starten, Browser öffnen.
# Fenster schließen oder Ctrl+C beendet Nextfix.

cd "$(dirname "$0")" || exit 1
PORT="${NEXTFIX_PORT:-8000}"
ADRESSE="http://localhost:$PORT"

laeuft() { curl -s -o /dev/null --max-time 1 "$ADRESSE"; }

# Läuft schon (zweiter Doppelklick)? Dann nur den Browser öffnen.
if laeuft; then
  echo "Nextfix läuft schon, öffne $ADRESSE"
  open "$ADRESSE"
  exit 0
fi

# Erster Start: Python-Umgebung einrichten (dauert ein paar Minuten, nur einmal)
if [ ! -x .venv/bin/uvicorn ]; then
  if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
    echo "Nextfix braucht Python 3.12 oder neuer: https://www.python.org/downloads/"
    read -r -p "Enter drücken zum Schließen …"
    exit 1
  fi
  echo "Erster Start: richte Nextfix ein (einmalig, ein paar Minuten) …"
  python3 -m venv .venv &&
    .venv/bin/pip install -q -r requirements.txt &&
    .venv/bin/playwright install chromium || {
      echo "Einrichtung fehlgeschlagen, siehe Meldungen oben."
      read -r -p "Enter drücken zum Schließen …"
      exit 1
    }
fi

echo "Starte Nextfix … (zum Beenden dieses Fenster schließen oder Ctrl+C)"
.venv/bin/uvicorn app.web:app --port "$PORT" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
trap 'exit 0' INT TERM HUP

# Warten, bis der Server antwortet, dann Browser öffnen
for _ in $(seq 1 30); do
  if laeuft; then
    open "$ADRESSE"
    break
  fi
  if ! kill -0 $SERVER 2>/dev/null; then
    echo "Nextfix ließ sich nicht starten, siehe Meldungen oben."
    read -r -p "Enter drücken zum Schließen …"
    exit 1
  fi
  sleep 1
done

wait $SERVER
