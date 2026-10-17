#!/usr/bin/env bash
# Nextfix installieren (macOS und Linux), in einer Zeile:
#   curl -fsSL https://raw.githubusercontent.com/the-neyro/nextfix/main/scripts/install.sh | bash
#
# Prüft Python 3.12+, holt das neueste Release nach ~/nextfix (oder nutzt den Ordner, aus dem das Skript läuft),
# richtet .venv mit allen Paketen und Chromium ein, zeigt den Befehl für Claude Code und startet auf Wunsch
# Nextfix mit der Demo-Website.
# Einstellbar: NEXTFIX_DIR (Zielordner), NEXTFIX_REPO, NEXTFIX_BRANCH (z. B. main statt neuestem Release),
# NEXTFIX_START=ja|nein (ohne Rückfrage).
set -euo pipefail

REPO="${NEXTFIX_REPO:-https://github.com/the-neyro/nextfix.git}"
BRANCH="${NEXTFIX_BRANCH:-}"
ZIEL="${NEXTFIX_DIR:-$HOME/nextfix}"
PORT=8000
DEMO_PORT=8798

schritt() { printf '\n\033[1m%s\033[0m\n' "$*"; }
abbruch() { printf '\nFehler: %s\n' "$*" >&2; exit 1; }

# 1. Python 3.12 oder neuer finden
schritt "1/4 Python prüfen"
PY=""
for kandidat in python3.14 python3.13 python3.12 python3; do
  if command -v "$kandidat" >/dev/null 2>&1 &&
     "$kandidat" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
    PY="$(command -v "$kandidat")"
    break
  fi
done
if [ -z "$PY" ]; then
  if [ "$(uname)" = "Darwin" ]; then
    abbruch "Nextfix braucht Python 3.12 oder neuer. Installieren: https://www.python.org/downloads/ (oder: brew install python@3.12)"
  fi
  abbruch "Nextfix braucht Python 3.12 oder neuer, z. B.: sudo apt install python3.12 python3.12-venv"
fi
echo "$("$PY" --version) gefunden: $PY"

# 2. Ordner: läuft das Skript aus einem Nextfix-Ordner, wird der genutzt, sonst klonen bzw. aktualisieren
schritt "2/4 Nextfix holen"
SKRIPT="${BASH_SOURCE[0]:-}"
if [ -n "$SKRIPT" ] && [ -f "$SKRIPT" ] && [ -d "$(dirname "$SKRIPT")/../app/web" ]; then
  ZIEL="$(cd "$(dirname "$SKRIPT")/.." && pwd)"
  echo "Nutze vorhandenen Ordner: $ZIEL"
else
  command -v git >/dev/null 2>&1 || abbruch "git fehlt. macOS: xcode-select --install · Linux: sudo apt install git"
  # Standard: neuestes Release (höchstes Tag v…); ohne Release oder mit NEXTFIX_BRANCH: dieser Branch
  if [ -z "$BRANCH" ]; then
    BRANCH="$(git ls-remote --tags --refs --sort=-v:refname "$REPO" 'v*' 2>/dev/null | sed -n '1s|.*refs/tags/||p' || true)"
    [ -n "$BRANCH" ] || BRANCH=main
  fi
  if [ -d "$ZIEL/.git" ]; then
    # Tag oder Branch gezielt holen: der flache Klon kennt sonst nur den Stand, mit dem er angelegt wurde
    echo "Aktualisiere $ZIEL auf $BRANCH"
    git -C "$ZIEL" fetch --quiet --depth 1 origin "$BRANCH"
    git -C "$ZIEL" -c advice.detachedHead=false checkout --quiet --detach FETCH_HEAD
  elif [ -e "$ZIEL" ]; then
    abbruch "$ZIEL gibt es schon, ist aber kein Nextfix-Ordner. Anderen Ordner wählen: NEXTFIX_DIR=~/anderer-ordner"
  else
    echo "Hole Nextfix $BRANCH nach $ZIEL"
    git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$BRANCH" "$REPO" "$ZIEL"
  fi
fi
cd "$ZIEL"

# 3. Python-Umgebung mit allen Paketen und Chromium (für Ladezeit, PDF und JavaScript-Seiten)
schritt "3/4 Pakete einrichten (beim ersten Mal ein paar Minuten)"
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv || abbruch "Python-Umgebung ließ sich nicht anlegen. Linux: sudo apt install python3-venv"
fi
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
if ! .venv/bin/python -m playwright install chromium; then
  echo "Hinweis: Chromium fehlt. Website-Check läuft trotzdem, nur Ladezeit, PDF und JavaScript-Seiten nicht."
  echo "Später nachholen: .venv/bin/python -m playwright install --with-deps chromium"
fi

# 4. Startdatei bereitlegen und auf Wunsch gleich starten
schritt "4/4 Fertig"
if [ "$(uname)" = "Darwin" ] && [ -f "Nextfix starten.command" ]; then
  chmod +x "Nextfix starten.command"
  echo "Künftig starten: Doppelklick auf „Nextfix starten.command“ in $ZIEL"
else
  echo "Künftig starten: cd \"$ZIEL\" && .venv/bin/uvicorn app.web:app   → http://localhost:$PORT"
fi
echo
echo "Mit Claude Code verbinden (einmal, dann kennt Claude die Nextfix-Werkzeuge in jedem Ordner):"
echo "  claude mcp add --scope user seo-tool -e PYTHONPATH=\"$ZIEL\" -- \"$ZIEL/.venv/bin/python\" -m app.mcp_server"

START="${NEXTFIX_START:-}"
if [ -z "$START" ]; then
  if [ -r /dev/tty ] && { : </dev/tty; } 2>/dev/null; then
    printf '\nJetzt starten, mit Demo-Website zum Ausprobieren? [J/n] '
    read -r antwort </dev/tty || antwort="n"
    case "$antwort" in [nN]*) START=nein ;; *) START=ja ;; esac
  else
    START=nein
  fi
fi
[ "$START" = "ja" ] || exit 0

.venv/bin/python -m scripts.demo_website "$DEMO_PORT" >/dev/null 2>&1 &
DEMO=$!
.venv/bin/uvicorn app.web:app --port "$PORT" &
SERVER=$!
trap 'kill $DEMO $SERVER 2>/dev/null' EXIT
trap 'exit 0' INT TERM HUP
for _ in $(seq 1 30); do
  if curl -s -o /dev/null --max-time 1 "http://localhost:$PORT"; then
    if command -v open >/dev/null 2>&1; then open "http://localhost:$PORT"
    elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://localhost:$PORT" >/dev/null 2>&1 || true
    fi
    break
  fi
  sleep 1
done
echo
echo "Nextfix läuft auf http://localhost:$PORT"
echo "Demo-Website zum Ausprobieren: Projekt anlegen mit der Start-URL http://127.0.0.1:$DEMO_PORT/"
echo "Beenden: Ctrl+C"
wait $SERVER
