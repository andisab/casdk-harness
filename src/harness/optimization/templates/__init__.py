"""Template loading for optimization.

Provides access to context-engineering templates for structure-aware
prompt optimization.
"""

from harness.optimization.templates.loader import (
    TemplateLoader,
    TemplateInfo,
    get_template_loader,
)

__all__ = [
    "TemplateLoader",
    "TemplateInfo",
    "get_template_loader",
]
