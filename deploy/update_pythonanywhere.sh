#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PAW_PROJECT_DIR:-/home/monografiaspn/monografia-spn}"
cd "$PROJECT_DIR"

git pull --ff-only
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy

echo "Atualização concluída. Recarregue o Web App no painel do PythonAnywhere."
