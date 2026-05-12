#!/usr/bin/env bash
# Post-run cleanup for the iac-team smoke fixture.
#
# Runs unconditionally (PASS or FAIL) so smoke runs leave no residue on
# host or container state. Set SMOKE_KEEP_RESOURCES=1 to skip teardown
# when you want to poke around the cluster after a failure.

set -uo pipefail   # NOT -e — best-effort cleanup; surface failures but continue

echo "==> iac-team smoke: post-run teardown"

if [ "${SMOKE_KEEP_RESOURCES:-0}" = "1" ]; then
    echo "==> SMOKE_KEEP_RESOURCES=1; skipping teardown (cluster + localstack left running)"
    exit 0
fi

# --- 1. kind cluster ---
# TODO: delete the smoke cluster. Tolerate "not found" — a setup failure
# may have skipped cluster creation.
#
# kind delete cluster --name casdk-smoke-iac 2>/dev/null || true

# --- 2. localstack ---
# TODO: stop and remove the localstack container.
#
# docker rm -f casdk-smoke-localstack 2>/dev/null || true

# --- 3. Workspace artifacts ---
#
# By default we keep workspace/iac-team/ after the run so the operator
# can inspect artifacts, transcripts, and eval results. The next
# `make smoke FIXTURE=iac-team` overwrites it cleanly.
#
# To force a wipe here, set SMOKE_WIPE_WORKSPACE=1.
#
# if [ "${SMOKE_WIPE_WORKSPACE:-0}" = "1" ]; then
#     rm -rf workspace/iac-team
# fi

echo "==> iac-team smoke: teardown scaffolding present; TODO blocks pending"
