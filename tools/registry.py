r'''Tool registry for OrgMind.

Implements the :class:`Tool` decorator that converts a plain Python function
into a Gemini-compatible tool definition. The orchestrator (Phase 2+) feeds
``Tool.tool_schema`` straight into the Gemini ``tools=[...]`` list and
re-dispatches calls back to the wrapped function.

Canonical tool names and signatures live in ``docs/CONTRACTS.md`` section 3
(Tool catalogue); this module is just the decorator that turns those
functions into wire-format JSON Schema.

Example
-------
::

    from tools.registry import Tool, REGISTRY

    @Tool
    def add(a: int, b: int) -> int:
        # docstring stripped and used as the tool description
        return a + b

    # Wire to Gemini:
    # client.messages.create(..., tools=[add.tool_schema], ...)
'''

from __future__ import annotations

import inspect
import types as _types
from typing import Any, Callable, Union, get_args, get_origin, get_type_hints

__all__ = ["Tool", "REGISTRY"]


# ---------------------------------------------------------------------------
# JSON Schema construction from Python type hints
# ---------------------------------------------------------------------------


def _annotation_to_schema(ann: Any) -> dict:
    """Translate a single Python annotation into a JSON Schema fragment.

    Supports the subset called out in the P0 brief: ``str``, ``int``,
    ``float``, ``bool``, ``list[X]``, ``dict`` / ``dict[str, Any]``, and
    ``Optional[X]`` / ``X | None``. Unknown annotations fall back to
    ``{"type": "string"}`` so the schema is still well-formed.
    """
    # Nothing typed — caller usually wants a string default.
    if ann is None or ann is type(None):
        return {"type": "null"}

    origin = get_origin(ann)
    args = get_args(ann)

    # Optional[X] / X | None / Union[X, None] -> {"anyOf": [..., null]}.
    is_union = origin is Union or (
        hasattr(_types, "UnionType") and isinstance(ann, _types.UnionType)
    )
    if is_union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and type(None) in args:
            inner = _annotation_to_schema(non_none[0])
            return {"anyOf": [inner, {"type": "null"}]}
        # Plain Union without None -> fall through to a permissive schema.
        return {"type": "string"}

    # list[X] / List[X]
    if origin is list:
        items_schema = _annotation_to_schema(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": items_schema}

    # dict / dict[K, V]
    if origin is dict:
        return {"type": "object"}

    # Bare builtins (no subscript) — origin is None for plain ``list`` / ``dict``.
    if ann is list:
        return {"type": "array", "items": {"type": "string"}}
    if ann is dict:
        return {"type": "object"}

    # bool must be checked before int because ``bool`` is a subclass of ``int``.
    if ann is bool:
        return {"type": "boolean"}
    if ann is int:
        return {"type": "integer"}
    if ann is float:
        return {"type": "number"}
    if ann is str:
        return {"type": "string"}

    # Anything we don't know — be conservative so the schema still validates.
    return {"type": "string"}


def _build_schema(func: Callable[..., Any]) -> dict:
    """Build a Gemini ``tools=[...]`` entry from a Python function."""
    sig = inspect.signature(func)

    try:
        hints = get_type_hints(func)
    except Exception:
        # Forward references, missing imports, etc. — don't blow up P0.
        hints = {}

    properties: dict[str, dict] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        # *args / **kwargs aren't real the model tool inputs.
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        ann = hints.get(name, param.annotation)
        if ann is inspect.Parameter.empty:
            schema: dict = {"type": "string"}
        else:
            schema = _annotation_to_schema(ann)

        properties[name] = schema
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "name": func.__name__,
        "description": (func.__doc__ or "").strip(),
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


# ---------------------------------------------------------------------------
# The decorator
# ---------------------------------------------------------------------------


class Tool:
    """Decorator that registers a Python function as an Gemini tool.

    Usage::

        @Tool
        def add(a: int, b: int) -> int:
            '''Add two integers and return the sum.'''
            return a + b

    Each instance records itself into :data:`REGISTRY` at decoration time,
    in declaration order. ``tool_schema`` returns the dict that goes into
    the Gemini ``tools=[...]`` list. Calling the instance forwards to
    the wrapped function unchanged.
    """

    def __init__(self, func: Callable[..., Any]) -> None:
        self._func: Callable[..., Any] = func
        self._schema: dict = _build_schema(func)
        # Preserve introspection-friendly attributes via functools.wraps.
        import functools

        functools.wraps(func)(self)
        # Register in declaration order.
        REGISTRY.append(self)

    # --- behaviour --------------------------------------------------------

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._func(*args, **kwargs)

    # --- introspection ----------------------------------------------------

    @property
    def tool_schema(self) -> dict:
        """The ``{name, description, input_schema}`` dict for Gemini."""
        return self._schema

    @property
    def name(self) -> str:
        return self._schema["name"]

    @property
    def description(self) -> str:
        return self._schema["description"]


# ---------------------------------------------------------------------------
# Module-level registry
# ---------------------------------------------------------------------------

REGISTRY: list[Tool] = []
'''Every :class:`Tool` instance, in declaration order.'''