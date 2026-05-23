from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from typing import Callable, Awaitable

from agentguard.monitor.events import AgentEvent, EventType

type AsyncEventHandler = Callable[[AgentEvent], Awaitable[None]]
type SyncEventHandler = Callable[[AgentEvent], None]


class AsyncEventBus:
    """Async event bus with per-type and wildcard subscriptions."""

    def __init__(self, max_queue_size: int = 10_000) -> None:
        self._handlers: defaultdict[str, list[AsyncEventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._task: asyncio.Task[None] | None = None

    def subscribe(self, event_type: EventType | str, handler: AsyncEventHandler) -> None:
        key = event_type.value if isinstance(event_type, EventType) else event_type
        self._handlers[key].append(handler)

    def subscribe_all(self, handler: AsyncEventHandler) -> None:
        self._handlers["*"].append(handler)

    async def publish(self, event: AgentEvent) -> None:
        await self._queue.put(event)

    def publish_nowait(self, event: AgentEvent) -> None:
        self._queue.put_nowait(event)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._process_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _process_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except (asyncio.TimeoutError, TimeoutError):
                continue

            handlers = (
                self._handlers.get(event.type.value, [])
                + self._handlers.get("*", [])
            )
            if handlers:
                await asyncio.gather(
                    *[h(event) for h in handlers],
                    return_exceptions=True,
                )
            self._queue.task_done()

    async def drain(self) -> None:
        await self._queue.join()


class SyncEventBus:
    """Thread-safe synchronous event bus for non-async contexts."""

    def __init__(self) -> None:
        self._handlers: defaultdict[str, list[SyncEventHandler]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: EventType | str, handler: SyncEventHandler) -> None:
        key = event_type.value if isinstance(event_type, EventType) else event_type
        with self._lock:
            self._handlers[key].append(handler)

    def subscribe_all(self, handler: SyncEventHandler) -> None:
        with self._lock:
            self._handlers["*"].append(handler)

    def publish(self, event: AgentEvent) -> None:
        with self._lock:
            handlers = list(
                self._handlers.get(event.type.value, [])
                + self._handlers.get("*", [])
            )
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                pass
