#!/usr/bin/env bash
# Clean Docker Compose runtime proof for Drake AI Trading Phase 1.
# This script is intentionally read-only after startup: it verifies runtime
# behavior and writes evidence; it never changes trading mode or credentials.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

EVIDENCE_DIR="${RUNTIME_EVIDENCE_DIR:-runtime-evidence}"
mkdir -p "$EVIDENCE_DIR"

collect_evidence() {
  docker compose ps --format json >"$EVIDENCE_DIR/compose-ps.json" 2>&1 || true
  docker compose logs --no-color >"$EVIDENCE_DIR/compose.log" 2>&1 || true
  docker image ls >"$EVIDENCE_DIR/docker-images.txt" 2>&1 || true
}
trap collect_evidence EXIT

run_capture() {
  local name="$1"
  shift
  "$@" >"$EVIDENCE_DIR/$name" 2>&1
}

require_json() {
  local file="$1"
  local description="$2"
  python3 - "$file" "$description" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
description = sys.argv[2]
data = json.loads(path.read_text())

assert data["health"]["components"]["database"]["status"] == "healthy", "database must be healthy"
assert data["health"]["components"]["redis"]["status"] == "healthy", "redis must be healthy"
assert data["health"]["components"]["api"]["status"] == "healthy", "api must be healthy"

# The current Compose architecture intentionally has no standalone worker
# service. It must report this honestly rather than being presented as healthy.
workers = data["health"]["components"]["workers"]
assert workers["status"] == "degraded", f"workers status changed: {workers}"
assert "No worker probe registered" in workers["detail"], workers

# Broker credentials are intentionally absent in Phase 1; this is the only
# external integration allowed to be unconfigured during the runtime proof.
broker = data["health"]["components"]["broker"]
assert broker["status"] == "degraded", f"broker should be unconfigured: {broker}"
assert "No broker probe registered" in broker["detail"], broker

# A market-data readiness degradation is not an approved Phase 1 exception.
# Keep this assertion strict so a gate failure is visible in CI evidence.
market_data = data["health"]["components"]["market_data"]
assert market_data["status"] == "healthy", (
    f"{description}: market-data health must be healthy, received {market_data}"
)
PY
}

printf 'Drake AI Trading Phase 1 runtime verification\n' | tee "$EVIDENCE_DIR/verification-header.txt"
run_capture docker-version docker version
run_capture docker-compose-version docker compose version
run_capture compose-config docker compose config

# Reproducible clean start: no retained data volume or orphaned containers.
docker compose down --remove-orphans --volumes

docker compose build --no-cache
docker compose up -d

# Wait up to two minutes for liveness and dependency readiness.
for attempt in $(seq 1 60); do
  if curl --fail --silent --show-error http://localhost:8000/health >"$EVIDENCE_DIR/health.json" 2>"$EVIDENCE_DIR/health.err" && \
     curl --fail --silent --show-error http://localhost:8000/api/v1/infrastructure/deployment/readiness >"$EVIDENCE_DIR/readiness.json" 2>"$EVIDENCE_DIR/readiness.err"; then
    if python3 - "$EVIDENCE_DIR/readiness.json" <<'PY'
import json
import sys
payload = json.load(open(sys.argv[1]))
assert payload["ready"] is True, payload
assert payload["checks"]["database"] is True, payload
assert payload["checks"]["redis"] is True, payload
assert payload["checks"]["migrations_applied"] is True, payload
PY
    then
      break
    fi
  fi
  if [[ "$attempt" == "60" ]]; then
    echo "API did not become ready within 120 seconds." >&2
    exit 1
  fi
  sleep 2
done

curl --fail --silent --show-error http://localhost:8000/api/v1/health/full >"$EVIDENCE_DIR/health-full.json"
curl --fail --silent --show-error http://localhost:8000/api/v1/monitoring/health >"$EVIDENCE_DIR/overview-health.json"
curl --fail --silent --show-error http://localhost:8000/api/v1/infrastructure/deployment/config >"$EVIDENCE_DIR/deployment-config.json"
curl --fail --silent --show-error http://localhost:8000/api/v1/settings/ >"$EVIDENCE_DIR/settings.json"

# Verify that migrations performed the documented bootstrap, without mutating
# the database. The three required instruments and singleton settings row must
# exist after a clean first start.
docker compose exec -T postgres psql -U drake -d drake_trading -Atc \
  "SELECT symbol FROM instruments WHERE symbol IN ('ES', 'MES', 'NQ', 'MNQ') ORDER BY symbol;" \
  >"$EVIDENCE_DIR/seeded-instruments.txt"
docker compose exec -T postgres psql -U drake -d drake_trading -Atc \
  "SELECT id || ':' || trading_mode FROM application_settings WHERE id = 1;" \
  >"$EVIDENCE_DIR/bootstrap-settings.txt"
docker compose exec -T api alembic current >"$EVIDENCE_DIR/alembic-current.txt"
# Capture startup logs before asserting the migration completion contract; the
# EXIT trap captures a final copy as well, including logs from any failure.
docker compose logs --no-color >"$EVIDENCE_DIR/compose.log" 2>&1

python3 - "$EVIDENCE_DIR" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
health = json.loads((out / "health.json").read_text())
assert health == {"status": "ok"}, health

config = json.loads((out / "deployment-config.json").read_text())
assert config["valid"] is True, config
assert config["checks"]["database_url"] is True, config
assert config["checks"]["redis_url"] is True, config
assert config["checks"]["secret_key_set"] is True, config
assert config["checks"]["trading_mode"] == "PAPER", config
assert config["checks"]["live_allowed"] is False, config

settings = json.loads((out / "settings.json").read_text())
assert settings["trading_mode"] == "PAPER", settings

instruments = (out / "seeded-instruments.txt").read_text().split()
assert instruments == ["ES", "MES", "MNQ", "NQ"], instruments
assert (out / "bootstrap-settings.txt").read_text().strip() == "1:PAPER"
assert "Migrations complete." in (out / "compose.log").read_text()
PY

# This validates the exact monitoring payload consumed by the Overview page.
require_json "$EVIDENCE_DIR/overview-health.json" "Overview monitoring payload"
require_json "$EVIDENCE_DIR/health-full.json" "Full health payload"

echo "PASS: clean Docker runtime verification completed." | tee "$EVIDENCE_DIR/verdict.txt"
