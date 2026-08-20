from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from prefect import flow, task
from prefect.states import State


def logger(fun_obj: Any, fun_run: Any, state: State) -> None:
    name = getattr(fun_obj, "name", None) or getattr(fun_obj, "__name__", type(fun_obj).__name__)
    run_name = getattr(fun_run, "name", None) or getattr(fun_run, "id", "")
    message = getattr(state, "message", "") or ""
    timestamp = getattr(state, "timestamp", "")
    print(f"[{timestamp}] {state.name}: {name} {run_name} {message}".strip())


def glow_task(function: Callable[..., Any]) -> Any:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        return function(*args, **kwargs)

    return task(
        wrapped,
        name=function.__name__,
        on_running=[logger],
        on_completion=[logger],
        on_failure=[logger],
    )


def glow_flow(function: Callable[..., Any]) -> Any:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        return function(*args, **kwargs)

    return flow(
        wrapped,
        name=function.__name__,
        validate_parameters=False,
        on_running=[logger],
        on_completion=[logger],
        on_failure=[logger],
        on_cancellation=[logger],
        on_crashed=[logger],
    )
