import argparse
import logging

from common_runtime.settings import Settings
from common_storage.local import LocalStorage
from common_storage.models import StoredDocument
from common_storage.snowflake import SnowflakeStorage
from scraper.sites.aspim import AspimScraper
from scraper.sites.banque_france import BanqueFranceScraper
from scraper.sites.bnp_paribas import BNPParibasScraper
from scraper.sites.bnppre_market_france import BNPPREMarketFranceScraper
from scraper.sites.catella import CatellaScraper
from scraper.sites.credit_agricole_immobilier import CreditAgricoleImmobilierScraper
from scraper.sites.cushman_wakefield import CushmanWakefieldScraper
from scraper.sites.fbf import FBFScraper
from scraper.sites.groupe_bpce import GroupeBPCEScraper
from scraper.sites.knight_frank import KnightFrankScraper
from scraper.sites.labanquepostale import LaBanquePostaleScraper
from scraper.sites.leaseo import LeaseoScraper
from scraper.sites.notaires_fr_tendances import NotairesFranceTendancesScraper
from scraper.sites.notaires_grand_paris import NotairesGrandParisScraper
from scraper.sites.observatoire_credit_logement import ObservatoireCreditLogementScraper
from scraper.sites.savills import SavillsScraper
from scraper.sites.societe_generale import SocieteGeneraleScraper
from scraper.sites.wargny_katz import WargnyKatzScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper.run")


SCRAPER_REGISTRY = {
    "fbf": FBFScraper,
    "observatoire": ObservatoireCreditLogementScraper,
    "banque_france": BanqueFranceScraper,
    "credit_agricole_immobilier": CreditAgricoleImmobilierScraper,
    "labanquepostale": LaBanquePostaleScraper,
    "societe_generale": SocieteGeneraleScraper,
    "groupe_bpce": GroupeBPCEScraper,
    "bnp_paribas": BNPParibasScraper,
    "wargny_katz": WargnyKatzScraper,
    "notaires_grand_paris": NotairesGrandParisScraper,
    "notaires_fr_tendances": NotairesFranceTendancesScraper,
    "catella": CatellaScraper,
    "savills": SavillsScraper,
    "knight_frank": KnightFrankScraper,
    "leaseo": LeaseoScraper,
    "cushman_wakefield": CushmanWakefieldScraper,
    "aspim": AspimScraper,
    "bnppre_market_france": BNPPREMarketFranceScraper,
}


def build_scrapers(site_names=None, max_pages: int | None = None):
    if not site_names:
        scrapers = [cls() for cls in SCRAPER_REGISTRY.values()]
    else:
        unknown = [name for name in site_names if name not in SCRAPER_REGISTRY]
        if unknown:
            raise ValueError(
                f"Unknown site(s): {', '.join(unknown)}. "
                f"Available sites: {', '.join(SCRAPER_REGISTRY.keys())}"
            )
        scrapers = [SCRAPER_REGISTRY[name]() for name in site_names]

    # Appliquer max_pages aux scrapers qui le supportent
    for s in scrapers:
        if hasattr(s, "set_max_pages"):
            s.set_max_pages(max_pages)

    return scrapers


def build_storage_backend():
    if Settings.storage_backend == "snowflake":
        return SnowflakeStorage.from_env()
    return LocalStorage(output_dir="output")


def map_resource_to_document(source_name: str, resource) -> StoredDocument:
    mime_type = (
        "application/pdf"
        if getattr(resource, "type", None) and str(resource.type).endswith("PDF")
        else "text/html"
    )
    content = getattr(resource, "raw_content", None)
    text_content = getattr(resource, "text", None)

    return StoredDocument(
        source_name=source_name,
        source_url=(resource.meta or {}).get("listing_url"),
        document_url=resource.url,
        title=resource.title,
        document_type="pdf" if mime_type == "application/pdf" else "html",
        mime_type=mime_type,
        content=content,
        text_content=text_content,
        external_id=resource.url,
        metadata=resource.meta or {},
    )


def pick_best_text(resource):
    meta = resource.meta or {}

    if resource.text and resource.text.strip():
        if meta.get("pdf_text") and resource.text == meta.get("pdf_text"):
            return resource.text, "pdf"
        if meta.get("html_text") and resource.text == meta.get("html_text"):
            return resource.text, "html"
        return resource.text, "text"

    if meta.get("pdf_text"):
        return meta["pdf_text"], "pdf"

    if meta.get("html_text"):
        return meta["html_text"], "html"

    return None, "none"


