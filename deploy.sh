#!/usr/bin/env sh
# Single-command deploy, runnable by hand on the host or from the CI deploy
# job: get the image, run migrations, restart, verify health.
#
# The image is PRIVATE on GHCR, so this host must be logged in before it can
# deploy. One time, as the user that runs this script:
#
#     echo <TOKEN> | docker login ghcr.io -u <github-username> --password-stdin
#
# where <TOKEN> is a classic personal access token with the read:packages
# scope. Docker stores it in ~/.docker/config.json, so it survives reboots.
set -eu

COMPOSE="docker compose -f docker-compose.prod.yml"
IMAGE="${IMAGE:-ghcr.io/galirousa/oposdocs:latest}"

# A failed pull used to fall through to a local build. That is the wrong
# default now the image is private: a missing or expired login would quietly
# turn every deploy into a full image build on the machine that is serving
# traffic, and hide the credential problem instead of reporting it.
if ! pull_log=$($COMPOSE pull 2>&1); then
    printf '%s\n' "$pull_log" >&2
    if printf '%s' "$pull_log" | grep -qiE 'denied|unauthori[sz]ed|authentication required|forbidden|403'; then
        cat >&2 <<'MSG'

Registry authentication failed, and the image is private.

Log this host in to GHCR, then re-run the deploy:

    echo <TOKEN> | docker login ghcr.io -u <github-username> --password-stdin

<TOKEN> is a classic personal access token with the read:packages scope.
Building locally would not fix a credential problem, so stopping here.
MSG
        exit 1
    fi
    if [ "${ALLOW_LOCAL_BUILD:-0}" = "1" ]; then
        echo "Registry unreachable - building $IMAGE locally (ALLOW_LOCAL_BUILD=1)." >&2
        docker build --target runtime -t "$IMAGE" .
    else
        cat >&2 <<'MSG'

Could not pull the image, and this does not look like an auth failure.

If the registry is genuinely unreachable and you want this host to build the
image itself (it will compete with serving traffic), re-run as:

    ALLOW_LOCAL_BUILD=1 ./deploy.sh
MSG
        exit 1
    fi
fi

$COMPOSE run --rm web python manage.py migrate --noinput
$COMPOSE run --rm web python manage.py sync_roles
$COMPOSE up -d
sleep 5
$COMPOSE exec -T web curl -fs http://localhost:8000/healthz
echo "Deploy OK"
