from typing import Annotated

from fastapi import FastAPI, HTTPException, Query

from gmail_fetcher.fetch_gmail import run_gmail_fetcher
from scraper.run import SCRAPER_REGISTRY, run_scraper_job

app = FastAPI(title="Stonelake Scraper")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/sites")
def list_sites():
    return {"sites": list(SCRAPER_REGISTRY.keys())}


@app.post("/run/scrapers")
def run_scrapers(
    site: Annotated[list[str] | None, Query()] = None,
    output_dir: str = "output",
    max_pages: int | None = None,
    list_sites: bool = False,
):
    try:
        result = run_scraper_job(
            sites=site,
            output_dir=output_dir,
            max_pages=max_pages,
            list_sites=list_sites,
        )
        return {"status": "ok", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run/gmail")
def run_gmail():
    try:
        result = run_gmail_fetcher()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run/all")
def run_all(
    site: Annotated[list[str] | None, Query()] = None,
    output_dir: str = "output",
    max_pages: int | None = None,
):
    try:
        scraper_result = run_scraper_job(
            sites=site,
            output_dir=output_dir,
            max_pages=max_pages,
        )
        gmail_result = run_gmail_fetcher()
        return {
            "status": "ok",
            "result": {
                "scrapers": scraper_result,
                "gmail": gmail_result,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
