"""Background task processing for heavy operations.

Uses asyncio.Queue for in-process tasks with optional Redis-backed
distributed queue for multi-worker setups.

Prevents: AI queries and ingestion from blocking the API request cycle.
"""

import asyncio
import logging
import time
import traceback
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("collective_brain.tasks")

# TTL for completed/failed task results (seconds)
_RESULT_TTL_SECONDS = 3600  # 1 hour
_MAX_RESULTS = 1000
_STUCK_TASK_TIMEOUT = 600  # 10 minutes — mark RUNNING tasks as FAILED


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
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


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
        # Start background cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
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
        if hasattr(self, "_cleanup_task"):
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
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

    async def _cleanup_loop(self):
        """Periodically clean up stale results to prevent memory leaks."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Run cleanup every minute
                self._cleanup_results()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Task cleanup error: %s", e)

    def _cleanup_results(self):
        """Remove expired results and mark stuck tasks as failed."""
        now = time.time()
        to_delete = []

        for task_id, result in self._results.items():
            # Remove completed/failed results older than TTL
            if result.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                if (now - result.updated_at) > _RESULT_TTL_SECONDS:
                    to_delete.append(task_id)
            # Mark stuck RUNNING/PENDING tasks as failed
            elif result.status in (TaskStatus.RUNNING, TaskStatus.PENDING):
                if (now - result.created_at) > _STUCK_TASK_TIMEOUT:
                    result.status = TaskStatus.FAILED
                    result.error = "Task timed out (stuck)"
                    result.updated_at = now
                    logger.warning("Task marked as stuck/failed: %s", task_id)

        for task_id in to_delete:
            del self._results[task_id]

        # Hard cap: if still too many, remove oldest completed/failed
        if len(self._results) > _MAX_RESULTS:
            terminal = sorted(
                [(k, v) for k, v in self._results.items()
                 if v.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)],
                key=lambda x: x[1].updated_at,
            )
            for k, _ in terminal[: len(self._results) - _MAX_RESULTS]:
                del self._results[k]

        if to_delete:
            logger.info("Cleaned up %d stale task results", len(to_delete))

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
