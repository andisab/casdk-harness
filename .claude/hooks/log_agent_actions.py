#!/usr/bin/env python3
"""
Log agent actions from Claude Agent SDK sessions.

This hook parses JSONL transcript files and extracts all agent tool calls,
logging them with timestamps, tool names, inputs, and unique identifiers.

Adapted from claude-agent-sdk-intro for the harness infrastructure.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

# Setup structured logging
logger = structlog.get_logger(__name__)


def parse_agent_actions(filepath: str) -> list[dict[str, Any]]:
    """
    Parse a JSONL transcript file and extract all agent tool calls.

    Args:
        filepath: Path to the JSONL transcript file

    Returns:
        List of dictionaries containing:
        - timestamp: when the action occurred
        - tool_name: name of the tool that was called
        - tool_input: arguments passed to the tool
        - tool_use_id: unique identifier for the tool use
    """
    actions = []

    if not os.path.exists(filepath):
        logger.warning("Transcript file not found", filepath=filepath)
        return actions

    with open(filepath, "r") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())

                # Only process assistant messages
                if entry.get("type") != "assistant":
                    continue

                message = entry.get("message", {})
                content = message.get("content", [])
                timestamp = entry.get("timestamp", "")

                # Look for tool_use in content
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        action = {
                            "timestamp": timestamp,
                            "tool_name": item.get("name"),
                            "tool_input": item.get("input"),
                            "tool_use_id": item.get("id"),
                        }
                        actions.append(action)

            except json.JSONDecodeError:
                # Skip malformed lines
                logger.warning("Malformed JSON line in transcript", filepath=filepath)
                continue

    logger.info("Parsed agent actions", filepath=filepath, action_count=len(actions))
    return actions


def get_logged_tool_ids(log_filepath: str) -> set[str]:
    """
    Read existing log file and extract all tool IDs that have been logged.

    Args:
        log_filepath: Path to the log file

    Returns:
        Set of tool IDs that have already been logged
    """
    logged_ids = set()

    if not os.path.exists(log_filepath):
        return logged_ids

    with open(log_filepath, "r") as f:
        for line in f:
            # Look for lines with "Tool ID: "
            if line.strip().startswith("Tool ID:"):
                tool_id = line.split("Tool ID:")[1].strip()
                logged_ids.add(tool_id)

    return logged_ids


def save_agent_actions_log(
    actions: list[dict[str, Any]], session_id: str, logs_dir: str = "logs/actions"
) -> tuple[str, int]:
    """
    Save agent actions to a log file in append mode.
    Only logs new actions that haven't been logged before (based on tool_use_id).

    Args:
        actions: List of agent actions to log
        session_id: Session ID to use as filename
        logs_dir: Directory to save logs (default: "logs/actions")

    Returns:
        Tuple of (log file path, number of new actions logged)
    """
    # Create logs directory if it doesn't exist
    os.makedirs(logs_dir, exist_ok=True)

    # Check if a log file for this session already exists
    log_filepath = None
    if os.path.exists(logs_dir):
        for filename in os.listdir(logs_dir):
            if filename.endswith(f"_{session_id}.log"):
                log_filepath = os.path.join(logs_dir, filename)
                break

    # If no existing file, create new one with timestamp prefix
    if log_filepath is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{timestamp}_{session_id}.log"
        log_filepath = os.path.join(logs_dir, log_filename)

    # Get already logged tool IDs to avoid duplicates
    logged_ids = get_logged_tool_ids(log_filepath)

    # Filter out actions that have already been logged
    new_actions = [action for action in actions if action["tool_use_id"] not in logged_ids]

    # If this is a new file, write header
    is_new_file = not os.path.exists(log_filepath)

    # Append new actions to log file
    with open(log_filepath, "a") as f:
        if is_new_file:
            f.write(f"{'=' * 80}\n")
            f.write(f"Agent Actions Log - Session: {session_id}\n")
            f.write(f"{'=' * 80}\n\n")

        if new_actions:
            for action in new_actions:
                f.write(f"Action:\n")
                f.write(f"  Timestamp: {action['timestamp']}\n")
                f.write(f"  Tool: {action['tool_name']}\n")
                f.write(f"  Tool ID: {action['tool_use_id']}\n")
                f.write(f"  Input: {json.dumps(action['tool_input'], indent=4)}\n")
                f.write("\n")

    logger.info(
        "Agent actions logged",
        log_filepath=log_filepath,
        new_actions=len(new_actions),
        total_actions=len(actions),
    )

    return log_filepath, len(new_actions)


def main() -> None:
    """Entry point for the hook script."""
    try:
        # Read payload from stdin (passed by Claude Code hooks system)
        payload: dict = json.load(sys.stdin)
        transcript_path = payload.get("transcript_path", "")
        session_id = payload.get("session_id", "unknown_session")

        if not transcript_path:
            logger.error("No transcript path provided in payload")
            sys.exit(1)

        logger.info(
            "Processing agent actions",
            transcript_path=transcript_path,
            session_id=session_id,
        )

        # Parse agent actions and save to log file (append mode, no duplicates)
        actions = parse_agent_actions(transcript_path)
        log_filepath, new_actions_count = save_agent_actions_log(actions, session_id)

        logger.info(
            "Hook execution complete",
            log_filepath=log_filepath,
            new_actions_logged=new_actions_count,
        )

    except json.JSONDecodeError as e:
        logger.error("Failed to decode JSON payload", error=str(e))
        sys.exit(1)
    except Exception as e:
        logger.error("Hook execution failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
