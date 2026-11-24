#!/usr/bin/env bash
set -euo pipefail

cd /var/home/shay0129/Code/Projects/leadflow-ai

# Default to a reserved non-routable test domain so Gmail/Brave is never touched unless an email is explicitly passed
if [[ -n "${1:-}" ]]; then
  EMAIL="$1"
  echo "Using explicit email address: ${EMAIL}"
else
  EMAIL="e2e-$(date +%s)@example.com"
  echo "No email specified — using non-routable test address: ${EMAIL} (skipping Gmail/Brave)"
fi

LOG_FILE="$(mktemp)"
FIFO_PATH="$(mktemp -u)"
mkfifo "$FIFO_PATH"

cleanup() {
  exec 3>&- 2>/dev/null || true
  rm -f "$LOG_FILE" "$FIFO_PATH"
}
trap cleanup EXIT

python3 -u scripts/e2e_prod_smoke.py --email "$EMAIL" < "$FIFO_PATH" > "$LOG_FILE" 2>&1 &
TEST_PID=$!
tail -n +1 -f "$LOG_FILE" --pid="$TEST_PID" &

exec 3>"$FIFO_PATH"

for _ in $(seq 1 40); do
  if grep -q "Enter the 6-digit OTP" "$LOG_FILE"; then
    break
  fi
  sleep 0.5
done

OTP=$(ssh -n hetzner-tunnel "podman exec leadflow-backend python3 -c '
import sys
from src.database.models import User
from src.database.session import get_db

db = next(get_db())
user = db.query(User).filter(User.email == sys.argv[1].lower()).first()
print(user.otp_code if user and user.otp_code else \"\")
' '$EMAIL'" | tr -d '\r\n')

if [[ ! "$OTP" =~ ^[0-9]{6}$ ]]; then
  echo "ERROR: Invalid or empty OTP retrieved from database: '${OTP}'" >&2
  kill "$TEST_PID" 2>/dev/null || true
  wait "$TEST_PID" 2>/dev/null || true
  exit 1
fi

echo "Injected decrypted OTP from Hetzner DB: ${OTP}"
printf '%s\n' "$OTP" >&3
exec 3>&-

wait "$TEST_PID"
