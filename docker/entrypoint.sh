#!/bin/sh
set -e

# Wait for Postgres
python - <<'PY'
import os, time
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.db import connection
from django.db.utils import OperationalError

for i in range(30):
    try:
        connection.ensure_connection()
        print("database: ready")
        break
    except OperationalError:
        print(f"database: waiting ({i+1}/30)...")
        time.sleep(2)
else:
    raise SystemExit("database not ready")
PY

python manage.py migrate --noinput

case "$1" in
  web)
    python manage.py runserver 0.0.0.0:8000
    ;;
  worker)
    celery -A config worker -l info
    ;;
  beat)
    celery -A config beat -l info
    ;;
  *)
    exec "$@"
    ;;
esac
