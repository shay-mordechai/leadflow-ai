"""Bound in-process FastAPI background work to protect worker memory."""

import inspect
import threading
from collections.abc import Callable
from typing import Any

from fastapi import BackgroundTasks


class BackgroundTaskCapacity:
    """Limit queued plus running tasks using a non-blocking process-wide slot pool."""

    def __init__(self, max_in_flight: int) -> None:
        if max_in_flight < 1:
            raise ValueError("max_in_flight must be positive")
        self._slots = threading.BoundedSemaphore(max_in_flight)

    def try_add(
        self,
        background_tasks: BackgroundTasks,
        function: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """Queue work only when a bounded in-flight slot is available."""
        if not self.try_reserve():
            return False
        self.add_reserved(background_tasks, function, *args, **kwargs)
        return True

    def try_reserve(self) -> bool:
        """Reserve a slot before performing other work needed to enqueue a task."""
        return self._slots.acquire(blocking=False)

    def release_reservation(self) -> None:
        """Release a slot when work could not be queued."""
        self._slots.release()

    def add_reserved(
        self,
        background_tasks: BackgroundTasks,
        function: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Attach a function to a slot already reserved by this capacity pool."""
        background_tasks.add_task(self._run_reserved, function, args, kwargs)

    async def _run_reserved(
        self,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        try:
            result = function(*args, **kwargs)
            if inspect.isawaitable(result):
                await result
        finally:
            self._slots.release()


background_task_capacity = BackgroundTaskCapacity(max_in_flight=200)
