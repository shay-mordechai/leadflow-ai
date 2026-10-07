#!/usr/bin/env bash

set -Eeuo pipefail

CONTAINER_NAME="${DB_CONTAINER_NAME:-leadflow-backend}"
R2_BUCKET="${R2_BUCKET:?Set R2_BUCKET to the destination bucket name}"
R2_ENDPOINT_URL="${R2_ENDPOINT_URL:?Set R2_ENDPOINT_URL to the Cloudflare R2 S3 endpoint}"
R2_PREFIX="${R2_PREFIX:-database-backups}"

for command in podman gzip aws mktemp date; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'Required command is unavailable: %s\n' "$command" >&2
        exit 1
    fi
done

if [[ "$(podman inspect --format '{{.State.Running}}' "$CONTAINER_NAME")" != "true" ]]; then
    printf 'Database container is not running: %s\n' "$CONTAINER_NAME" >&2
    exit 1
fi

image_id="$(podman inspect --format '{{.Image}}' "$CONTAINER_NAME")"
image_sha="${image_id#sha256:}"
if [[ ! "$image_sha" =~ ^[[:xdigit:]]{12,}$ ]]; then
    printf 'Container returned an invalid image SHA: %s\n' "$image_id" >&2
    exit 1
fi

timestamp="$(date -u '+%Y%m%dT%H%M%SZ')"
filename="db_backup_${timestamp}_image_${image_sha}.sql.gz"
temporary_file="$(mktemp "${TMPDIR:-/tmp}/${filename}.XXXXXX")"
trap 'rm -f -- "$temporary_file"' EXIT

if ! podman exec "$CONTAINER_NAME" sh -c \
    'test -n "${DATABASE_URL:-}" && command -v pg_dump >/dev/null 2>&1'; then
    printf 'Container must provide DATABASE_URL and pg_dump.\n' >&2
    exit 1
fi

podman exec "$CONTAINER_NAME" sh -c \
    'case "$DATABASE_URL" in
        postgresql+asyncpg://*) DATABASE_URL="postgresql://${DATABASE_URL#postgresql+asyncpg://}" ;;
        postgresql+psycopg2://*) DATABASE_URL="postgresql://${DATABASE_URL#postgresql+psycopg2://}" ;;
        postgres+psycopg2://*) DATABASE_URL="postgresql://${DATABASE_URL#postgres+psycopg2://}" ;;
    esac
    export DATABASE_URL
    exec pg_dump --no-owner --no-acl "$DATABASE_URL"' |
    gzip -c >"$temporary_file"

object_key="${filename}"
if [[ -n "$R2_PREFIX" ]]; then
    object_key="${R2_PREFIX#/}/${filename}"
fi

aws s3 cp "$temporary_file" \
    "s3://${R2_BUCKET%/}/${object_key}" \
    --endpoint-url "$R2_ENDPOINT_URL" \
    --only-show-errors

printf 'Uploaded %s to Cloudflare R2 bucket %s.\n' "$filename" "$R2_BUCKET"
