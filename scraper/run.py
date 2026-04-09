import argparse
import logging
from urllib.parse import urlsplit, urlunsplit

from common_runtime.notifications import send_error_notification
from common_runtime.settings import Settings
from common_storage.local import LocalStorage
from common_storage.models import StoredDocument, StoredError
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


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return url

    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = (parts.netloc or "").lower()

    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    return urlunsplit((scheme, netloc, path, "", ""))


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

    for scraper in scrapers:
        if hasattr(scraper, "set_max_pages"):
            scraper.set_max_pages(max_pages)

    return scrapers


def build_storage_backend(output_dir: str = "output"):
    if Settings.storage_backend == "snowflake":
        return SnowflakeStorage.from_env()
    return LocalStorage(output_dir=output_dir)


def log_and_notify_error(storage, err: StoredError):
    try:
        if hasattr(storage, "log_and_notify_error"):
            storage.log_and_notify_error(err)
            return

        if hasattr(storage, "log_error"):
            storage.log_error(err)

        send_error_notification(
            source_name=err.source_name,
            step=err.step,
            error_type=err.error_type,
            error_message=err.error_message,
            run_id=err.run_id,
            url=err.url,
            metadata=err.metadata,
        )
    except Exception as notify_exc:
        logger.exception(
            "Failed to log/notify error for source=%s url=%s: %s",
            err.source_name,
            err.url,
            notify_exc,
        )


