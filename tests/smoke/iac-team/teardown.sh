#!/usr/bin/env bash
# Post-run cleanup for the iac-team smoke fixture.
#
# Runs unconditionally (PASS or FAIL) so smoke runs leave no residue on
# host or container state. Best-effort — surface failures but never abort.
#
# Set SMOKE_KEEP_RESOURCES=1 to skip teardown when you want to poke
# around the cluster / localstack after a failure.

set -uo pipefail   # NOT -e — best-effort cleanup

echo "==> iac-team smoke: post-run teardown"

if [ "${SMOKE_KEEP_RESOURCES:-0}" = "1" ]; then
    echo "    SMOKE_KEEP_RESOURCES=1; skipping teardown"
    echo "    Resources left running (if started):"
    echo "      - kind cluster 'casdk-smoke-iac' (delete: kind delete cluster --name casdk-smoke-iac)"
    echo "      - localstack 'casdk-smoke-localstack' (delete: docker rm -f casdk-smoke-localstack)"
    exit 0
fi

# ---------------------------------------------------------------------------
# 1. kind cluster — delete if present
# ---------------------------------------------------------------------------
if command -v kind >/dev/null 2>&1; then
    if kind get clusters 2>/dev/null | grep -qx "casdk-smoke-iac"; then
        echo "    Deleting kind cluster 'casdk-smoke-iac'..."
        kind delete cluster --name casdk-smoke-iac || \
            echo "    (kind delete returned non-zero; continuing)"
    fi
fi

# ---------------------------------------------------------------------------
# 2. localstack container — stop if running
# ---------------------------------------------------------------------------
if command -v docker >/dev/null 2>&1; then
    if docker ps -a --filter "name=casdk-smoke-localstack" --format '{{.Names}}' \
       | grep -qx "casdk-smoke-localstack"; then
        echo "    Removing localstack container..."
        docker rm -f casdk-smoke-localstack >/dev/null 2>&1 || \
            echo "    (docker rm returned non-zero; continuing)"
    fi
fi

# ---------------------------------------------------------------------------
# 3. Workspace artifacts
# ---------------------------------------------------------------------------
# By default we keep workspace/iac-team/ after the run so the operator
# can inspect artifacts, transcripts, and eval results. The next
# `make smoke FIXTURE=iac-team` overwrites it cleanly.
#
# To force a wipe here, set SMOKE_WIPE_WORKSPACE=1.

if [ "${SMOKE_WIPE_WORKSPACE:-0}" = "1" ]; then
    echo "    SMOKE_WIPE_WORKSPACE=1; removing workspace/iac-team/"
    rm -rf workspace/iac-team
fi

echo "==> iac-team smoke: teardown complete"
