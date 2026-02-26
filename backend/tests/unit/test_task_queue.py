"""Unit tests for TaskQueue — async task execution, results, graceful shutdown."""

import asyncio

import pytest

from app.services.task_queue import TaskQueue, TaskStatus


class TestTaskQueueLifecycle:
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        q = TaskQueue(max_concurrent=2)
        await q.start()
        await q.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        q = TaskQueue(max_concurrent=1)
        await q.stop()  # should not raise


class TestTaskExecution:
    @pytest.mark.asyncio
    async def test_enqueue_and_complete(self):
        q = TaskQueue(max_concurrent=2)
        await q.start()

        async def add(a, b):
            return a + b

        task_id = await q.enqueue("t1", add, 2, 3)
        await asyncio.sleep(0.2)

        result = q.get_result(task_id)
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == 5

        await q.stop()

    @pytest.mark.asyncio
    async def test_failing_task(self):
        q = TaskQueue(max_concurrent=1)
        await q.start()

        async def fail():
            raise ValueError("intentional failure")

        task_id = await q.enqueue("fail1", fail)
        await asyncio.sleep(0.2)

        result = q.get_result(task_id)
        assert result is not None
        assert result.status == TaskStatus.FAILED
        assert "intentional failure" in str(result.error)

        await q.stop()

    @pytest.mark.asyncio
    async def test_callback_on_completion(self):
        q = TaskQueue(max_concurrent=1)
        await q.start()

        callback_results = []

        async def my_task():
            return 42

        async def my_callback(result):
            callback_results.append(result)

        await q.enqueue("cb_test", my_task, callback=my_callback)
        await asyncio.sleep(0.3)

        assert len(callback_results) == 1

        await q.stop()

    @pytest.mark.asyncio
    async def test_get_result_unknown_task(self):
        q = TaskQueue(max_concurrent=1)
        assert q.get_result("nonexistent") is None

    @pytest.mark.asyncio
    async def test_concurrent_tasks(self):
        q = TaskQueue(max_concurrent=3)
        await q.start()

        results = []

        async def work(n):
            await asyncio.sleep(0.05)
            return n * 2

        ids = []
        for i in range(5):
            tid = await q.enqueue(f"t{i}", work, i)
            ids.append(tid)

        await asyncio.sleep(0.5)

        for tid in ids:
            r = q.get_result(tid)
            assert r is not None
            assert r.status == TaskStatus.COMPLETED

        await q.stop()
