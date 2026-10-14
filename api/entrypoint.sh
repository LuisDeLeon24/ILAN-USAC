#!/bin/sh
set -eu
cd /src/api
alembic upgrade head
exec "$@"
