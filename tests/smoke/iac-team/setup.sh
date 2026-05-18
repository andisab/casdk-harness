#!/usr/bin/env bash
# Pre-run setup for the iac-team smoke fixture.
#
# Provisions the local infrastructure that the smoke run's eval graders
# need to validate AWS + Kubernetes IaC generation. Designed to be
# idempotent and locally-runnable.
#
# Invoked by `make smoke FIXTURE=iac-team`. Pair with teardown.sh.
#
# Default mode (no env vars set): no infrastructure is provisioned. The
# eval graders that work without a cluster — `terraform validate`,
# `helm lint --strict`, `kubeconform`, `trivy fs`, `trivy config`,
# `code_syntax`, `llm_judge` — are all the architect needs for the first
# pass. If the architect picks `kubectl --dry-run=server` or anything that
# hits a live cluster, the run will surface that as a defect and the next
# iteration can opt into kind via SMOKE_USE_KIND=1.
#
# Opt-in modes:
#   SMOKE_USE_KIND=1       — provision a kind cluster (real K8s API)
#   SMOKE_USE_LOCALSTACK=1 — provision a localstack container (AWS APIs)
#   SMOKE_USE_REAL_AWS=1   — sanity-check real AWS creds (no provisioning)
#
# Override with SMOKE_SKIP_SETUP=1 to bypass this script entirely (the
# Makefile handles that gate; this script does not need to re-check).

set -euo pipefail

echo "==> iac-team smoke: pre-run setup"

# ---------------------------------------------------------------------------
# 1. Tooling sanity check (always runs)
# ---------------------------------------------------------------------------
# These CLIs need to be on PATH **inside the main-agent container** —
# the graders run there, not on the host. The Dockerfile installs them
# (see agents/main/Dockerfile § "IaC eval tooling"); this is a probe to
# catch image-build drift, not a hard gate (some graders will work even
# if a subset is missing).
#
# I1 fix: probe inside the container via `docker compose exec` so we
# report what the graders will actually see. Falls back to host-side
# probing if the container isn't running (e.g. user is running setup.sh
# in isolation for debugging). The host-side check is informational
# only — the graders don't run on the host.

probe_inside_container() {
    local tool="$1"
    # `command` is a shell builtin, not an executable; wrap in `sh -c`
    # so `docker exec` can find it.  Bare `docker exec -T main-agent
    # command -v X` fails with "command: executable not found in PATH".
    docker compose exec -T main-agent sh -c "command -v '$tool'" >/dev/null 2>&1
}

# Decide probe scope: use the container if it's running, otherwise fall
# back to the host (with a header that says so).
if docker compose ps main-agent 2>/dev/null | grep -q 'running\|Up'; then
    probe_scope="container"
    probe_cmd="probe_inside_container"
else
    probe_scope="host (container not running — fallback probe)"
    probe_cmd="command -v"
fi

echo "    Probing for IaC graders' required CLIs in: $probe_scope"
missing_tools=()
for tool in kubectl helm terraform trivy kubeconform; do
    if ! $probe_cmd "$tool" >/dev/null 2>&1; then
        missing_tools+=("$tool")
    fi
done

if [ "${#missing_tools[@]}" -gt 0 ]; then
    echo "    WARN: missing CLI tools in $probe_scope: ${missing_tools[*]}"
    echo "          (eval graders that need them will fail; rebuild the"
    echo "           harness image with 'make build' if running in container)"
else
    echo "    All required CLIs present (kubectl, helm, terraform, trivy, kubeconform)"
fi

# ---------------------------------------------------------------------------
# 2. kind cluster (opt-in via SMOKE_USE_KIND=1)
# ---------------------------------------------------------------------------
# kind runs a real Kubernetes control plane inside a Docker container.
# Generated manifests can be applied with `kubectl --dry-run=server` for
# server-side validation. NOT enabled by default — the IaC graders the
# eval-architect is likely to pick (terraform validate, helm lint,
# kubeconform) all work without a live cluster.

if [ "${SMOKE_USE_KIND:-0}" = "1" ]; then
    if ! command -v kind >/dev/null 2>&1; then
        echo "    ERROR: SMOKE_USE_KIND=1 but kind is not installed."
        echo "           Install: https://kind.sigs.k8s.io/docs/user/quick-start/"
        exit 1
    fi
    if kind get clusters 2>/dev/null | grep -qx "casdk-smoke-iac"; then
        echo "    kind cluster 'casdk-smoke-iac' already exists; reusing"
    else
        echo "    Creating kind cluster 'casdk-smoke-iac' (~30-60s)..."
        kind create cluster --name casdk-smoke-iac --image kindest/node:v1.31.0
    fi
    kubectl config use-context kind-casdk-smoke-iac
    export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
    echo "    KUBECONFIG=$KUBECONFIG"
else
    echo "    Skipping kind (set SMOKE_USE_KIND=1 to enable)"
fi

# ---------------------------------------------------------------------------
# 3. localstack (opt-in via SMOKE_USE_LOCALSTACK=1)
# ---------------------------------------------------------------------------
# Localstack emulates AWS APIs on http://localhost:4566. Generated
# Terraform can target it via the `endpoints` block. Free CE edition is
# sufficient for syntax / dry-run grading; EKS-specific calls need Pro.

if [ "${SMOKE_USE_LOCALSTACK:-0}" = "1" ]; then
    if ! command -v docker >/dev/null 2>&1; then
        echo "    ERROR: SMOKE_USE_LOCALSTACK=1 but docker is not on PATH"
        exit 1
    fi
    if docker ps --filter "name=casdk-smoke-localstack" --format '{{.Names}}' \
       | grep -qx "casdk-smoke-localstack"; then
        echo "    localstack container already running; reusing"
    else
        echo "    Starting localstack container..."
        docker run -d --rm \
            --name casdk-smoke-localstack \
            -p 4566:4566 \
            -e SERVICES=s3,iam,ec2,eks,ecr,sts,cloudformation \
            localstack/localstack:3.4 >/dev/null
        echo "    Waiting for localstack to become ready..."
        for _ in $(seq 1 30); do
            if curl -fsS http://localhost:4566/_localstack/health >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
    fi
    export AWS_ENDPOINT_URL="http://localhost:4566"
    echo "    AWS_ENDPOINT_URL=$AWS_ENDPOINT_URL"
else
    echo "    Skipping localstack (set SMOKE_USE_LOCALSTACK=1 to enable)"
fi

# ---------------------------------------------------------------------------
# 4. Real AWS creds (opt-in via SMOKE_USE_REAL_AWS=1)
# ---------------------------------------------------------------------------
# Sanity-check that AWS creds work. No provisioning — graders that hit
# AWS need to be expensive-tolerant when this branch is on.

if [ "${SMOKE_USE_REAL_AWS:-0}" = "1" ]; then
    if ! command -v aws >/dev/null 2>&1; then
        echo "    ERROR: SMOKE_USE_REAL_AWS=1 but aws CLI is not on PATH"
        exit 1
    fi
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        echo "    ERROR: SMOKE_USE_REAL_AWS=1 but aws sts get-caller-identity failed"
        exit 1
    fi
    echo "    Real AWS creds verified: $(aws sts get-caller-identity --query Account --output text)"
fi

echo "==> iac-team smoke: setup complete"
