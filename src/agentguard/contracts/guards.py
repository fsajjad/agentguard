# Allows using ClassName in type hints before defining it
from __future__ import annotations

# asyncio = for async/await support
# functools = for wraps() which preserves function metadata
# inspect = for reading function signatures (what params it takes)
import asyncio
import functools
import inspect
from typing import Any, Callable, ParamSpec, TypeVar

# The error we raise when a safety check fails
from agentguard.contracts.models import ViolationError

# P = placeholder for "whatever parameters the decorated function takes"
# R = placeholder for "whatever type the decorated function returns"
P = ParamSpec("P")
R = TypeVar("R")

# Type aliases — shortcuts for readability
type ConditionFn = Callable[..., bool]  # a function that returns True/False
type AsyncConditionFn = Callable[..., Any]  # an async function


def agent_guard(
    *,  # forces all arguments to be named (keyword-only)
    pre: list[ConditionFn | AsyncConditionFn] | None = None,  # checks to run BEFORE
    post: list[Callable[[Any], bool]] | None = None,  # checks to run AFTER
    on_violation: Callable[[ViolationError], Any] | None = None,  # custom handler if a check fails
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that wraps a tool function with pre/post condition checks."""

    # This inner function receives the actual function being decorated
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        # Get the function's parameter info (names, defaults, etc.)
        sig = inspect.signature(fn)

        # If the function is async (uses await)...
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)  # preserves original function's name and docstring
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore[misc]
                # Match the arguments to parameter names
                # e.g. if fn(cmd, folder) is called with ("ls", "/tmp")
                # then call_ctx = {"cmd": "ls", "folder": "/tmp"}
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()  # fill in any default values
                call_ctx = dict(bound.arguments)  # dict of param_name: value

                # Run each pre-condition check BEFORE the function executes
                for check in (pre or []):  # if pre is None, use empty list
                    if asyncio.iscoroutinefunction(check):
                        ok = await check(**call_ctx)  # async check
                    else:
                        ok = check(**call_ctx)  # sync check
                    if not ok:  # check returned False = violation!
                        err = ViolationError(rule=check.__name__, context=call_ctx)
                        if on_violation:  # if custom handler provided, call it
                            return on_violation(err)  # type: ignore[return-value]
                        raise err  # otherwise raise the error

                # All pre-checks passed — run the actual function
                result = await fn(*args, **kwargs)  # type: ignore[misc]

                # Run each post-condition check AFTER the function returns
                for check in (post or []):
                    if not check(result):  # check the result
                        err = ViolationError(rule=check.__name__, context={"result": result})
                        if on_violation:
                            return on_violation(err)  # type: ignore[return-value]
                        raise err

                # Everything passed — return the result
                return result  # type: ignore[return-value]

            return async_wrapper  # type: ignore[return-value]
        else:
            # Same logic but for regular (non-async) functions
            @functools.wraps(fn)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                call_ctx = dict(bound.arguments)

                # Run pre-checks
                for check in (pre or []):
                    if not check(**call_ctx):
                        err = ViolationError(rule=check.__name__, context=call_ctx)
                        if on_violation:
                            return on_violation(err)  # type: ignore[return-value]
                        raise err

                # Run the actual function
                result = fn(*args, **kwargs)

                # Run post-checks
                for check in (post or []):
                    if not check(result):
                        err = ViolationError(rule=check.__name__, context={"result": result})
                        if on_violation:
                            return on_violation(err)  # type: ignore[return-value]
                        raise err

                return result

            return sync_wrapper  # type: ignore[return-value]

    # Return the decorator function
    return decorator
