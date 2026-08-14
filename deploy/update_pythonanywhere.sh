#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PAW_PROJECT_DIR:-/home/monografiaspn/monografia-spn}"
cd "$PROJECT_DIR"

BACKUP_DIR="${PAW_BACKUP_DIR:-$PROJECT_DIR/backups}"
mkdir -p "$BACKUP_DIR" "$PROJECT_DIR/media"
if [[ -f "$PROJECT_DIR/db.sqlite3" ]]; then
  cp "$PROJECT_DIR/db.sqlite3" "$BACKUP_DIR/db.sqlite3.$(date +%Y%m%d-%H%M%S)"
fi

git pull --ff-only
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy

echo "Atualização concluída. Recarregue o Web App no painel do PythonAnywhere."
