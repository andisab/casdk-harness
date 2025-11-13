NOTE: 
This is a guidance file for OpenAI Codex (the equivalent of CLAUDE.md for Claude). 

# Repository Guidelines

## Project Structure & Module Organization
- `src/harness/` contains the CLI, agent orchestration, monitoring hooks, and config utilities.
- `src/mcp_servers/` keeps MCP adapters (`docker/`, `git/`, etc.); add new servers in their own folder with an `__init__.py`.
- `agents/` stores Docker build contexts for each agent; keep custom scripts and assets beside the agent Dockerfile.
- `tests/` separates suites into `unit/`, `integration/`, `e2e/`, and shared fixtures via `fixtures/` and `conftest.py`.
- `config/`, `workspace/`, `memory/`, and `logs/` hold runtime configuration, working artifacts, and model checkpoints.

## Build, Test, and Development Commands
- `make install-deps` installs Python tooling locally with `uv`.
- `make init` seeds `.env`, workspace directories, and checkpoint storage; run once per machine.
- `make dev` launches the Dockerized dev stack with hot reload; use `make dev-detached` to background it.
- `make build` rebuilds all services, while `make build-main` targets the main agent only.
- `make test`, `make test-unit`, `make test-integration`, `make test-e2e`, or `make test-smoke` run the matching Pytest suites.
- `make lint`, `make format`, `make typecheck`, and `make coverage` execute Ruff lint/format, MyPy, and coverage reporting.

## Coding Style & Naming Conventions
- Python 3.11+, 4-space indentation, snake_case for modules/functions, PascalCase for classes, and UPPER_SNAKE_CASE for constants.
- Keep public APIs type hinted and add docstrings when behaviour is not obvious; align with Ruff and MyPy rules in `pyproject.toml`.

## Testing Guidelines
- Pytest drives all suites; decorators `@pytest.mark.integration`, `e2e`, and `smoke` scope longer runs. Use `pytest -m integration` before altering CI pipelines.
- Add unit coverage for harness logic and place MCP or Docker flow tests under `tests/integration/`.
- Track coverage with `make coverage` and keep results above the CI threshold.

## Commit & Pull Request Guidelines
- Follow the repository’s Conventional Commit + emoji pattern (`✨ feat: ...`, `🔧 chore: ...`); include a concise scope when helpful.
- Squash incidental commits locally and ensure messages describe the user impact plus any linked issue (`Fixes #123`).
- PRs must document test commands, highlight config or schema updates, and attach screenshots or logs for UX changes.

## Environment & Agent Configuration
- Manage secrets through `.env` (created by `make init`) and document new variables in `.env.example` and `docs/`.
- Keep agent state within `workspace/` and `memory/`; update `config/` and `docker-compose.*.yml` alongside code whenever services change.
