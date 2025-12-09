"""Autonomous development mode entry point.

This module provides the main loop for autonomous development sessions.
It manages the transition between initializer mode (Tech Lead Q&A) and
continuation mode (Coding Agent).

Usage:
    python -m harness.autonomous [--model MODEL] [--allow-all-commands]

Modes:
    - Initializer: When no task_list.json exists, runs Tech Lead Q&A
    - Continuation: When task_list.json exists, runs Coding Agent
"""

import argparse
import asyncio
import hashlib
import json
import re
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from rich.console import Console
from rich.prompt import Prompt

from harness.agent import AgentSession
from harness.cli import parse_and_print_message
from harness.config import get_config
from harness.progress import (
    ProgressManager,
    QASession,
    SessionData,
    TaskList,
    WorkspaceConfig,
    WorkspaceState,
)

# Load prompts from files
PROMPTS_DIR = Path(__file__).parent / "prompts"

logger = structlog.get_logger(__name__)


def load_prompt(prompt_name: str) -> str:
    """Load a prompt from the prompts directory.

    Args:
        prompt_name: Name of prompt file (without .md extension)

    Returns:
        Prompt content as string
    """
    prompt_path = PROMPTS_DIR / f"{prompt_name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")

    with open(prompt_path) as f:
        return f.read()


class AutonomousRunner:
    """Main runner for autonomous development sessions."""

    def __init__(
        self,
        workspace_dir: Path,
        model: str | None = None,
    ) -> None:
        """Initialize the autonomous runner.

        Args:
            workspace_dir: Directory for development work
            model: Claude model to use (defaults to config)
        """
        self.workspace_dir = workspace_dir
        self.model = model
        self.config = get_config()
        self.progress_manager = ProgressManager(workspace_dir)
        self._shutdown_requested = False
        self._shutdown_event: asyncio.Event | None = None
        self.console = Console()
        # Workspace config to be persisted in task_list.json (set by external repo handler)
        self._pending_workspace_config: WorkspaceConfig | None = None

    def _setup_signal_handlers(self) -> None:
        """Set up async signal handlers in the running event loop.

        Must be called from within an async context (e.g., run()).
        Uses loop.add_signal_handler() for proper async signal handling.
        """
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._handle_signal(s)),
            )
        logger.debug("Async signal handlers installed", signals=["SIGINT", "SIGTERM"])

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signals asynchronously.

        Args:
            sig: The signal that was received
        """
        sig_name = sig.name if hasattr(sig, "name") else str(sig)
        logger.info("Shutdown signal received", signal=sig_name)
        self._shutdown_requested = True

        # Set event to wake up any waiting coroutines
        if self._shutdown_event is not None:
            self._shutdown_event.set()

    def _init_context_directory(self) -> None:
        """Initialize the context directory with template files.

        Creates /workspace/context/ with architecture.md, decisions.md,
        issues.md, and next-steps.md if they don't exist.
        """
        context_dir = self.workspace_dir / "context"
        context_dir.mkdir(exist_ok=True)

        # Template files with YAML front matter
        templates = {
            "architecture.md": """\
---
type: architecture
created: {timestamp}
updated: {timestamp}
updated_by: session-0
tags: [system-design, overview]
---

# System Architecture

## Overview

*Describe the high-level system architecture here.*

## Key Components

*List and briefly describe the main components.*

## Dependencies

*List external dependencies and integrations.*
""",
            "decisions.md": """\
---
type: decisions
created: {timestamp}
updated: {timestamp}
updated_by: session-0
tags: [log, append-only]
---

# Technical Decisions Log

*Append new decisions here. Never delete entries.*

""",
            "issues.md": """\
---
type: issues
created: {timestamp}
updated: {timestamp}
updated_by: session-0
tags: [blockers, bugs]
---

# Known Issues

*Track active blockers and bugs here. Remove when resolved.*

""",
            "next-steps.md": """\
---
type: next-steps
created: {timestamp}
updated: {timestamp}
updated_by: session-0
tags: [priorities, focus]
---

# Next Steps

*Focus areas for the next session.*

## Immediate Priorities

1. *First priority*
2. *Second priority*

## Notes for Next Session

