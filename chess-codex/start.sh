#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# 1️⃣ venv erstellen falls nicht vorhanden
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# 2️⃣ venv aktivieren
source .venv/bin/activate

# 3️⃣ pip aktualisieren
python -m pip install --upgrade pip

# 4️⃣ requirements installieren (nur wenn Datei existiert)
if [ -f "requirements.txt" ]; then
  echo "Installing requirements..."
  pip install -r requirements.txt
fi

# 5️⃣ Applikation starten
echo "Starting application..."
exec python __main__.py "$@"