def serialize_resource(resource):
    meta = resource.meta or {}
    best_text, content_source = pick_best_text(resource)

    return {
        "title": resource.title,
        "url": resource.url,
        "type": getattr(resource.type, "value", str(resource.type)),
        "content_source": content_source,
        "text": best_text,
        "pdf_url": meta.get("pdf_url"),
        "listing_url": meta.get("listing_url"),
        "source_html": meta.get("source_html"),
        "meta": meta,
    }


def compute_summary(results):
    summary = {
        "total": len(results),
        "with_text": 0,
        "without_text": 0,
        "content_source_pdf": 0,
        "content_source_html": 0,
        "content_source_other": 0,
        "with_pdf_url": 0,
        "fetch_error": 0,
        "pdf_error": 0,
        "run_error": 0,
    }

    for item in results:
        text = item.get("text")
        meta = item.get("meta") or {}
        content_source = item.get("content_source")

        if text and str(text).strip():
            summary["with_text"] += 1
        else:
            summary["without_text"] += 1

        if content_source == "pdf":
            summary["content_source_pdf"] += 1
        elif content_source == "html":
            summary["content_source_html"] += 1
        else:
            summary["content_source_other"] += 1

        if item.get("pdf_url"):
            summary["with_pdf_url"] += 1

        if meta.get("fetch_error"):
            summary["fetch_error"] += 1

        if meta.get("pdf_error"):
            summary["pdf_error"] += 1

        if item.get("error"):
            summary["run_error"] += 1

    return summary


def log_summary(scraper_name, summary):
    logger.info(
        (
            "[%s] total=%d | with_text=%d | without_text=%d | "
            "source_pdf=%d | source_html=%d | other=%d | "
            "pdf_url=%d | fetch_error=%d | pdf_error=%d | run_error=%d"
        ),
        scraper_name,
        summary["total"],
        summary["with_text"],
        summary["without_text"],
        summary["content_source_pdf"],
        summary["content_source_html"],
        summary["content_source_other"],
        summary["with_pdf_url"],
        summary["fetch_error"],
        summary["pdf_error"],
        summary["run_error"],
    )


def run_scraper(scraper):
    logger.info("Running scraper: %s", scraper.__class__.__name__)
    output = []

    for listing_url in scraper.iter_listing_urls():
        logger.info("Listing: %s", listing_url)

        resp = scraper.session.get(listing_url, timeout=30)
        resp.raise_for_status()
        resources = scraper.extract_resources_from_listing(resp.text, listing_url)

        logger.info("Found %d resources", len(resources))

        for resource in resources:
            try:
                resource = scraper.extract_content(resource)
                output.append(serialize_resource(resource))
            except Exception as e:
                logger.exception("Failed on resource %s: %s", resource.url, e)
                output.append(
                    {
                        "title": resource.title,
                        "url": resource.url,
                        "type": getattr(resource.type, "value", str(resource.type)),
                        "content_source": "error",
                        "text": None,
                        "pdf_url": (resource.meta or {}).get("pdf_url"),
                        "listing_url": (resource.meta or {}).get("listing_url"),
                        "source_html": (resource.meta or {}).get("source_html"),
                        "meta": resource.meta or {},
                        "error": str(e),
                    }
                )

    return output