*Any important context for continuing work.*
""",
        }

        timestamp = datetime.now(UTC).isoformat()

        for filename, template in templates.items():
            file_path = context_dir / filename
            if not file_path.exists():
                content = template.format(timestamp=timestamp)
                with open(file_path, "w") as f:
                    f.write(content)
                logger.debug("Created context file", path=str(file_path))

    # --- Workspace State Detection ---

    def _detect_workspace_state(self) -> tuple[WorkspaceState, dict[str, Any]]:
        """Detect the current workspace state.

        Analyzes the workspace directory to determine what state it's in:
        - EMPTY: Only SPEC.md exists or workspace is empty
        - WORK_IN_PROGRESS: task_list.json exists with incomplete tasks
        - COMPLETED: task_list.json exists with all tasks done
        - CONFLICT: Multiple SPEC.md or task_list.json files found
        - EXTERNAL_REPO: Git repo exists without our files (cloned repo)
        - MIXED: Files exist but no git repo

        Returns:
            Tuple of (state, context_dict) where context_dict contains
            relevant information about the detected state.
        """
        context: dict[str, Any] = {}

        # Check for conflicting files (State D)
        spec_files = list(self.workspace_dir.glob("**/SPEC.md"))
        task_list_files = list(self.workspace_dir.glob("**/task_list.json"))

        if len(spec_files) > 1 or len(task_list_files) > 1:
            context["spec_files"] = [str(f) for f in spec_files]
            context["task_list_files"] = [str(f) for f in task_list_files]
            return WorkspaceState.CONFLICT, context

        # Check for existing task list
        has_task_list = self.progress_manager.has_task_list()
        has_git = (self.workspace_dir / ".git").is_dir()
        has_spec = (self.workspace_dir / "SPEC.md").exists()

        # Get workspace contents (excluding hidden files and sessions dir)
        workspace_contents = [
            f
            for f in self.workspace_dir.iterdir()
            if not f.name.startswith(".") and f.name != "sessions"
        ]

        if has_task_list:
            task_list = self.progress_manager.load_task_list()
            stats = task_list.get_completion_stats()
            context["task_list"] = task_list
            context["stats"] = stats

            if stats["remaining"] == 0:
                return WorkspaceState.COMPLETED, context
            return WorkspaceState.WORK_IN_PROGRESS, context

        # No task_list.json - check other states
        if has_git and not has_spec:
            # External repo (State E) - git repo without our files
            context["remote_url"] = self._get_git_remote_url()
            context["current_branch"] = self._get_current_branch()
            return WorkspaceState.EXTERNAL_REPO, context

        # Count non-SPEC files (excluding context directory and hidden files)
        non_spec_files = [
            f
            for f in workspace_contents
            if f.name != "SPEC.md" and f.name != "context"
        ]

        if not has_git and len(non_spec_files) > 0:
            # Mixed state (State F) - files exist but no git
            context["files"] = [f.name for f in non_spec_files[:10]]
            return WorkspaceState.MIXED, context

        # Empty or only SPEC.md (State A)
        context["has_spec"] = has_spec
        return WorkspaceState.EMPTY, context

    # --- Git Helper Methods ---

    def _get_git_remote_url(self) -> str | None:
        """Get the git remote URL for origin."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def _get_current_branch(self) -> str | None:
        """Get the current git branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def _run_git_init(self) -> bool:
        """Initialize a git repository in the workspace.

        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "init"],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("Git repository initialized", path=str(self.workspace_dir))
                return True
            logger.error("Git init failed", stderr=result.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error("Git init exception", error=str(e))
        return False

    def _ensure_branch(self, branch_name: str) -> bool:
        """Ensure we're on the specified branch, creating if needed.

        Args:
            branch_name: Name of branch to switch to or create

        Returns:
            True if successful, False otherwise
        """
        current = self._get_current_branch()
        if current == branch_name:
            logger.info("Already on branch", branch=branch_name)
            return True

        try:
            # Check if branch exists
            result = subprocess.run(
                ["git", "rev-parse", "--verify", branch_name],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                # Branch exists, checkout
                checkout_result = subprocess.run(
                    ["git", "checkout", branch_name],
                    cwd=self.workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if checkout_result.returncode == 0:
                    logger.info("Switched to existing branch", branch=branch_name)
                    return True
            else:
                # Create and checkout new branch
                checkout_result = subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    cwd=self.workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if checkout_result.returncode == 0:
                    logger.info("Created and switched to branch", branch=branch_name)
                    return True

            logger.error("Failed to switch branch", stderr=checkout_result.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error("Branch switch exception", error=str(e))
        return False

    def _parse_branch_from_spec(self) -> str | None:
        """Parse branch name from SPEC.md file.

        Looks for a line like 'branch: casdk-feature-name'

        Returns:
            Branch name if found, None otherwise
        """
        spec_path = self.workspace_dir / "SPEC.md"
        if not spec_path.exists():
            return None

        try:
            content = spec_path.read_text()
            # Look for branch: casdk-xxx pattern
            match = re.search(r"^branch:\s*(casdk-[\w-]+)", content, re.MULTILINE)
            if match:
                return match.group(1)
        except OSError:
            pass
        return None

    def _get_or_prompt_branch_name(self) -> str | None:
        """Get branch name from SPEC.md or prompt user.

        Returns:
            Branch name if provided, None if user cancels
        """
        # First try to get from SPEC.md
        branch = self._parse_branch_from_spec()
        if branch:
            return branch

        # Prompt user
        self.console.print(
            "\n[yellow]No branch specified in SPEC.md.[/yellow]\n"
            "Branch naming convention: casdk-{feature-name}"
        )

        try:
            branch_name = Prompt.ask(
                "Enter branch name (or 'cancel' to exit)",
                default="casdk-feature",
            )

            if branch_name.lower() == "cancel":
                return None

            if not branch_name.startswith("casdk-"):
                branch_name = f"casdk-{branch_name}"

            return branch_name
        except (KeyboardInterrupt, EOFError):
            return None

    # --- Workspace State Handlers ---

    async def _handle_workspace_state(
        self, state: WorkspaceState, context: dict[str, Any]
    ) -> bool:
        """Handle the detected workspace state.

        Args:
            state: Detected workspace state
            context: Context dict from detection

        Returns:
            True if should proceed, False if should exit
        """
        handlers = {
            WorkspaceState.EMPTY: self._handle_empty_workspace,
            WorkspaceState.WORK_IN_PROGRESS: self._handle_wip_workspace,
            WorkspaceState.COMPLETED: self._handle_completed_workspace,
            WorkspaceState.CONFLICT: self._handle_conflict_workspace,
            WorkspaceState.EXTERNAL_REPO: self._handle_external_repo,
            WorkspaceState.MIXED: self._handle_mixed_workspace,
        }
        handler = handlers.get(state)
        if handler:
            return await handler(context)
        return True

    async def _handle_empty_workspace(self, context: dict[str, Any]) -> bool:
        """Handle State A: Empty workspace.

        Initializes git repo and proceeds to initializer mode.
        """
        logger.info("Empty workspace detected, initializing git repository")

        # Initialize git repo
        if not self._run_git_init():
            self.console.print(
                "[red]Failed to initialize git repository. Please check permissions.[/red]"
            )
            return False

        if not context.get("has_spec"):
            self.console.print(
                "\n[yellow]No SPEC.md found. The Tech Lead will help you create one.[/yellow]\n"
            )

        return True

    async def _handle_wip_workspace(self, context: dict[str, Any]) -> bool:
        """Handle State B: Work in progress.

        Logs progress and continues normally.
        """
        stats = context.get("stats", {})
        self.console.print(
            f"\n[green]Resuming work: {stats.get('passed', 0)}/{stats.get('total_tasks', 0)} "
            f"tasks complete[/green]\n"
        )
        return True

    async def _handle_completed_workspace(self, context: dict[str, Any]) -> bool:
        """Handle State C: All tasks completed.

        Prompts user to review or archive.
        """
        stats = context.get("stats", {})
        self.console.print(
            f"\n[bold green]All {stats.get('total_tasks', 0)} tasks completed![/bold green]\n"
            "\nOptions:\n"
            "  1. Archive and start new project (run 'make reset-workspace')\n"
            "  2. Continue to review/finalize\n"
        )

        try:
            response = Prompt.ask(
                "Continue reviewing?",
                choices=["y", "n"],
                default="n",
            )
            return response.lower() == "y"
        except (KeyboardInterrupt, EOFError):
            return False

    async def _handle_conflict_workspace(self, context: dict[str, Any]) -> bool:
        """Handle State D: Conflicting files.

        Refuses to proceed and requires manual cleanup.
        """
        self.console.print(
            "\n[bold red]ERROR: Conflicting workspace state detected[/bold red]\n"
        )

        spec_files = context.get("spec_files", [])
        task_list_files = context.get("task_list_files", [])

        if len(spec_files) > 1:
            self.console.print("Multiple SPEC.md files found:")
            for f in spec_files:
                self.console.print(f"  - {f}")

        if len(task_list_files) > 1:
            self.console.print("\nMultiple task_list.json files found:")
            for f in task_list_files:
                self.console.print(f"  - {f}")

        self.console.print(
            "\n[yellow]Please delete or rename the duplicate files and run again.[/yellow]"
        )
        return False

    async def _handle_external_repo(self, context: dict[str, Any]) -> bool:
        """Handle State E: External repository.

        Prompts user to work on the repo or clean workspace.
        """
        remote_url = context.get("remote_url", "unknown")
        current_branch = context.get("current_branch", "unknown")

        self.console.print(
            f"\n[cyan]External repository detected[/cyan]\n"
            f"  Remote: {remote_url}\n"
            f"  Branch: {current_branch}\n"
        )

        try:
            response = Prompt.ask(
                "Work on this repository or clean workspace?",
                choices=["work", "clean"],
                default="work",
            )

            if response == "clean":
                self.console.print(
                    "\n[yellow]Please run 'make reset-workspace' to clean.[/yellow]\n"
                )
                return False

            # Get or prompt for branch name
            branch_name = self._get_or_prompt_branch_name()
            if not branch_name:
                self.console.print("\n[yellow]No branch specified. Exiting.[/yellow]\n")
                return False

            # Ensure we're on the correct branch
            if not self._ensure_branch(branch_name):
                self.console.print(
                    f"\n[red]Failed to switch to branch '{branch_name}'[/red]\n"
                )
                return False

            # Store workspace config for persistence in task_list.json
            self._pending_workspace_config = WorkspaceConfig(
                type="external",
                branch=branch_name,
                remote_url=remote_url,
                initialized_from=self._get_spec_hash(),
            )

            self.console.print(
                f"\n[green]Ready to work on branch '{branch_name}'[/green]\n"
            )
            return True

        except (KeyboardInterrupt, EOFError):
            return False

    async def _handle_mixed_workspace(self, context: dict[str, Any]) -> bool:
        """Handle State F: Mixed state.

        Warns user and asks about cleanup.
        """
        files = context.get("files", [])

        self.console.print(
            f"\n[yellow]Workspace contains files but no git repository:[/yellow]\n"
            f"  Files: {', '.join(files[:5])}"
            f"{'...' if len(files) > 5 else ''}\n"
        )

        try:
            response = Prompt.ask(
                "Initialize git and continue, or clean workspace?",
                choices=["continue", "clean"],
                default="continue",
            )

            if response == "clean":
                self.console.print(
                    "\n[yellow]Please run 'make reset-workspace' to clean.[/yellow]\n"
                )
                return False

            # Initialize git repo
            if not self._run_git_init():
                self.console.print(
                    "[red]Failed to initialize git repository.[/red]"
                )
                return False

            return True

        except (KeyboardInterrupt, EOFError):
            return False

    def _get_spec_hash(self) -> str:
        """Get hash of SPEC.md to detect changes."""
        spec_path = self.workspace_dir / "SPEC.md"
        if not spec_path.exists():
            return "no_spec"
        with open(spec_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def _get_qa_session_path(self) -> Path:
        """Get path to QA session file."""
        return self.workspace_dir / "qa_session.json"

    def _load_qa_session(self) -> QASession | None:
        """Load QA session from file if exists and valid."""
        qa_path = self._get_qa_session_path()
        if not qa_path.exists():
            return None

        try:
            with open(qa_path) as f:
                data = json.load(f)
            session = QASession.from_dict(data)

            # Check if spec has changed
            current_hash = self._get_spec_hash()
            if session.spec_hash != current_hash:
                logger.info(
                    "SPEC.md changed since last session, starting fresh",
                    old_hash=session.spec_hash,
                    new_hash=current_hash,
                )
                return None

            return session
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Invalid QA session file, starting fresh", error=str(e))
            return None

    def _save_qa_session(self, session: QASession) -> None:
        """Save QA session to file."""
        qa_path = self._get_qa_session_path()
        with open(qa_path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)
        logger.debug("QA session saved", path=str(qa_path))

    def _delete_qa_session(self) -> None:
        """Delete QA session file after completion."""
        qa_path = self._get_qa_session_path()
        if qa_path.exists():
            qa_path.unlink()
            logger.debug("QA session file deleted")

    def _create_qa_session(self) -> QASession:
        """Create a new QA session."""
        return QASession(
            started_at=datetime.now(UTC).isoformat(),
            spec_hash=self._get_spec_hash(),
        )

    def _parse_question_progress(
        self, content: str, qa_session: QASession
    ) -> None:
        """Parse question progress signals from agent output.

        Updates qa_session with parsed values.
        """
        # Parse [QUESTIONS_PLANNED: N] to get total
        if "[QUESTIONS_PLANNED:" in content:
            match = re.search(r"\[QUESTIONS_PLANNED:\s*(\d+)\]", content)
            if match:
                qa_session.total_questions = int(match.group(1))
                logger.debug(
                    "Questions planned", total=qa_session.total_questions
                )

        # Parse "Question X/Y" to track progress
        question_match = re.search(r"\*\*Question\s+(\d+)/(\d+)\*\*", content)
        if question_match:
            qa_session.current_question = int(question_match.group(1))
            qa_session.total_questions = int(question_match.group(2))
            logger.debug(
                "Question progress",
                current=qa_session.current_question,
                total=qa_session.total_questions,
            )

    def _get_mode(self) -> str:
        """Determine the current mode based on state.

        Returns:
            'initializer' or 'continuation'
        """
        if self.progress_manager.has_task_list():
            return "continuation"
        return "initializer"

    def _build_initializer_prompt(self, qa_session: QASession | None = None) -> str:
        """Build the prompt for initializer mode.

        Args:
            qa_session: Optional QA session for resume context
        """
        base_prompt = load_prompt("initializer")
        tech_lead_prompt = load_prompt("tech_lead")

        # Check for existing spec
        spec_path = self.workspace_dir / "SPEC.md"
        spec_content = ""
        if spec_path.exists():
            with open(spec_path) as f:
                spec_content = f.read()

        prompt = f"""{base_prompt}

---

## Tech Lead Capabilities

{tech_lead_prompt}

---

## Current Specification

"""
        if spec_content:
            prompt += f"File: SPEC.md\n\n```markdown\n{spec_content}\n```\n"
        else:
            prompt += "No SPEC.md found. Please describe the project requirements.\n"

        # Add resume context if available
        if qa_session and qa_session.is_resumable():
            prompt += f"""

---

## Resuming Previous Session

A previous Q&A session was interrupted. Here is the conversation history:

**Progress**: Question {qa_session.current_question}/{qa_session.total_questions}

### Previous Conversation

"""
            for msg in qa_session.conversation_history:
                role = "Tech Lead" if msg["role"] == "assistant" else "User"
                prompt += f"**{role}**: {msg['content']}\n\n"

            prompt += """---

Continue from where you left off. Do NOT re-ask questions that were already answered.
Resume with the next question in the sequence.
"""

        return prompt

    def _build_continuation_prompt(self) -> str:
        """Build the prompt for continuation mode."""
        base_prompt = load_prompt("continuation")

        # Load current state
        task_list = self.progress_manager.load_task_list()

        # Get task stats from task list and session totals
        task_stats = task_list.get_completion_stats()
        totals = self.progress_manager.get_totals()
        next_task = task_list.get_next_task()

        prompt = f"""{base_prompt}

---

## Current State

**Project**: {task_list.project_name}
**Version**: {task_list.version}
**Created**: {task_list.created_at}

### Progress
- **Total Tasks**: {task_stats['total_tasks']}
- **Passed**: {task_stats['passed']} ({task_stats['completion_percent']:.1f}%)
- **Failed**: {task_stats['failed']}
- **Remaining**: {task_stats['remaining']}
- **Total Sessions**: {totals['total_sessions']}
- **Total Cost**: ${totals['total_cost_usd']:.4f}

### Current Task
"""
        if next_task:
            prompt += f"""
**ID**: {next_task.id}
**Title**: {next_task.title}
**Priority**: {next_task.priority}
**Description**: {next_task.description}

**Acceptance Criteria**:
"""
            for i, criterion in enumerate(next_task.acceptance_criteria, 1):
                prompt += f"{i}. {criterion}\n"
        else:
            prompt += "\n**All tasks completed!** Review and finalize the project.\n"

        # Add recent session summaries
        all_sessions = self.progress_manager.load_all_sessions()
        if all_sessions:
            prompt += "\n### Recent Sessions\n"
            for session in all_sessions[-3:]:  # Last 3 sessions
                prompt += f"\n**Session {session.session_number}** ({session.started_at})\n"
                prompt += f"- Passed: {', '.join(session.tasks_passed) or 'None'}\n"
                prompt += f"- Failed: {', '.join(session.tasks_failed) or 'None'}\n"
                if session.notes:
                    prompt += f"- Notes: {session.notes[:200]}...\n"

        return prompt

    def _extract_content_str(self, message: object) -> str:
        """Extract string content from a message object.

        Args:
            message: Message object from SDK

        Returns:
            String representation of message content
        """
        raw_content = getattr(message, "content", None)
        if raw_content is None:
            return str(message)
        elif isinstance(raw_content, list):
            # Handle multi-block content (e.g., text + tool_use)
            return "\n".join(str(block) for block in raw_content)
        else:
            return str(raw_content)

    def _check_completion_signals(
        self,
        content: str,
        session: SessionData,
        task_list: "TaskList | None" = None,
    ) -> tuple[bool, bool]:
        """Check message content for task completion signals.

        Args:
            content: Message content to check
            session: Session data to update
            task_list: Task list to update status (for continuation mode)

        Returns:
            Tuple of (task_completed, task_blocked)
        """
        task_completed = False
        task_blocked = False

        # Check for task list ready (initializer mode)
        if "[TASK_LIST_READY]" in content:
            task_completed = True
            logger.info("Task list ready signal received")

        # Check for task complete (continuation mode)
        if "[TASK_COMPLETE:" in content:
            match = re.search(r"\[TASK_COMPLETE:\s*(task-\d+)\]", content)
            if match:
                task_id = match.group(1)
                if task_id not in session.tasks_passed:
                    session.tasks_passed.append(task_id)
                if task_id not in session.tasks_worked:
                    session.tasks_worked.append(task_id)
                # Update task status in task_list
                if task_list:
                    task_list.update_task_status(task_id, "PASS")
                task_completed = True
                logger.info("Task completed", task_id=task_id)

        # Check for task blocked
        if "[TASK_BLOCKED:" in content:
            match = re.search(r"\[TASK_BLOCKED:\s*(task-\d+):\s*(.+?)\]", content)
            if match:
                task_id = match.group(1)
                blocked_reason = match.group(2)
                if task_id not in session.tasks_failed:
                    session.tasks_failed.append(task_id)
                if task_id not in session.tasks_worked:
                    session.tasks_worked.append(task_id)
                # Update task status in task_list
                if task_list:
                    task_list.update_task_status(task_id, "FAIL")
                task_blocked = True
                logger.info("Task blocked", task_id=task_id, reason=blocked_reason)

        # Check for git commits
        if "[COMMIT:" in content:
            # Pattern: [COMMIT: hash: message] or [COMMIT: hash]
            for match in re.finditer(r"\[COMMIT:\s*([a-f0-9]+)(?::\s*(.+?))?\]", content):
                commit_hash = match.group(1)
                commit_msg = match.group(2) or ""
                commit_entry = f"{commit_hash}: {commit_msg}" if commit_msg else commit_hash
                if commit_entry not in session.git_commits:
                    session.git_commits.append(commit_entry)
                    logger.info("Commit recorded", hash=commit_hash, message=commit_msg)

        return task_completed, task_blocked

    async def _run_initializer_session(
        self,
        prompt: str,
        session: SessionData,
        qa_session: QASession,
    ) -> tuple[bool, str]:
        """Run an interactive Tech Lead Q&A session.

        This mode allows human interaction - the agent asks questions,
        waits for user responses, and iterates until task_list.json is ready.

        Args:
            prompt: System prompt for the session
            session: Session data to track stats
            qa_session: QA session for progress tracking and persistence

        Returns:
            Tuple of (task_list_ready, session_content)
        """
        agent_name = "autonomous-initializer"
        session_content: list[str] = []
        task_list_ready = False
        is_resuming = qa_session.is_resumable()

        # Display header with progress if available
        self.console.print(
            "\n[bold cyan]╔══════════════════════════════════════════════════════════════╗[/]"
        )
        if is_resuming:
            self.console.print(
                "[bold cyan]║[/]  [bold white]Tech Lead Q&A Session (Resuming)[/]                        [bold cyan]║[/]"
            )
            if qa_session.total_questions > 0:
                progress_pct = (
                    qa_session.current_question / qa_session.total_questions * 100
                )
                progress_str = (
                    f"Progress: {qa_session.current_question}/{qa_session.total_questions} "
                    f"({progress_pct:.0f}%)"
                )
                # Pad to fit the box
                padded = progress_str.ljust(56)
                self.console.print(
                    f"[bold cyan]║[/]  [dim]{padded}[/]  [bold cyan]║[/]"
                )
        else:
            self.console.print(
                "[bold cyan]║[/]  [bold white]Tech Lead Q&A Session[/]                                      [bold cyan]║[/]"
            )
            self.console.print(
                "[bold cyan]║[/]  [dim]Answer questions to refine the spec and generate task list[/]  [bold cyan]║[/]"
            )
        self.console.print(
            "[bold cyan]╚══════════════════════════════════════════════════════════════╝[/]\n"
        )

        # Track last agent response for recording exchanges
        last_agent_response = ""

        try:
            async with AgentSession(
                agent_name=agent_name,
                model=self.model,
                system_prompt=prompt,
            ) as agent_session:
                # Start message depends on whether we're resuming
                if is_resuming:
                    current_message = (
                        f"Continue from Question {qa_session.current_question + 1}. "
                        "Do not repeat questions already answered."
                    )
                else:
                    current_message = "Begin spec review and task list creation."

                while not task_list_ready and not self._shutdown_requested:
                    # Execute current message and display response
                    last_agent_response = ""
                    async for message in agent_session.execute(current_message):
                        # Handle budget warnings from harness
                        if (
                            isinstance(message, dict)
                            and message.get("subtype") == "context_budget_warning"
                        ):
                            logger.warning(
                                "Context budget warning in Q&A session",
                                level=message.get("level"),
                                tokens_used=message.get("tokens_used"),
                                tokens_remaining=message.get("tokens_remaining"),
                                percent_used=message.get("percent_used"),
                            )
                            # Let parse_and_print_message handle display
                            parse_and_print_message(message, self.console, quiet=False)
                            continue

                        content = self._extract_content_str(message)
                        session_content.append(content)
                        session.total_turns += 1
                        last_agent_response += content

                        # Parse question progress
                        self._parse_question_progress(content, qa_session)

                        # Display message using Rich formatting
                        parse_and_print_message(message, self.console, quiet=False)

                        # Check for completion
                        completed, blocked = self._check_completion_signals(
                            content, session
                        )
                        if completed:
                            task_list_ready = True
                            qa_session.status = "completed"
                            break

                    # If task list not ready and not shutting down, get user input
                    if not task_list_ready and not self._shutdown_requested:
                        try:
                            # Show progress hint
                            if qa_session.total_questions > 0:
                                self.console.print(
                                    f"[dim](Question {qa_session.current_question}/{qa_session.total_questions} - "
                                    f"type 'quit' to save and exit)[/dim]"
                                )
                            self.console.print()  # Add spacing
                            user_input = Prompt.ask("[bold cyan]You[/]")

                            # Check for exit commands
                            if user_input.lower() in ("exit", "quit", "q"):
                                logger.info("User requested exit during Q&A")
                                # Save session before exiting
                                self._save_qa_session(qa_session)
                                self.console.print(
                                    "\n[yellow]Session saved. Run 'make autonomous' to resume.[/yellow]\n"
                                )
                                self._shutdown_requested = True
                                break

                            # Skip empty input
                            if not user_input.strip():
                                continue

                            # Record the exchange in QA session
                            qa_session.add_exchange(last_agent_response, user_input)
                            self._save_qa_session(qa_session)

                            # Use user input for next iteration
                            current_message = user_input
                            session_content.append(f"\n[USER]: {user_input}\n")

                        except (KeyboardInterrupt, EOFError):
                            logger.info("User interrupted Q&A session")
                            # Save session before exiting
                            self._save_qa_session(qa_session)
                            self.console.print(
                                "\n[yellow]Session saved. Run 'make autonomous' to resume.[/yellow]\n"
                            )
                            self._shutdown_requested = True
                            break

                # Get final stats
                if hasattr(agent_session, "total_tokens"):
                    session.total_tokens = agent_session.total_tokens
                if hasattr(agent_session, "total_cost_usd"):
                    session.total_cost_usd = agent_session.total_cost_usd

        except Exception as e:
            logger.error("Initializer session error", error=str(e))
            session_content.append(f"\n\n**ERROR**: {str(e)}")
            self.console.print(f"\n[red bold]Error: {str(e)}[/red bold]\n")

        # Clean up QA session file if completed
        if task_list_ready:
            self._delete_qa_session()

        return task_list_ready, "\n".join(session_content)

    async def _run_continuation_session(
        self,
        prompt: str,
        session: SessionData,
        task_list: TaskList,
    ) -> tuple[bool, str]:
        """Run an autonomous coding session (no human interaction).

        This mode runs fully autonomously - works on tasks from task_list.json
        without requiring human input.

        Args:
            prompt: System prompt for the session
            session: Session data to track stats
            task_list: Task list for status updates

        Returns:
            Tuple of (task_completed_or_blocked, session_content)
        """
        agent_name = "autonomous-continuation"
        session_content: list[str] = []
        task_completed = False
        task_blocked = False

        self.console.print(
            "\n[bold green]╔══════════════════════════════════════════════════════════════╗[/]"
        )
        self.console.print(
            "[bold green]║[/]  [bold white]Autonomous Development Session[/]                           [bold green]║[/]"
        )
        self.console.print(
            "[bold green]║[/]  [dim]Working on tasks from task_list.json[/]                       [bold green]║[/]"
        )
        self.console.print(
            "[bold green]╚══════════════════════════════════════════════════════════════╝[/]\n"
        )

        try:
            async with AgentSession(
                agent_name=agent_name,
                model=self.model,
                system_prompt=prompt,
            ) as agent_session:
                # Single autonomous execution
                async for message in agent_session.execute("Begin work on current task."):
                    # Handle budget warnings from harness
                    if (
                        isinstance(message, dict)
                        and message.get("subtype") == "context_budget_warning"
                    ):
                        logger.warning(
                            "Context budget warning in continuation session",
                            level=message.get("level"),
                            tokens_used=message.get("tokens_used"),
                            tokens_remaining=message.get("tokens_remaining"),
                            percent_used=message.get("percent_used"),
                        )
                        # Let parse_and_print_message handle display
                        parse_and_print_message(message, self.console, quiet=False)
                        continue

                    content = self._extract_content_str(message)
                    session_content.append(content)
                    session.total_turns += 1

                    # Display message
                    parse_and_print_message(message, self.console, quiet=False)

                    # Check for completion signals (updates task_list status)
                    completed, blocked = self._check_completion_signals(
                        content, session, task_list
                    )
                    if completed:
                        task_completed = True
                    if blocked:
                        task_blocked = True

                    # Check for shutdown
                    if self._shutdown_requested:
                        logger.info("Shutdown requested, ending session")
                        break

                # Get final stats
                if hasattr(agent_session, "total_tokens"):
                    session.total_tokens = agent_session.total_tokens
                if hasattr(agent_session, "total_cost_usd"):
                    session.total_cost_usd = agent_session.total_cost_usd

        except Exception as e:
            logger.error("Continuation session error", error=str(e))
            session_content.append(f"\n\n**ERROR**: {str(e)}")
            self.console.print(f"\n[red bold]Error: {str(e)}[/red bold]\n")

        return task_completed or task_blocked, "\n".join(session_content)

    async def _run_session(
        self,
        mode: str,
        prompt: str,
        session: SessionData,
        qa_session: QASession | None = None,
        task_list: TaskList | None = None,
    ) -> tuple[bool, str]:
        """Run a single agent session.

        Dispatches to the appropriate session handler based on mode:
        - initializer: Interactive Q&A with human
        - continuation: Autonomous development

        Args:
            mode: 'initializer' or 'continuation'
            prompt: System prompt for the session
            session: Session data to track stats
            qa_session: QA session for initializer mode
            task_list: Task list for continuation mode

        Returns:
            Tuple of (task_completed, session_content)
        """
        if mode == "initializer":
            if qa_session is None:
                qa_session = self._create_qa_session()
            return await self._run_initializer_session(prompt, session, qa_session)
        else:
            if task_list is None:
                raise ValueError("task_list required for continuation mode")
            return await self._run_continuation_session(prompt, session, task_list)

    async def run(self) -> None:
        """Run the autonomous development loop."""
        # Set up async signal handlers now that we have an event loop
        self._setup_signal_handlers()
        self._shutdown_event = asyncio.Event()

        logger.info(
            "Starting autonomous runner",
            workspace=str(self.workspace_dir),
            model=self.model or self.config.claude_model,
        )

        # Detect and handle workspace state before main loop
        state, context = self._detect_workspace_state()
        logger.info("Workspace state detected", state=state.name)

        should_proceed = await self._handle_workspace_state(state, context)
        if not should_proceed:
            logger.info("Exiting due to workspace state handling")
            return

        while not self._shutdown_requested:
            mode = self._get_mode()
            logger.info("Starting session", mode=mode)

            # Load state based on mode
            qa_session: QASession | None = None
            task_list: TaskList | None = None

            if mode == "initializer":
                qa_session = self._load_qa_session()
                if qa_session is None:
                    qa_session = self._create_qa_session()
                prompt = self._build_initializer_prompt(qa_session)
            else:
                # Initialize context directory for continuation mode
                self._init_context_directory()
                # Load task list BEFORE building prompt and running session
                task_list = self.progress_manager.load_task_list()
                prompt = self._build_continuation_prompt()

            # Start session tracking
            session = self.progress_manager.start_session()

            # Run the session
            task_completed, session_content = await self._run_session(
                mode=mode,
                prompt=prompt,
                session=session,
                qa_session=qa_session,
                task_list=task_list,
            )

            # Handle session completion
            if mode == "continuation":
                # task_list status was updated during session via _check_completion_signals
                # Add transcript to session
                session.transcript = [{"role": "system", "content": session_content}]

                # Check if all done using task_list stats
                stats = task_list.get_completion_stats()
                if stats["remaining"] == 0:
                    logger.info("All tasks completed!")
                    # End session (saves both task_list and session)
                    self.progress_manager.end_session(session, task_list)
                    break

                # End session (saves both task_list and session)
                self.progress_manager.end_session(session, task_list)

            else:
                # For initializer mode, just save session
                session.transcript = [{"role": "system", "content": session_content}]
                self.progress_manager.save_session(session)

                if task_completed:
                    # Task list was created, next iteration will be continuation
                    logger.info("Initializer complete, switching to continuation mode")

            # Check for shutdown before delay
            if self._shutdown_requested:
                break

            # Delay before next session with visible countdown (interruptible)
            self.console.print(
                "\n[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]"
            )
            delay = self.config.autonomous_delay_seconds
            self.console.print(
                f"[yellow]Session complete. Starting next session in {delay} seconds...[/yellow]"
            )
            self.console.print(
                "[dim]Press Ctrl+C to exit[/dim]"
            )
            logger.debug(f"Waiting {delay}s before next session...")

            # Use interruptible wait with shutdown event
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=delay,
                )
                # If we get here, shutdown was requested
                logger.info("Shutdown event received during delay")
            except TimeoutError:
                # Normal timeout, continue to next session
                pass

        logger.info("Autonomous runner stopped")


async def run_autonomous(
    workspace_dir: Path | None = None,
    model: str | None = None,
    quiet: bool = False,  # noqa: ARG001 - handled in main() before this is called
) -> None:
    """Run autonomous development mode.

    Args:
        workspace_dir: Directory for development work
        model: Claude model to use
        quiet: Suppress system logs (handled in main() before this call)
    """
    config = get_config()

    if workspace_dir is None:
        workspace_dir = config.workspace_dir

    runner = AutonomousRunner(
        workspace_dir=workspace_dir,
        model=model,
    )

    await runner.run()


def main() -> None:
    """Entry point for autonomous mode."""
    parser = argparse.ArgumentParser(
        description="Run Claude Agent SDK in autonomous development mode",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (default: from config)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        choices=["sonnet", "opus", "haiku"],
        help="Claude model to use",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress system logs (show only agent output)",
    )

    args = parser.parse_args()

    # Configure quiet mode EARLY, before any other operations that might log
    if args.quiet:
        import logging
        logging.getLogger().setLevel(logging.CRITICAL)
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        )

    # Map model shorthand to full name
    model_map = {
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-5-20251101",
        "haiku": "claude-3-5-haiku-20241022",
    }

    model = model_map.get(args.model) if args.model else None

    try:
        asyncio.run(
            run_autonomous(
                workspace_dir=args.workspace,
                model=model,
                quiet=args.quiet,
            )
        )
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        sys.exit(0)


if __name__ == "__main__":
    main()
