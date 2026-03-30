from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, Deque

from shipsim.engine import SimulationEngine
from shipsim.models import ScenarioConfig, TelemetrySnapshot
from shipsim.scenario import load_scenario


SnapshotListener = Callable[[TelemetrySnapshot], None]


class SimulationRunner:
    def __init__(self, history_limit: int = 300) -> None:
        self._history: Deque[TelemetrySnapshot] = deque(maxlen=history_limit)
        self._latest: TelemetrySnapshot | None = None
        self._scenario: ScenarioConfig | None = None
        self._listeners: list[SnapshotListener] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def add_listener(self, listener: SnapshotListener) -> None:
        self._listeners.append(listener)

    def start(self, scenario_path: str | Path) -> None:
        with self._lock:
            if self.is_running():
                raise RuntimeError("Simulation is already running.")

            self._scenario = load_scenario(scenario_path)
            self._history.clear()
            self._latest = None
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def latest(self) -> TelemetrySnapshot | None:
        with self._lock:
            return self._latest

    def history(self, limit: int = 50) -> list[TelemetrySnapshot]:
        with self._lock:
            return list(self._history)[-limit:]

    def status(self) -> dict[str, object]:
        latest = self.latest()
        return {
            "running": self.is_running(),
            "scenario": self._scenario.name if self._scenario else None,
            "tick_rate_hz": self._scenario.tick_rate_hz if self._scenario else None,
            "latest_tick": latest.tick if latest else None,
            "last_timestamp": latest.timestamp.isoformat() if latest else None,
        }

    def _run_loop(self) -> None:
        assert self._scenario is not None
        engine = SimulationEngine(self._scenario)
        dt = 1 / max(self._scenario.tick_rate_hz, 0.1)

        while not self._stop_event.is_set():
            snapshot = engine.step(dt)
            with self._lock:
                self._latest = snapshot
                self._history.append(snapshot)

            for listener in self._listeners:
                listener(snapshot)

            time.sleep(dt)