def parse_args():
    parser = argparse.ArgumentParser(description="Run site scrapers")
    parser.add_argument(
        "--site",
        action="append",
        dest="sites",
        help=(
            "Site to run. Can be repeated. "
            f"Available: {', '.join(SCRAPER_REGISTRY.keys())}"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory (default: output)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Max number of listing pages per site (default: no limit)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    scrapers = build_scrapers(args.sites, max_pages=args.max_pages)

    storage = build_storage_backend()

    all_summaries = {}

    for scraper in scrapers:
        scraper_name = scraper.__class__.__name__
        source_name = scraper_name

        logger.info("Running scraper: %s", scraper_name)

        # stats pour ce run
        processed = inserted = skipped = errors = 0
        results: list[dict] = []

        # --- nouveau : début de run Snowflake ---
        run_id = None
        if hasattr(storage, "start_run"):
            try:
                run_id = storage.start_run(source_name=source_name, metadata=None)
            except Exception as e:
                logger.exception("Failed to start run for %s: %s", source_name, e)
        # ----------------------------------------

        try:
            # 1. collecter toutes les resources comme avant
            raw_resources = []
            for listing_url in scraper.iter_listing_urls():
                logger.info("Listing: %s", listing_url)

                resp = scraper.session.get(listing_url, timeout=30)
                resp.raise_for_status()
                resources = scraper.extract_resources_from_listing(
                    resp.text, listing_url
                )

                logger.info("Found %d resources", len(resources))
                raw_resources.extend(resources)

            # 2. traiter les resources
            for resource in raw_resources:
                processed += 1
                try:
                    resource = scraper.extract_content(resource)
                    serialized = serialize_resource(resource)
                    results.append(serialized)

                    doc_url = serialized.get("url")
                    if hasattr(storage, "exists") and storage.exists(
                        source_name=source_name, document_url=doc_url
                    ):
                        skipped += 1
                        continue

                    doc = map_resource_to_document(source_name, resource)
                    storage.save_document(doc)
                    inserted += 1

                except Exception as e:
                    errors += 1
                    logger.exception("Failed on resource %s: %s", resource.url, e)

                    serialized = {
                        "title": resource.title,
                        "url": resource.url,
                        "type": getattr(resource.type, "value", str(resource.type)),
                        "content_source": "error",
                        "text": None,
                        "pdf_url": (resource.meta or {}).get("pdf_url"),
                        "listing_url": (resource.meta or {}).get("listing_url"),
                        "source_html": (resource.meta or {}).get("source_html"),
                        "meta": resource.meta or {},
                        "error": str(e),
                    }
                    results.append(serialized)

                    # --- nouveau : log_error Snowflake ---
                    if run_id and hasattr(storage, "log_error"):
                        try:
                            from common_storage.models import StoredError

                            err = StoredError(
                                run_id=run_id,
                                source_name=source_name,
                                url=resource.url,
                                step="extract_or_save",
                                error_type=type(e).__name__,
                                error_message=str(e),
                                error_stack="",
                                metadata=resource.meta or {},
                            )
                            storage.log_error(err)
                        except Exception as log_e:
                            logger.exception(
                                "Failed to log error for %s: %s", resource.url, log_e
                            )
                    # -------------------------------------

            # 3. résumé + logs
            summary = compute_summary(results)
            all_summaries[scraper_name] = summary
            log_summary(scraper_name, summary)

            logger.info(
                "[%s] processed=%d | inserted=%d | skipped=%d | errors=%d",
                scraper_name,
                processed,
                inserted,
                skipped,
                errors,
            )

            # --- nouveau : fin de run OK ---
            if run_id and hasattr(storage, "finish_run"):
                try:
                    storage.finish_run(
                        run_id=run_id,
                        status="SUCCESS" if errors == 0 else "PARTIAL_SUCCESS",
                        stats={
                            "processed": processed,
                            "inserted": inserted,
                            "skipped": skipped,
                            "errors": errors,
                        },
                        message=None,
                    )
                except Exception as e:
                    logger.exception("Failed to finish run for %s: %s", source_name, e)
            # --------------------------------

        except Exception as e:
            logger.exception("Fatal error in scraper %s: %s", scraper_name, e)

            # --- nouveau : fin de run en échec ---
            if run_id and hasattr(storage, "finish_run"):
                try:
                    storage.finish_run(
                        run_id=run_id,
                        status="FAILED",
                        stats={
                            "processed": processed,
                            "inserted": inserted,
                            "skipped": skipped,
                            "errors": errors + 1,
                        },
                        message=str(e),
                    )
                except Exception as fe:
                    logger.exception(
                        "Failed to finish FAILED run for %s: %s", source_name, fe
                    )
            # -------------------------------------

    # Si tu veux garder le behaviour multi-sites global, tu peux encore calculer un résumé global
    if len(scrapers) > 1:
        logger.info("==== Global summary ====")
        for scraper_name, summary in all_summaries.items():
            log_summary(scraper_name, summary)


if __name__ == "__main__":
    main()
