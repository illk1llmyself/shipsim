from __future__ import annotations

import asyncio

from shipsim.models import FleetSnapshot


class TelemetryBroadcaster:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[FleetSnapshot]] = set()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[FleetSnapshot]:
        queue: asyncio.Queue[FleetSnapshot] = asyncio.Queue(maxsize=5)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[TelemetrySnapshot]) -> None:
        self._subscribers.discard(queue)

    def publish(self, snapshot: FleetSnapshot) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._dispatch, snapshot)

    def _dispatch(self, snapshot: FleetSnapshot) -> None:
        for queue in list(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(snapshot)
            except asyncio.QueueFull:
                pass
