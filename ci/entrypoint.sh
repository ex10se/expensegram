#!/usr/bin/env sh

set -e

# Накатывание миграций
alembic upgrade head

# Запуск сервера
python3 start_bot.py
