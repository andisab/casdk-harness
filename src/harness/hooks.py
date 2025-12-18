"""Hook registry for plugin event triggers.

Manages registration and execution of hooks defined by plugins.
Hooks are triggered at key points in the agent lifecycle and tool execution.
"""

from __future__ import annotations

import asyncio
import fnmatch
import os
import subprocess
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from harness.plugin_manager import HookEvent, PluginHook

logger = structlog.get_logger(__name__)


class HookRegistry:
    """Registry for plugin event hooks.

    Hooks are triggered at specific events (PreToolUse, PostToolUse, etc.)
    and can optionally match on tool names or file paths.
    """

    def __init__(self, cwd: str | None = None) -> None:
        """Initialize hook registry.

        Args:
            cwd: Working directory for hook command execution.
                 Defaults to current working directory.
        """
        self._hooks: list[PluginHook] = []
        self.cwd = cwd or os.getcwd()

    def register(self, hook: PluginHook) -> None:
        """Register a hook.

        Args:
            hook: PluginHook to register.
        """
        self._hooks.append(hook)
        logger.debug(
            "Registered hook",
            hook_event=hook.event.value,
            plugin=hook.plugin_name,
            has_matcher=bool(hook.matcher),
        )

    def register_all(self, hooks: list[PluginHook]) -> None:
        """Register multiple hooks.

        Args:
            hooks: List of PluginHook objects to register.
        """
        for hook in hooks:
            self.register(hook)

    def get_hooks_for_event(
        self, event: HookEvent, context: dict[str, Any] | None = None
    ) -> list[PluginHook]:
        """Get hooks matching an event and optional context.

        Args:
            event: The hook event type.
            context: Optional context dict for matcher filtering.

        Returns:
            List of matching PluginHook objects.
        """
        matching = []

        for hook in self._hooks:
            if hook.event != event:
                continue

            # If no matcher, hook matches all events of this type
            if not hook.matcher:
                matching.append(hook)
                continue

            # Check matcher conditions
            if self._matches_context(hook.matcher, context):
                matching.append(hook)

        return matching

    def _matches_context(
        self, matcher: dict[str, Any], context: dict[str, Any] | None
    ) -> bool:
        """Check if a matcher matches the given context.

        Matcher fields:
        - tool_name: Glob pattern for tool name
        - file_path: Glob pattern for file path

        Args:
            matcher: Matcher dict from hook.
            context: Context dict with tool_name, file_path, etc.

        Returns:
            True if all matcher conditions are satisfied.
        """
        if context is None:
            return False

        # Check tool_name matcher
        if "tool_name" in matcher:
            tool_name = context.get("tool_name", "")
            if not fnmatch.fnmatch(tool_name, matcher["tool_name"]):
                return False

        # Check file_path matcher
        if "file_path" in matcher:
            file_path = context.get("file_path", "")
            if not fnmatch.fnmatch(file_path, matcher["file_path"]):
                return False

        return True

    def trigger(
        self,
        event: HookEvent,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Trigger hooks for an event synchronously.

        Args:
            event: The hook event type.
            context: Optional context dict for variable substitution.

        Returns:
            List of result dicts with status and output for each hook.
        """
        hooks = self.get_hooks_for_event(event, context)

        if not hooks:
            return []

        results = []
        for hook in hooks:
            result = self._execute_hook(hook, context)
            results.append(result)

        return results

    async def trigger_async(
        self,
        event: HookEvent,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Trigger hooks for an event asynchronously.

        Args:
            event: The hook event type.
            context: Optional context dict for variable substitution.

        Returns:
            List of result dicts with status and output for each hook.
        """
        hooks = self.get_hooks_for_event(event, context)

        if not hooks:
            return []

        tasks = [
            self._execute_hook_async(hook, context)
            for hook in hooks
        ]

        return await asyncio.gather(*tasks)

    def _execute_hook(
        self, hook: PluginHook, context: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Execute a single hook synchronously.

        Args:
            hook: The hook to execute.
            context: Context for variable substitution.

        Returns:
            Result dict with status, output, and hook info.
        """
        command = self._substitute_variables(hook.command, context)

        result: dict[str, Any] = {
            "plugin": hook.plugin_name,
            "event": hook.event.value,
            "command": command,
        }

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=hook.timeout,
                cwd=self.cwd,
            )

            result["status"] = "success" if proc.returncode == 0 else "error"
            result["exit_code"] = proc.returncode
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr

            if proc.returncode != 0:
                logger.warning(
                    "Hook command failed",
                    plugin=hook.plugin_name,
                    command=command[:100],
                    exit_code=proc.returncode,
                    stderr=proc.stderr[:200] if proc.stderr else None,
                )
            else:
                logger.debug(
                    "Hook executed successfully",
                    plugin=hook.plugin_name,
                    hook_event=hook.event.value,
                )

        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["error"] = f"Command timed out after {hook.timeout}s"
            logger.warning(
                "Hook command timed out",
                plugin=hook.plugin_name,
                command=command[:100],
                timeout=hook.timeout,
            )

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(
                "Hook execution failed",
                plugin=hook.plugin_name,
                command=command[:100],
                error=str(e),
            )

        return result

    async def _execute_hook_async(
        self, hook: PluginHook, context: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Execute a single hook asynchronously.

        Args:
            hook: The hook to execute.
            context: Context for variable substitution.

        Returns:
            Result dict with status, output, and hook info.
        """
        command = self._substitute_variables(hook.command, context)

        result: dict[str, Any] = {
            "plugin": hook.plugin_name,
            "event": hook.event.value,
            "command": command,
        }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=hook.timeout,
                )

                result["status"] = "success" if proc.returncode == 0 else "error"
                result["exit_code"] = proc.returncode
                result["stdout"] = stdout.decode() if stdout else ""
                result["stderr"] = stderr.decode() if stderr else ""

                if proc.returncode != 0:
                    logger.warning(
                        "Hook command failed",
                        plugin=hook.plugin_name,
                        command=command[:100],
                        exit_code=proc.returncode,
                    )
                else:
                    logger.debug(
                        "Hook executed successfully",
                        plugin=hook.plugin_name,
                        hook_event=hook.event.value,
                    )

            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                result["status"] = "timeout"
                result["error"] = f"Command timed out after {hook.timeout}s"
                logger.warning(
                    "Hook command timed out",
                    plugin=hook.plugin_name,
                    command=command[:100],
                    timeout=hook.timeout,
                )

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(
                "Hook execution failed",
                plugin=hook.plugin_name,
                command=command[:100],
                error=str(e),
            )

        return result

    def _substitute_variables(
        self, command: str, context: dict[str, Any] | None
    ) -> str:
        """Substitute variables in a hook command.

        Variables:
        - $FILE : File path from context
        - $TOOL : Tool name from context
        - $RESULT : Result/output from context

        Args:
            command: Command string with variables.
            context: Context dict for substitution.

        Returns:
            Command with variables substituted.
        """
        if context is None:
            return command

        # Standard substitutions
        substitutions = {
            "$FILE": context.get("file_path", ""),
            "$TOOL": context.get("tool_name", ""),
            "$RESULT": str(context.get("result", "")),
        }

        result = command
        for var, value in substitutions.items():
            result = result.replace(var, value)

        return result

    def list_all(self) -> list[PluginHook]:
        """Get all registered hooks.

        Returns:
            List of all PluginHook objects.
        """
        return self._hooks.copy()

    def list_by_event(self, event: HookEvent) -> list[PluginHook]:
        """Get hooks for a specific event.

        Args:
            event: Hook event type to filter by.

        Returns:
            List of PluginHook objects for that event.
        """
        return [hook for hook in self._hooks if hook.event == event]

    def list_by_plugin(self, plugin_name: str) -> list[PluginHook]:
        """Get hooks for a specific plugin.

        Args:
            plugin_name: Plugin name to filter by.

        Returns:
            List of PluginHook objects from that plugin.
        """
        return [hook for hook in self._hooks if hook.plugin_name == plugin_name]

    def clear(self) -> None:
        """Remove all registered hooks."""
        self._hooks.clear()
        logger.debug("Cleared all hooks")

    def __len__(self) -> int:
        """Return number of registered hooks."""
        return len(self._hooks)