def map_resource_to_document(source_name: str, resource) -> StoredDocument:
    mime_type = (
        "application/pdf"
        if getattr(resource, "type", None) and str(resource.type).endswith("PDF")
        else "text/html"
    )

    canonical_document_url = canonicalize_url(resource.url)
    canonical_source_url = canonicalize_url((resource.meta or {}).get("listing_url"))

    return StoredDocument(
        source_name=source_name,
        source_url=canonical_source_url,
        document_url=canonical_document_url,
        title=resource.title,
        document_type="pdf" if mime_type == "application/pdf" else "html",
        mime_type=mime_type,
        content=getattr(resource, "raw_content", None),
        text_content=getattr(resource, "text", None),
        external_id=canonical_document_url,
        metadata={
            **(resource.meta or {}),
            "canonical_document_url": canonical_document_url,
            "canonical_source_url": canonical_source_url,
            "original_document_url": resource.url,
        },
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
    canonical_document_url = canonicalize_url(resource.url)
    canonical_listing_url = canonicalize_url(meta.get("listing_url"))

    return {
        "title": resource.title,
        "url": canonical_document_url,
        "original_url": resource.url,
        "type": getattr(resource.type, "value", str(resource.type)),
        "content_source": content_source,
        "text": best_text,
        "pdf_url": meta.get("pdf_url"),
        "listing_url": canonical_listing_url,
        "source_html": meta.get("source_html"),
        "meta": {
            **meta,
            "canonical_document_url": canonical_document_url,
            "canonical_listing_url": canonical_listing_url,
        },
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
        "skipped_incremental": 0,
    }

    for item in results:
        text = item.get("text")
        meta = item.get("meta") or {}
        content_source = item.get("content_source")

        if item.get("skipped_incremental"):
            summary["skipped_incremental"] += 1

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
            "pdf_url=%d | fetch_error=%d | pdf_error=%d | "
            "run_error=%d | skipped_incremental=%d"
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
        summary["skipped_incremental"],
    )


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
    parser.add_argument(
        "--list-sites",
        action="store_true",
        help="Lister les sites disponibles et quitter",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_sites:
        print("Available sites:")
        for name in SCRAPER_REGISTRY.keys():
            print(f"- {name}")
        return

    scrapers = build_scrapers(args.sites, max_pages=args.max_pages)
    storage = build_storage_backend(output_dir=args.output_dir)

    all_summaries = {}

    for scraper in scrapers:
        scraper_name = scraper.__class__.__name__
        source_name = scraper_name

        logger.info("Running scraper: %s", scraper_name)

        processed = 0
        inserted = 0
        skipped = 0
        errors = 0
        results: list[dict] = []

        run_id = None
        if hasattr(storage, "start_run"):
            try:
                run_id = storage.start_run(source_name=source_name, metadata=None)
            except Exception as e:
                logger.exception("Failed to start run for %s: %s", source_name, e)

        try:
            stop_after_listing = False

            for listing_url in scraper.iter_listing_urls():
                if stop_after_listing:
                    logger.info(
                        "[%s] incremental stop activated, skipping remaining listings",
                        scraper_name,
                    )
                    break

                logger.info("Listing: %s", listing_url)

                try:
                    resp = scraper.session.get(listing_url, timeout=30)
                    resp.raise_for_status()
                    resources = scraper.extract_resources_from_listing(
                        resp.text,
                        listing_url,
                    )
                    logger.info("Found %d resources", len(resources))
                except Exception as e:
                    errors += 1
                    logger.exception("Failed on listing %s: %s", listing_url, e)

                    err = StoredError(
                        run_id=run_id or "",
                        source_name=source_name,
                        url=canonicalize_url(listing_url),
                        step="listing_fetch",
                        error_type=type(e).__name__,
                        error_message=str(e),
                        error_stack="",
                        metadata={
                            "listing_url": canonicalize_url(listing_url),
                            "original_listing_url": listing_url,
                            "scraper": scraper_name,
                            "max_pages": args.max_pages,
                        },
                    )
                    log_and_notify_error(storage, err)
                    continue

                if not resources:
                    logger.info(
                        "[%s] no resources found on listing %s",
                        scraper_name,
                        listing_url,
                    )
                    continue

                known_in_listing = 0
                new_in_listing = 0

                for resource in resources:
                    processed += 1

                    original_doc_url = resource.url
                    doc_url = canonicalize_url(original_doc_url)
                    already_exists = False

                    try:
                        logger.info(
                            "[%s] exists check | source_name=%s | original_url=%s | canonical_url=%s",
                            scraper_name,
                            source_name,
                            original_doc_url,
                            doc_url,
                        )

                        if hasattr(storage, "exists"):
                            already_exists = storage.exists(
                                source_name=source_name,
                                document_url=doc_url,
                            )

                        logger.info(
                            "[%s] exists result | canonical_url=%s | already_exists=%s",
                            scraper_name,
                            doc_url,
                            already_exists,
                        )
                    except Exception as e:
                        logger.exception(
                            "Failed during exists() check for %s: %s",
                            doc_url,
                            e,
                        )
                        err = StoredError(
                            run_id=run_id or "",
                            source_name=source_name,
                            url=doc_url,
                            step="exists_check",
                            error_type=type(e).__name__,
                            error_message=str(e),
                            error_stack="",
                            metadata={
                                **(resource.meta or {}),
                                "original_document_url": original_doc_url,
                                "canonical_document_url": doc_url,
                            },
                        )
                        log_and_notify_error(storage, err)

                    if already_exists:
                        skipped += 1
                        known_in_listing += 1
                        logger.info(
                            "[%s] incremental skip before extract_content: %s",
                            scraper_name,
                            doc_url,
                        )
                        results.append(
                            {
                                "title": resource.title,
                                "url": doc_url,
                                "original_url": original_doc_url,
                                "type": getattr(
                                    resource.type, "value", str(resource.type)
                                ),
                                "content_source": "skipped_incremental",
                                "text": None,
                                "pdf_url": (resource.meta or {}).get("pdf_url"),
                                "listing_url": canonicalize_url(
                                    (resource.meta or {}).get("listing_url")
                                ),
                                "source_html": (resource.meta or {}).get("source_html"),
                                "meta": {
                                    **(resource.meta or {}),
                                    "canonical_document_url": doc_url,
                                    "original_document_url": original_doc_url,
                                },
                                "skipped_incremental": True,
                            }
                        )
                        continue

                    new_in_listing += 1

                    try:
                        logger.info(
                            "[%s] extracting new resource: %s",
                            scraper_name,
                            doc_url,
                        )
                        resource = scraper.extract_content(resource)
                        serialized = serialize_resource(resource)
                        results.append(serialized)

                        doc = map_resource_to_document(source_name, resource)
                        storage.save_document(doc)
                        inserted += 1
                    except Exception as e:
                        errors += 1
                        logger.exception(
                            "Failed on resource %s: %s",
                            original_doc_url,
                            e,
                        )

                        results.append(
                            {
                                "title": resource.title,
                                "url": doc_url,
                                "original_url": original_doc_url,
                                "type": getattr(
                                    resource.type, "value", str(resource.type)
                                ),
                                "content_source": "error",
                                "text": None,
                                "pdf_url": (resource.meta or {}).get("pdf_url"),
                                "listing_url": canonicalize_url(
                                    (resource.meta or {}).get("listing_url")
                                ),
                                "source_html": (resource.meta or {}).get("source_html"),
                                "meta": {
                                    **(resource.meta or {}),
                                    "canonical_document_url": doc_url,
                                    "original_document_url": original_doc_url,
                                },
                                "error": str(e),
                            }
                        )

                        err = StoredError(
                            run_id=run_id or "",
                            source_name=source_name,
                            url=doc_url,
                            step="extract_or_save",
                            error_type=type(e).__name__,
                            error_message=str(e),
                            error_stack="",
                            metadata={
                                **(resource.meta or {}),
                                "canonical_document_url": doc_url,
                                "original_document_url": original_doc_url,
                            },
                        )
                        log_and_notify_error(storage, err)

                logger.info(
                    "[%s] listing summary | listing_url=%s | new=%d | known=%d",
                    scraper_name,
                    canonicalize_url(listing_url),
                    new_in_listing,
                    known_in_listing,
                )

                if known_in_listing == len(resources):
                    logger.info(
                        "[%s] all resources in listing already known; stopping incremental run",
                        scraper_name,
                    )
                    stop_after_listing = True

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

        except Exception as e:
            errors += 1
            logger.exception("Fatal error in scraper %s: %s", scraper_name, e)

            err = StoredError(
                run_id=run_id or "",
                source_name=source_name,
                url=None,
                step="listing_or_run",
                error_type=type(e).__name__,
                error_message=str(e),
                error_stack="",
                metadata={
                    "scraper": scraper_name,
                    "sites": args.sites,
                    "max_pages": args.max_pages,
                },
            )
            log_and_notify_error(storage, err)

            if run_id and hasattr(storage, "finish_run"):
                try:
                    storage.finish_run(
                        run_id=run_id,
                        status="FAILED",
                        stats={
                            "processed": processed,
                            "inserted": inserted,
                            "skipped": skipped,
                            "errors": errors,
                        },
                        message=str(e),
                    )
                except Exception as fe:
                    logger.exception(
                        "Failed to finish FAILED run for %s: %s",
                        source_name,
                        fe,
                    )

    if len(scrapers) > 1:
        logger.info("==== Global summary ====")
        for scraper_name, summary in all_summaries.items():
            log_summary(scraper_name, summary)


if __name__ == "__main__":
    main()
