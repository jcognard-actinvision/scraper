from scraper.core.simple_pdf_listing import PdfListingConfig, SimplePdfListingScraper


class BNPPREMarketFranceScraper(SimplePdfListingScraper):
    config = PdfListingConfig(
        listing_base_url=(
            "https://www.realestate.bnpparibas.fr/fr/etudes-tendances/etudes-de-marche-France?page=0"
        ),
        page_param="page",
        link_selector="div.content article a[href]",
        pdf_selector="article div.file-download a[href]",  # 1er lien PDF dans l’article
        base_url_for_join="https://www.realestate.bnpparibas.fr",
    )
