import typer

from .config import load_sites_config
from .pipeline import run_site_scraper

app = typer.Typer()


@app.command()
def list_sites():
    sites = load_sites_config()
    for s in sites:
        status = "ENABLED" if s.enabled else "DISABLED"
        typer.echo(f"{s.id:30} {status}")


@app.command()
def run_all():
    sites = load_sites_config()
    for s in sites:
        if not s.enabled:
            continue
        typer.echo(f"Running site: {s.id}")
        run_site_scraper(s)


@app.command()
def run_site(site_id: str):
    sites = load_sites_config()
    for s in sites:
        if s.id == site_id:
            run_site_scraper(s)
            return
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
