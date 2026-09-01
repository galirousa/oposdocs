#!/usr/bin/env sh
# Single-command deploy, runnable by hand on the host or from the CI deploy
# job: pull the new image, run migrations, restart, verify health.
set -eu

COMPOSE="docker compose -f docker-compose.prod.yml"

$COMPOSE pull
$COMPOSE run --rm web python manage.py migrate --noinput
$COMPOSE run --rm web python manage.py sync_roles
$COMPOSE up -d
sleep 5
$COMPOSE exec -T web curl -fs http://localhost:8000/healthz
echo "Deploy OK"
