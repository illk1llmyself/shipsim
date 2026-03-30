from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from shipsim.broadcaster import TelemetryBroadcaster
from shipsim.fleet import FleetRunner

WEB_DIR = Path(__file__).parent / "web"


def create_app(catalog_path: str | Path = "scenarios/world_fleet.json") -> FastAPI:
    runner = FleetRunner()
    broadcaster = TelemetryBroadcaster()
    runner.add_listener(broadcaster.publish)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        broadcaster.set_loop(asyncio.get_running_loop())
        runner.start(catalog_path)
        try:
            yield
        finally:
            runner.stop()

    app = FastAPI(
        title="shipsim API",
        version="0.2.0",
        description="Always-on global shipping simulator for web and mobile clients.",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/fleet/routes")
    def fleet_routes() -> dict[str, object]:
        return {"items": runner.routes()}

    @app.get("/fleet/current")
    def fleet_current() -> dict[str, object]:
        latest = runner.latest()
        if latest is None:
            raise HTTPException(status_code=404, detail="Fleet telemetry is not ready yet.")
        return latest.model_dump(mode="json")

    @app.get("/fleet/current/{route_id}")
    def fleet_current_route(route_id: str) -> dict[str, object]:
        latest = runner.latest()
        if latest is None:
            raise HTTPException(status_code=404, detail="Fleet telemetry is not ready yet.")
        for item in latest.items:
            if item.meta.get("id") == route_id:
                return item.model_dump(mode="json")
        raise HTTPException(status_code=404, detail="Route not found.")

    @app.get("/fleet/history")
    def fleet_history(limit: int = 10) -> list[dict[str, object]]:
        return [snapshot.model_dump(mode="json") for snapshot in runner.history(limit)]

    @app.get("/fleet/incidents")
    def fleet_incidents() -> dict[str, object]:
        latest = runner.latest()
        if latest is None:
            raise HTTPException(status_code=404, detail="Fleet telemetry is not ready yet.")
        return {
            "faults": [
                {"route_id": item.meta.get("id"), "ship": item.meta.get("ship_name"), "items": [fault.model_dump(mode="json") for fault in item.faults]}
                for item in latest.items
                if item.faults
            ],
            "events": [
                {"route_id": item.meta.get("id"), "ship": item.meta.get("ship_name"), "items": [event.model_dump(mode="json") for event in item.scenario_events]}
                for item in latest.items
                if item.scenario_events
            ],
            "alarm_history": [
                {"route_id": item.meta.get("id"), "ship": item.meta.get("ship_name"), "items": [entry.model_dump(mode="json") for entry in item.alarm_history]}
                for item in latest.items
                if item.alarm_history
            ],
        }

    @app.get("/simulation/status")
    def simulation_status() -> dict[str, object]:
        return runner.status()

    @app.get("/telemetry/current")
    def telemetry_current() -> dict[str, object]:
        latest = runner.latest()
        if latest is None:
            raise HTTPException(status_code=404, detail="Fleet telemetry is not ready yet.")
        return latest.model_dump(mode="json")

    @app.websocket("/ws/fleet")
    async def fleet_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = broadcaster.subscribe()
        try:
            latest = runner.latest()
            if latest is not None:
                await websocket.send_json(latest.model_dump(mode="json"))

            while True:
                snapshot = await queue.get()
                await websocket.send_json(snapshot.model_dump(mode="json"))
        except WebSocketDisconnect:
            pass
        finally:
            broadcaster.unsubscribe(queue)

    @app.websocket("/ws/telemetry")
    async def telemetry_socket(websocket: WebSocket) -> None:
        await fleet_socket(websocket)

    return app
