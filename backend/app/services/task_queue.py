"""Background task processing for heavy operations.

Uses asyncio.Queue for in-process tasks with optional Redis-backed
distributed queue for multi-worker setups.

Prevents: AI queries and ingestion from blocking the API request cycle.
"""

import asyncio
import logging
import traceback
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("collective_brain.tasks")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    result: Any = None
    error: str | None = None


@dataclass
class TaskEntry:
    task_id: str
    func: Callable[..., Awaitable[Any]]
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    callback: Callable[[TaskResult], Awaitable[None]] | None = None


class TaskQueue:
    """In-process async task queue for background work."""

    def __init__(self, max_concurrent: int = 3):
        self._queue: asyncio.Queue[TaskEntry] = asyncio.Queue(maxsize=100)
        self._results: dict[str, TaskResult] = {}
        self._workers: list[asyncio.Task] = []
        self._max_concurrent = max_concurrent
        self._running = False

    async def start(self):
        """Start worker tasks."""
        if self._running:
            return
        self._running = True
        for i in range(self._max_concurrent):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker)
        logger.info("Task queue started with %d workers", self._max_concurrent)

    async def stop(self):
        """Gracefully stop all workers."""
        self._running = False
        # Signal workers to exit
        for _ in self._workers:
            await self._queue.put(None)  # type: ignore
        for w in self._workers:
            w.cancel()
            try:
                await w
            except asyncio.CancelledError:
                pass
        self._workers.clear()
        logger.info("Task queue stopped")

    async def enqueue(
        self,
        task_id: str,
        func: Callable[..., Awaitable[Any]],
        *args,
        callback: Callable[[TaskResult], Awaitable[None]] | None = None,
        **kwargs,
    ) -> str:
        """Submit a task for background execution."""
        entry = TaskEntry(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            callback=callback,
        )
        self._results[task_id] = TaskResult(
            task_id=task_id, status=TaskStatus.PENDING
        )
        await self._queue.put(entry)
        logger.info("Task enqueued: %s", task_id)
        return task_id

    def get_result(self, task_id: str) -> TaskResult | None:
        """Check task status."""
        return self._results.get(task_id)

    async def _worker_loop(self, worker_name: str):
        """Worker that processes tasks from the queue."""
        while self._running:
            try:
                entry = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if entry is None:
                break

            task_id = entry.task_id
            self._results[task_id] = TaskResult(
                task_id=task_id, status=TaskStatus.RUNNING
            )
            logger.info("[%s] Processing task: %s", worker_name, task_id)

            try:
                result = await entry.func(*entry.args, **entry.kwargs)
                task_result = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    result=result,
                )
                self._results[task_id] = task_result
                logger.info("[%s] Task completed: %s", worker_name, task_id)
            except Exception as e:
                task_result = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error=f"{type(e).__name__}: {str(e)}",
                )
                self._results[task_id] = task_result
                logger.error(
                    "[%s] Task failed: %s — %s\n%s",
                    worker_name, task_id, e, traceback.format_exc(),
                )

            # Fire callback
            if entry.callback:
                try:
                    await entry.callback(task_result)
                except Exception as e:
                    logger.error("Task callback error for %s: %s", task_id, e)

            self._queue.task_done()

            # Prevent result dict from growing unbounded
            if len(self._results) > 1000:
                oldest = list(self._results.keys())[:500]
                for k in oldest:
                    if self._results[k].status in (
                        TaskStatus.COMPLETED,
                        TaskStatus.FAILED,
                    ):
                        del self._results[k]
