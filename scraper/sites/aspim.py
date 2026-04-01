from scraper.core.simple_pdf_listing import PdfListingConfig, SimplePdfListingScraper


class AspimScraper(SimplePdfListingScraper):
    config = PdfListingConfig(
        listing_base_url=(
            "https://www.aspim.fr/documentation/"
            "?_restriction=public&_sorting=date_desc&_paged=1"
        ),
        page_param="_paged",
        link_selector="div.card-document h3 a.no-icon[href]",
        pdf_selector=None,  # lien direct PDF
        base_url_for_join="https://www.aspim.fr",
    )
