#!/usr/bin/env bash
# Pre-run setup for the iac-team smoke fixture.
#
# Provisions the local infrastructure that the smoke run's eval graders
# need to validate AWS + Kubernetes IaC generation. Designed to be idempotent
# and locally-runnable (no cloud account required by default; optional real-AWS
# mode via SMOKE_USE_REAL_AWS=1).
#
# Invoked by `make smoke FIXTURE=iac-team`. Pair with teardown.sh, which
# the smoke runner calls regardless of test outcome.
#
# This file is currently a SCAFFOLD — it documents the intended setup but
# does not yet install or start the dependencies. Fill in the TODO sections
# before the iac-team smoke can actually grade against live infrastructure.

set -euo pipefail

echo "==> iac-team smoke: pre-run setup"

# --- 1. kind (Kubernetes IN Docker) cluster ---
#
# kind spins a real K8s control plane inside a Docker container. The
# generated K8s/Helm/Argo manifests can be applied with `kubectl --dry-run=client`
# or fully `apply`'d for higher-fidelity grading.
#
# TODO: provision a kind cluster named "casdk-smoke-iac" with a recent K8s version.
# Skip if a cluster of that name already exists (idempotent).
# Reference: https://kind.sigs.k8s.io/docs/user/quick-start/#installation
#
# kind create cluster --name casdk-smoke-iac --image kindest/node:v1.31.0 || true
# kubectl config use-context kind-casdk-smoke-iac

# --- 2. localstack (AWS API emulator) ---
#
# Localstack runs AWS service emulators (S3, IAM, EKS, ECR, ...) on
# http://localhost:4566. Generated Terraform can target localstack via the
# `endpoints` block; `aws` CLI commands work with --endpoint-url=...
#
# TODO: start a localstack container with the AWS services this fixture exercises
# (s3, iam, ec2, eks, ecr, sts, cloudformation). The free CE edition covers
# enough surface for syntax/dry-run validation.
# Reference: https://docs.localstack.cloud/getting-started/installation/
#
# docker run -d --rm \
#     --name casdk-smoke-localstack \
#     -p 4566:4566 \
#     -e SERVICES=s3,iam,ec2,eks,ecr,sts,cloudformation \
#     localstack/localstack:3.4

# --- 3. Optional: real AWS (when SMOKE_USE_REAL_AWS=1) ---
#
# When the user has cloud credentials and wants higher-fidelity grading,
# this branch verifies that the credentials work (cheap call) and exports
# the necessary env vars for downstream graders.
#
# if [ "${SMOKE_USE_REAL_AWS:-0}" = "1" ]; then
#     aws sts get-caller-identity > /dev/null \
#         || { echo "AWS creds invalid"; exit 1; }
# fi

# --- 4. Tooling check ---
#
# These CLIs must be on PATH inside the main-agent container for eval graders
# to function. The harness Dockerfile installs them; this is a sanity probe.
#
# for tool in kubectl helm terraform tfsec trivy kubeconform; do
#     command -v "$tool" >/dev/null \
#         || { echo "WARN: $tool not on PATH; some graders will fail"; }
# done

echo "==> iac-team smoke: setup scaffolding present; TODO blocks pending"
echo "==> Set SMOKE_SKIP_SETUP=1 to bypass this script entirely"
