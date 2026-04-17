#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
cd project
python manage.py migrate
python manage.py collectstatic --noinput
