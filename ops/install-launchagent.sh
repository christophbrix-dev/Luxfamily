#!/bin/bash
#
# Install (or re-install) the LaunchAgent that crawls three times a day.
#
# Run it from anywhere; it works out where the repository is from its own
# location. Safe to run again — it replaces what is there, it does not stack.
#
#   ops/install-launchagent.sh            # install or update
#   ops/install-launchagent.sh --remove   # take it out again
#   ops/install-launchagent.sh --status   # what is loaded, and when it ran
#
# Why a LaunchAgent and not the server's own scheduler: the scheduler lives in
# the server process, which on this machine only runs while a terminal is open.
# It was switched on correctly on 2026-09-30 and had not run once by the next
# morning. launchd keeps the schedule instead, and catches up a time that
# passed while the Mac was asleep.

set -euo pipefail

LABEL="lu.luxfamily.importers"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$REPO/ops/$LABEL.plist.template"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"

PYTHON="$REPO/backend/.venv/bin/python"
SCRIPT="$REPO/backend/run_importers.py"
WORKDIR="$REPO/backend"
LOGDIR="$HOME/Library/Logs/Luxfamily"
LOG="$LOGDIR/importers.log"

# launchctl needs the per-user domain spelled out, otherwise bootstrap in a
# non-login context silently targets the wrong one.
DOMAIN="gui/$(id -u)"

say() { printf '%s\n' "$*"; }

remove() {
  if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
    launchctl bootout "$DOMAIN/$LABEL"
    say "ausgeladen: $LABEL"
  else
    say "war nicht geladen: $LABEL"
  fi
  if [[ -f "$TARGET" ]]; then
    rm "$TARGET"
    say "gelöscht:   $TARGET"
  fi
  say ""
  say "Das Logfile bleibt stehen: $LOG"
}

status() {
  say "Label:   $LABEL"
  say "plist:   $TARGET"
  say "Log:     $LOG"
  say ""
  if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
    # The three lines worth having: is it loaded, how often has it run, did the
    # last run fail. Everything else in `launchctl print` is noise here.
    #
    # Anchored to a single leading tab on purpose. The job's own keys sit at
    # that depth; deeper down there are nested "state = active" lines for the
    # endpoints, and an unanchored grep printed those too — so the status said
    # "not running" and then "active" twice, which reads like a contradiction.
    launchctl print "$DOMAIN/$LABEL" \
      | grep -E "^\t(state|runs|last exit code) = " \
      | sed 's/^[[:space:]]*/  /' || true
  else
    say "  NICHT geladen."
  fi
  say ""
  if [[ -f "$LOG" ]]; then
    say "Letzte Zeilen aus dem Log:"
    tail -n 6 "$LOG" | sed 's/^/  /'
  else
    say "Noch kein Log — der Job hat noch nie gelaufen."
  fi
}

install() {
  [[ -f "$TEMPLATE" ]] || { say "Vorlage fehlt: $TEMPLATE"; exit 1; }
  [[ -x "$PYTHON"   ]] || { say "Kein Python in der venv: $PYTHON"; exit 1; }
  [[ -f "$SCRIPT"   ]] || { say "Skript fehlt: $SCRIPT"; exit 1; }

  mkdir -p "$LOGDIR" "$HOME/Library/LaunchAgents"

  # Every __PLACEHOLDER__ in the template has to be listed here. The offline
  # test test_launchagent_template.py compares the two lists, because one
  # forgotten placeholder gives a job that points at a file called
  # "__PYTHON__" and then fails three times a day without telling anybody.
  sed -e "s|__PYTHON__|$PYTHON|g" \
      -e "s|__SCRIPT__|$SCRIPT|g" \
      -e "s|__WORKDIR__|$WORKDIR|g" \
      -e "s|__LOG__|$LOG|g" \
      "$TEMPLATE" > "$TARGET"

  if grep -q "__" "$TARGET"; then
    say "FEHLER: in der erzeugten Datei stehen noch Platzhalter:"
    grep -n "__" "$TARGET" | sed 's/^/  /'
    rm "$TARGET"
    exit 1
  fi

  # plutil parses it the way launchd will. A plist that launchd rejects is
  # loaded as "nothing", and `launchctl bootstrap` says almost the same thing
  # either way — so check before, not after.
  plutil -lint "$TARGET" >/dev/null

  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  launchctl bootstrap "$DOMAIN" "$TARGET"

  say "installiert: $TARGET"
  say "Zeiten:      05:00, 12:00, 18:00 (verpasste Termine holt launchd beim Aufwachen nach)"
  say "Log:         $LOG"
  say ""
  say "Einmal von Hand auslösen, um es zu sehen:"
  say "  launchctl kickstart -p $DOMAIN/$LABEL"
}

case "${1:-}" in
  --remove) remove ;;
  --status) status ;;
  "")       install ;;
  *)        say "Unbekannte Option: $1"; say "Erlaubt: --remove, --status, oder keine."; exit 1 ;;
esac
