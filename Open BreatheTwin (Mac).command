#!/bin/bash
# Double-click (Mac) or run "bash 'Open BreatheTwin (Mac).command'" (Linux) to open the BreatheTwin dashboard.
# First run: creates a private Python environment in .venv and installs the packages (a few minutes, once).
# Close this window (or press Ctrl+C) to stop the dashboard.
cd "$(dirname "$0")" || exit 1

PY=""
for c in python3.13 python3.12 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "BreatheTwin needs Python 3.12 or newer. Install it from https://www.python.org/downloads/ and run this again."
  read -r -p "Press Enter to close." _
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "First run: installing the packages BreatheTwin needs (a few minutes, once)..."
  "$PY" -m venv .venv || { echo "Could not create the Python environment."; read -r -p "Press Enter to close." _; exit 1; }
  .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt || {
    rm -rf .venv; echo "Installation did not finish. Check your internet connection and try again."
    read -r -p "Press Enter to close." _; exit 1; }
fi

( sleep 6; if command -v open >/dev/null 2>&1; then open http://localhost:8501; else xdg-open http://localhost:8501 >/dev/null 2>&1; fi ) &
echo "Starting BreatheTwin at http://localhost:8501 (close this window to stop it)..."
exec .venv/bin/python -m streamlit run app/dashboard.py
