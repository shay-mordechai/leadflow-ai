"""Strong references and failure reporting for detached asyncio tasks."""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)
_background_tasks: set[asyncio.Task[Any]] = set()


def retain_task(task: asyncio.Task[Any]) -> asyncio.Task[Any]:
    """Keep a detached task alive and observe its exception until completion."""
    _background_tasks.add(task)

    def _on_done(completed: asyncio.Task[Any]) -> None:
        _background_tasks.discard(completed)
        if completed.cancelled():
            return
        error = completed.exception()
        if error is not None:
            logger.error(
                "Detached background task failed (%s)",
                type(error).__name__,
            )

    task.add_done_callback(_on_done)
    return task
