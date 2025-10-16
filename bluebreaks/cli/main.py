"""
CLI tool for Remote Surf
"""

import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table

from bluebreaks import __version__

app = typer.Typer(
    name="bluebreaks",
    help="Remote Surf CLI - Find unknown surf from oceanographic data",
    add_completion=False,
)
console = Console()


@app.command()
def version() -> None:
    """Show version information"""
    console.print(f"BlueBreaks v{__version__}")


@app.command()
def scan(
    grib: Path = typer.Option(..., help="Path to GRIB file (WW3/GFS)"),
    bbox: str = typer.Option(..., help="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    out: Path = typer.Option("results.geojson", help="Output GeoJSON file"),
    time: Optional[str] = typer.Option(None, help="ISO 8601 timestamp"),
    min_score: float = typer.Option(0.0, help="Minimum score threshold (0-10)"),
) -> None:
    """
    Scan a coastline for surf candidates using GRIB data

    Example:
        bluebreaks scan --grib ww3.grb2 --bbox -116,22,-109,28 --out results.geojson
    """
    console.print(f"[bold blue]Scanning coastline...[/bold blue]")
    console.print(f"  GRIB: {grib}")
    console.print(f"  BBox: {bbox}")
    console.print(f"  Min Score: {min_score}")

    # TODO: Implement actual scanning logic
    console.print("[yellow]⚠ Not yet implemented[/yellow]")


@app.command()
def rank(
    time: str = typer.Option(..., help="ISO 8601 timestamp"),
    top: int = typer.Option(50, help="Number of top spots to show"),
    min_score: float = typer.Option(5.0, help="Minimum score threshold"),
) -> None:
    """
    Rank and display top surf spots for a specific time

    Example:
        bluebreaks rank --time 2025-10-18T12:00 --top 50
    """
    console.print(f"[bold blue]Ranking top {top} spots...[/bold blue]")
    console.print(f"  Time: {time}")
    console.print(f"  Min Score: {min_score}")

    # TODO: Implement ranking logic

    # Mock table
    table = Table(title=f"Top {top} Surf Spots")
    table.add_column("Rank", style="cyan", no_wrap=True)
    table.add_column("Score", style="magenta")
    table.add_column("Location", style="green")
    table.add_column("Break Type", style="yellow")

    table.add_row("1", "8.2", "26.543°N, 111.234°W", "Point/Reef")
    table.add_row("2", "7.8", "26.521°N, 111.198°W", "Beach")

    console.print(table)
    console.print("[yellow]⚠ Using mock data - not yet implemented[/yellow]")


@app.group()
def data() -> None:
    """Data management commands"""
    pass


@data.command("import")
def data_import(
    grib: Optional[Path] = typer.Option(None, help="Path to GRIB file"),
    bathy: Optional[Path] = typer.Option(None, help="Path to bathymetry file (GeoTIFF/NetCDF)"),
    coastline: Optional[Path] = typer.Option(None, help="Path to coastline shapefile"),
) -> None:
    """
    Import and cache data files

    Example:
        bluebreaks data import --grib forecast.grb2 --bathy gebco.tif
    """
    console.print("[bold blue]Importing data...[/bold blue]")

    if grib:
        console.print(f"  GRIB: {grib}")
    if bathy:
        console.print(f"  Bathymetry: {bathy}")
    if coastline:
        console.print(f"  Coastline: {coastline}")

    # TODO: Implement data import
    console.print("[yellow]⚠ Not yet implemented[/yellow]")


@data.command("list")
def data_list() -> None:
    """List cached data files"""
    console.print("[bold blue]Cached data:[/bold blue]")
    # TODO: List actual cached data
    console.print("[yellow]⚠ Not yet implemented[/yellow]")


if __name__ == "__main__":
    app()
