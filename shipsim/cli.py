from __future__ import annotations

import time
from pathlib import Path

import typer
import uvicorn

from shipsim.api import create_app
from shipsim.fleet import FleetRunner

app = typer.Typer(help="Always-on global ship traffic simulator.")


@app.command()
def run(
    catalog: Path = typer.Option(Path("scenarios/world_fleet.json"), exists=True, readable=True),
    refresh_seconds: float = typer.Option(2.0, min=0.5),
) -> None:
    """Print a compact summary of the active fleet in the terminal."""
    runner = FleetRunner()
    runner.start(catalog)
    typer.echo(f"Fleet started from catalog: {catalog}")

    try:
        while True:
            latest = runner.latest()
            if latest is not None:
                typer.echo(
                    f"[TICK {latest.tick:04d}] routes={latest.summary['active_routes']} "
                    f"alerts={latest.summary['total_alerts']} countries={len(latest.summary['countries'])}"
                )
                for item in latest.items[:6]:
                    typer.echo(
                        f"  - {item.meta['name']}: "
                        f"{item.ship['latitude']:.2f},{item.ship['longitude']:.2f} "
                        f"{item.ship['speed_knots']:.1f}kn alerts={len(item.alerts)}"
                    )
            time.sleep(refresh_seconds)
    except KeyboardInterrupt:
        typer.echo("Stopping fleet...")
    finally:
        runner.stop()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0"),
    port: int = typer.Option(8000, min=1, max=65535),
    catalog: Path = typer.Option(Path("scenarios/world_fleet.json"), exists=True, readable=True),
) -> None:
    """Run the API server with the auto-starting global fleet dashboard."""
    uvicorn.run(create_app(catalog_path=catalog), host=host, port=port)


if __name__ == "__main__":
    app()
