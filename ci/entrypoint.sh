#!/usr/bin/env sh

set -e

./manage.py migrate --noinput
./manage.py loaddata fixtures/categories.json
./manage.py loaddata fixtures/subcategories.json
./manage.py loaddata fixtures/currencies.json
./manage.py loaddata fixtures/message_maps.json

# Запуск команды
./manage.py runserver 0.0.0.0:8000
