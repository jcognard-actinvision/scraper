from scraper.core.simple_pdf_listing import PdfListingConfig, SimplePdfListingScraper


class CreditAgricoleImmobilierScraper(SimplePdfListingScraper):
    """
    Crédit Agricole Immobilier – Études économiques.

    Listing :
      https://etudes-economiques.credit-agricole.com/fr/recherche
      avec paramètres :
        - search_api_fulltext=immobilier
        - search_mode=all
        - page=N (0,1,2,...)

    Sur chaque ligne :
      - lien PDF : a.btn-download[href]
      - titre : .search-engine-result-title / h2 / h3 / a ...
    """

    config = PdfListingConfig(
        listing_base_url=(
            "https://etudes-economiques.credit-agricole.com/fr/recherche"
            "?search_api_fulltext=immobilier&search_mode=all&page=0"
        ),
        page_param="page",
        # On pointe sur la page de listing elle-même, les liens sont déjà des PDFs
        link_selector="div.search-engine-result-row a.btn-download[href]",
        pdf_selector=None,  # lien direct PDF
        base_url_for_join="https://etudes-economiques.credit-agricole.com",
    )
