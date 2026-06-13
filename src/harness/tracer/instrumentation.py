"""Instrumentation decorators for automatic tracing.

This module provides decorators that automatically create spans for
functions and methods, simplifying instrumentation of existing code.

Example usage:
    from harness.tracer import traced, SpanKind

    @traced("tool.call", SpanKind.TOOL_CALL)
    async def call_tool(name: str, args: dict) -> dict:
        # Span automatically created and finished
        result = await execute_tool(name, args)
        return result

    # With attribute extraction
    @traced("agent.{agent_name}.execute", extract_attrs=["agent_name"])
    async def execute(self, agent_name: str, prompt: str):
        pass
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

import structlog

from harness.tracer.base import SpanKind

if TYPE_CHECKING:
    from harness.tracer.otel_tracer import OTelTracer

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# Module-level tracer reference (set by get_tracer())
_global_tracer: OTelTracer | None = None


def set_global_tracer(tracer: OTelTracer) -> None:
    """Set the global tracer for instrumentation decorators.

    Args:
        tracer: The tracer to use for instrumentation.
    """
    global _global_tracer
    _global_tracer = tracer


def get_global_tracer() -> OTelTracer | None:
    """Get the global tracer.

    Returns:
        The global tracer or None if not set.
    """
    return _global_tracer


def traced(
    name: str | None = None,
    kind: SpanKind = SpanKind.AGENT_EXECUTION,
    extract_attrs: list[str] | None = None,
    record_args: bool = False,
    record_result: bool = False,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to automatically trace a function.

    Creates a span around the function execution, handling both sync
    and async functions. Supports dynamic span names and attribute extraction.

    Args:
        name: Span name (supports {arg_name} substitution). If None, uses
            the function's qualified name.
        kind: Span kind category.
        extract_attrs: List of argument names to extract as span attributes.
        record_args: If True, record all arguments as span attributes.
        record_result: If True, record the return value (stringified) as attribute.

    Returns:
        Decorated function that creates spans automatically.

    Example:
        @traced("agent.execute", SpanKind.AGENT_EXECUTION)
        async def execute_agent(name: str, prompt: str):
            pass

        @traced(extract_attrs=["tool_name"])
        async def call_tool(tool_name: str, args: dict):
            pass
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        # Determine span name
        span_name = name or f"{func.__module__}.{func.__qualname__}"
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            tracer = _global_tracer
            if tracer is None or not tracer.enabled:
                return await func(*args, **kwargs)

            # Build dynamic span name and attributes
            actual_name, attributes = _build_span_info(
                span_name, func, args, kwargs, extract_attrs, record_args
            )

            with tracer.span(actual_name, kind, attributes) as span:
                try:
                    result = await func(*args, **kwargs)
                    if record_result:
                        span.set_attribute("result", _safe_str(result))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            tracer = _global_tracer
            if tracer is None or not tracer.enabled:
                return func(*args, **kwargs)

            # Build dynamic span name and attributes
            actual_name, attributes = _build_span_info(
                span_name, func, args, kwargs, extract_attrs, record_args
            )

            with tracer.span(actual_name, kind, attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    if record_result:
                        span.set_attribute("result", _safe_str(result))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise

        return async_wrapper if is_async else sync_wrapper  # type: ignore[return-value]

    return decorator


def _build_span_info(
    name_template: str,
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    extract_attrs: list[str] | None,
    record_args: bool,
) -> tuple[str, dict[str, Any]]:
    """Build span name and attributes from function call.

    Args:
        name_template: Span name with optional {arg} placeholders.
        func: The traced function.
        args: Positional arguments.
        kwargs: Keyword arguments.
        extract_attrs: Argument names to extract.
        record_args: Whether to record all args.

    Returns:
        Tuple of (span_name, attributes_dict).
    """
    # Build argument mapping
    sig = inspect.signature(func)
    bound = sig.bind_partial(*args, **kwargs)
    bound.apply_defaults()
    all_args = dict(bound.arguments)

    # Substitute name template
    span_name = name_template
    for key, value in all_args.items():
        placeholder = f"{{{key}}}"
        if placeholder in span_name:
            span_name = span_name.replace(placeholder, str(value))

    # Build attributes
    attributes: dict[str, Any] = {
        "function.name": func.__name__,
        "function.module": func.__module__,
    }

    if extract_attrs:
        for attr_name in extract_attrs:
            if attr_name in all_args:
                attributes[f"arg.{attr_name}"] = _safe_str(all_args[attr_name])

    if record_args:
        for key, value in all_args.items():
            # Skip 'self' and large values
            if key == "self":
                continue
            str_value = _safe_str(value)
            if len(str_value) <= 1000:  # Limit attribute size
                attributes[f"arg.{key}"] = str_value

    return span_name, attributes


def _safe_str(value: Any, max_len: int = 500) -> str:
    """Convert value to string safely with length limit.

    Args:
        value: Value to convert.
        max_len: Maximum string length.

    Returns:
        String representation, truncated if needed.
    """
    try:
        s = str(value)
        if len(s) > max_len:
            return s[:max_len] + "..."
        return s
    except Exception:
        return "<unrepresentable>"


class TracedClass:
    """Mixin class for automatic method tracing.

    Inherit from this class and specify traced_methods to automatically
    instrument specific methods.

    Example:
        class MyAgent(TracedClass):
            traced_methods = ["execute", "call_tool"]
            traced_kind = SpanKind.AGENT_EXECUTION

            async def execute(self, prompt: str):
                # Automatically traced
                pass
    """

    traced_methods: list[str] = []
    traced_kind: SpanKind = SpanKind.AGENT_EXECUTION
    traced_prefix: str = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        for method_name in cls.traced_methods:
            if hasattr(cls, method_name):
                original = getattr(cls, method_name)
                prefix = cls.traced_prefix or cls.__name__.lower()
                span_name = f"{prefix}.{method_name}"
                wrapped = traced(span_name, cls.traced_kind)(original)
                setattr(cls, method_name, wrapped)


def trace_method(
    kind: SpanKind = SpanKind.AGENT_EXECUTION,
    name_prefix: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for tracing class methods with automatic naming.

    Uses {class_name}.{method_name} as the span name by default.

    Args:
        kind: Span kind category.
        name_prefix: Optional prefix for span name (defaults to class name).

    Returns:
        Decorated method.

    Example:
        class Agent:
            @trace_method(SpanKind.AGENT_EXECUTION)
            async def execute(self, prompt: str):
                pass
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(self: Any, *args: P.args, **kwargs: P.kwargs) -> T:
            tracer = _global_tracer
            if tracer is None or not tracer.enabled:
                return await func(self, *args, **kwargs)

            prefix = name_prefix or type(self).__name__.lower()
            span_name = f"{prefix}.{func.__name__}"

            with tracer.span(span_name, kind) as span:
                span.set_attribute("class", type(self).__name__)
                try:
                    result = await func(self, *args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(self: Any, *args: P.args, **kwargs: P.kwargs) -> T:
            tracer = _global_tracer
            if tracer is None or not tracer.enabled:
                return func(self, *args, **kwargs)

            prefix = name_prefix or type(self).__name__.lower()
            span_name = f"{prefix}.{func.__name__}"

            with tracer.span(span_name, kind) as span:
                span.set_attribute("class", type(self).__name__)
                try:
                    result = func(self, *args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise

        return async_wrapper if is_async else sync_wrapper  # type: ignore[return-value]

    return decorator


def record_tokens(
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    model: str | None = None,
) -> None:
    """Record token usage on the current span.

    Convenience function for recording LLM token usage.

    Args:
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cached_tokens: Number of cached tokens.
        model: Model name.
    """
    if _global_tracer is None:
        return

    span = _global_tracer.current_span()
    if span is None:
        return

    span.token_usage = {
        "input": input_tokens,
        "output": output_tokens,
        "cached": cached_tokens,
        "total": input_tokens + output_tokens,
    }

    if model:
        span.set_attribute("llm.model", model)
