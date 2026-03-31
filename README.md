# Scraper d’études économiques (PDF & HTML)

Ce projet permet de scraper automatiquement plusieurs sites d’institutions financières (banques centrales, observatoires, banques de détail, etc.) afin de récupérer :

- les pages d’articles (HTML),
- les liens vers les documents PDF associés,
- éventuellement le texte extrait des PDF.

L’objectif est de construire un pipeline homogène pour collecter et traiter des publications économiques (études, notes de conjoncture, observatoires, etc.).

## Fonctionnalités principales

- Gestion centralisée des requêtes HTTP (session, headers, timeouts).
- Abstraction commune pour chaque site (`SiteScraper`).
- Gestion de la pagination (querystring `page`, patterns spécifiques par site).
- Extraction des articles à partir des pages de listing.
- Récupération des liens PDF spécifiques à chaque site.
- Extraction du texte des PDF pour certains sites.
- Paramétrage du nombre maximum de pages à parcourir par site.

## Structure du projet

```text
scraper/
├── .gitignore
├── list_gmail_label.py          # Script annexe pour Gmail (optionnel)
└── scraper/
    ├── __init__.py
    ├── run.py                   # Point d’entrée principal (CLI / script)
    ├── core/
    │   ├── __init__.py
    │   ├── base_site.py         # Classe abstraite commune SiteScraper
    │   ├── http.py              # Session HTTP partagée (User-Agent, retries, etc.)
    │   ├── models.py            # Modèle Resource, ResourceType, etc.
    │   ├── parsers.py           # Fonctions d’extraction de texte (HTML, PDF)
    │   └── predicates.py        # Fonctions utilitaires (filtres / conditions)
    └── sites/
        ├── __init__.py
        ├── banque_france.py
        ├── credit_agricole_immobilier.py
        ├── fbf.py
        ├── labanquepostale.py
        ├── observatoire_credit_logement.py
        └── societe_generale.py  # Exemple de nouveau site
```

### Modèle `Resource`

Le type central est `Resource` (dans `core/models.py`), qui représente une pièce de contenu à récupérer :

- `url` : URL de la ressource (HTML ou PDF).
- `type` : `ResourceType.HTML` ou `ResourceType.PDF`.
- `title` : titre de l’article ou du document.
- `raw_content` : contenu binaire (HTML ou PDF).
- `text` : texte brut associé (HTML ou PDF) quand il est extrait.
- `meta` : dictionnaire avec informations supplémentaires (URL de listing, `pdf_url`, `html_text`, `pdf_text`, erreurs, etc.).

## Installation

### Prérequis

- Python 3.11+ (recommandé).
- Un environnement virtuel Python (venv / conda) est conseillé.

### Étapes

```bash
git clone https://github.com/jcognard-actinvision/scraper.git
cd scraper

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt  # si un fichier existe
# ou bien installer manuellement:
pip install requests beautifulsoup4 pdfminer.six rich  # à adapter
```

> Remarque : il est recommandé de lister toutes les dépendances dans `requirements.txt`.

## Utilisation

### Lancement simple depuis `run.py`

Le fichier `scraper/run.py` regroupe la logique permettant de choisir un site et d’exécuter le scraping. Un schéma classique ressemble à :

```python
from scraper.sites.banque_france import BanqueFranceScraper
from scraper.sites.credit_agricole_immobilier import CreditAgricoleImmobilierScraper
from scraper.sites.fbf import FBFScraper
from scraper.sites.labanquepostale import LaBanquePostaleScraper
from scraper.sites.observatoire_credit_logement import ObservatoireCreditLogementScraper
from scraper.sites.societe_generale import SocieteGeneraleScraper

SITES = {
    "banque_france": BanqueFranceScraper,
    "ca_immobilier": CreditAgricoleImmobilierScraper,
    "fbf": FBFScraper,
    "labanquepostale": LaBanquePostaleScraper,
    "observatoire_credit_logement": ObservatoireCreditLogementScraper,
    "societe_generale": SocieteGeneraleScraper,
}
```

Un pattern d’exécution typique :

```bash
python -m scraper.run banque_france --max-pages 3
```

ou, si `run.py` est scriptable directement :

```bash
python scraper/run.py banque_france --max-pages 3
```

Selon ta mise en place actuelle, les options peuvent varier (nom du site, nombre de pages, output JSON/CSV, etc.).

### Exemple d’usage programmatique

```python
from scraper.sites.banque_france import BanqueFranceScraper

scraper = BanqueFranceScraper()
scraper.set_max_pages(2)  # optionnel
resources = scraper.run()

for res in resources:
    print(res.type, res.title, res.meta.get("pdf_url"))
```

## Détail par site

### Banque de France

- Listing : `https://www.banque-france.fr/fr/publications-et-statistiques/publications?page=N`
- Pagination via querystring `page`.
- Sélection des cartes via `div.col.d-flex a.card[href]`.
- Pour chaque article HTML :
  - Titre depuis `<h1>` (fallback dans la carte si besoin).
  - Texte principal depuis `<main>` (ou `body`).
  - Lien PDF via  
    `div.paragraph--type--espaces2-telecharger-document a.card-download[href]`.
  - `pdf_url` et `html_text` stockés dans `resource.meta`.

### Crédit Agricole Immobilier

- Listing :  
  `https://etudes-economiques.credit-agricole.com/fr/recherche?search_api_fulltext=immobilier&search_mode=all&page=N`
