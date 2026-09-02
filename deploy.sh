#!/usr/bin/env sh
# Single-command deploy, runnable by hand on the host or from the CI deploy
# job: get the image (pull, or build locally when the registry is
# unreachable), run migrations, restart, verify health.
set -eu

COMPOSE="docker compose -f docker-compose.prod.yml"
IMAGE="${IMAGE:-ghcr.io/galirousa/oposdocs:latest}"

# Prefer the CI-published image. If it cannot be pulled (private GHCR package
# or no registry access), build the same tag from the checked-out source.
if ! $COMPOSE pull; then
    echo "Registry pull failed - building $IMAGE locally."
    docker build --target runtime -t "$IMAGE" .
fi

$COMPOSE run --rm web python manage.py migrate --noinput
$COMPOSE run --rm web python manage.py sync_roles
$COMPOSE up -d
sleep 5
$COMPOSE exec -T web curl -fs http://localhost:8000/healthz
echo "Deploy OK"