- Paramètres fixes : `search_api_fulltext=immobilier`, `search_mode=all`, plus `page`.
- Les pages de listing retournent directement des liens PDF via  
  `div.search-engine-result-row a.btn-download[href]`.
- `Resource` créées en type `PDF`, avec `pdf_url` renseigné.

### FBF (Fédération Bancaire Française)

- Listings : plusieurs URLs (chiffres clés, emploi, etc.) définies dans `LISTING_URLS`.
- Extraction des articles via `div.category__content article a.card__link`.
- Pagination supplémentaire via un endpoint AJAX (`/fr/ajax-post/filtered-posts-page`) alimenté par le formulaire `#category-posts-filter`.
- Sur chaque article HTML :
  - `html_text` extrait depuis `<main>` / `<article>`.
  - Lien PDF (href se terminant par `.pdf`).
  - PDF téléchargé, texte extrait via `extract_pdf_text`.
  - `resource.text` contient le texte PDF si disponible, sinon le texte HTML.

### La Banque Postale

- Plusieurs URLs de base dans `LISTING_URLS` du type `.../rebond.p-1.html`.
- Pagination via un pattern `*.p-<page>.html`.
- Extraction des articles via `div.o-newslist__push a.u-link[href]`.
- Sur chaque article HTML :
  - Titre depuis `<h1>`.
  - Texte principal depuis `<main>` / `body`.
  - Lien PDF via `div.m-cta--download a.m-cta[href]`.

### Observatoire Crédit Logement

- Listing unique : `/historique`.
- Ciblage de la section « Analyses du marché immobilier mensuelles ».
- Parcours des titres `h3` situés dans cette section, avec un lien « En savoir plus ».
- Sur chaque article HTML :
  - Titre depuis `<h1>` / `<h2>`.
  - Texte principal depuis `div#page-publications`, `<main>` ou `body`.
  - Lien PDF dans `div.box-download a[href$=".pdf"]`.
  - PDF récupéré, texte stocké dans `resource.meta["pdf_text"]` et `resource.text`.

### Société Générale (Études économiques)

- Listing :  
  `https://www.societegenerale.com/fr/etudes-economiques?type=153&lock_type=yes&page=N`
- Paramètres fixes : `type=153`, `lock_type=yes`, plus `page`.
- Articles du listing sélectionnés via `ul.newsroom-list a.actu-thumb[href]`.
- Sur chaque article HTML :
  - Titre depuis `<h1>`.
  - Texte principal depuis `<main>` / `body`.
  - Lien PDF via  
    `div.bloc-element-de-contexte a.custom-download-link[href]`.

## Base commune : `SiteScraper`

Toutes les classes de site héritent de `SiteScraper` (`core/base_site.py`), qui fournit :

- Un constructeur qui crée une session HTTP partagée.
- Trois méthodes abstraites à implémenter :

  ```python
  def iter_listing_urls(self) -> Iterable[str]: ...
  def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]: ...
  def extract_content(self, resource: Resource) -> Resource: ...
  ```

- Des helpers génériques pour factoriser le code :

  - `set_max_pages(max_pages: int | None)` : limite le nombre de pages de listing.
  - `safe_get(url, retries=2, delay=1.5)` : GET avec retries.
  - `with_page_query(url, page, extra_params=None)` : gestion propre de `?page=N` + autres paramètres.
  - `iter_paginated_listing_urls(base_url, extract_resources_fn, first_page=0)` : boucle générique de pagination jusqu’à épuisement des résultats.

- Une méthode `run()` qui orchestre le pipeline par défaut :

  1. Itère sur `iter_listing_urls()` pour récupérer toutes les pages de listing.
  2. Appelle `extract_resources_from_listing()` sur chaque page.
  3. Télécharge et enrichit chaque `Resource` via `extract_content()`.

## Ajouter un nouveau site

Pour ajouter un nouveau site :

1. Créer `scraper/sites/mon_site.py`.
2. Définir une classe `MonSiteScraper(SiteScraper)` avec :

   - `base_url` et éventuellement `listing_base_url`.
   - `iter_listing_urls()` :
     - soit via `iter_paginated_listing_urls(...)` si la pagination est de type `?page=N`,
     - soit via une simple boucle sur une liste d’URLs.
   - `extract_resources_from_listing(html, url)` pour transformer une page de listing en liste de `Resource`.
   - `extract_content(resource)` pour télécharger la ressource et remplir `raw_content`, `text`, `meta`.

3. Enregistrer la classe dans `scraper/run.py`.
4. Tester avec `set_max_pages(1)` avant de lancer sur tout l’historique.

## Logs et debug

Chaque scraper utilise un logger (`logging.getLogger("scraper.<site>")`) avec des messages comme :

- nombre de ressources trouvées sur une page de listing ;
- URL de PDF trouvés / non trouvés ;
- erreurs de récupération ou de parsing.

Configure le niveau de logs dans `run.py` pour faciliter le debug.

## Script Gmail (optionnel)

`list_gmail_label.py` fournit un script séparé pour interagir avec l’API Gmail (par exemple lister des messages d’un label donné). Il n’est pas directement intégré au pipeline de scraping mais peut servir à croiser des informations ou à archiver des mails liés aux études.

## Limitations et TODO

- Extraction du texte PDF seulement pour certains sites (FBF, Observatoire, …).
- Pas encore d’export standardisé (JSON/CSV) des ressources.
- Pas de persistance centralisée (base de données) ni de dédoublonnage.
