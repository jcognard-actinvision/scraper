# Stonelake – Scraper & Gmail Fetcher

Ce projet regroupe :
- un **module scraper** pour extraire des contenus web (HTML, PDF, métadonnées),
- un **module gmail_fetcher** pour extraire le contenu et les pièces jointes PDF d’emails d’un label Gmail donné.

L’objectif est de produire des sorties homogènes (JSON + PDF) qui pourront ensuite être exploitées ou adaptées (par exemple pour alimenter Snowflake directement).

---

## Prérequis

- Python 3.11+ recommandé.
- Compte Google avec Gmail activé.
- Accès à la console Google Cloud (création d’identifiants OAuth).

Installation des dépendances :

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

---

## Module scraper

Le module `scraper` permet d’extraire des pages web et des documents (PDF) à partir de différentes sources configurées, puis de produire un JSON et des fichiers locaux (PDF, HTML, etc.).

### Principales fonctionnalités

- Récupération de pages d’insights / articles (ex. Cushman & Wakefield).
- Extraction de métadonnées (titre, date, tags, etc.).
- Téléchargement de pièces jointes PDF.
- Normalisation de la sortie pour qu’elle soit facilement exploitable.

### Configuration (exemple)

Un exemple de fichier de configuration (YAML) typique pourrait ressembler à :

```yaml
sources:
  - name: "cushman_fr_insights"
    base_url: "https://www.cushmanwakefield.com"
    listing_url: "https://www.cushmanwakefield.com/fr-fr/france/insights"
    max_pages: 5
    selectors:
      article_links: "a.cw-card__link"
      title: "h1"
      date: "time"
      tags: ".cw-tags a"
    pdf_patterns:
      - ".pdf"
output_dir: "scraper_output"
```

Les champs exacts dépendent de ton implémentation, mais l’idée est de centraliser :
- les URLs à explorer,
- les sélecteurs CSS ou XPath,
- les patterns de liens pour les PDF,
- les paramètres de pagination.

### Exécution (exemple)

```bash
python -m scraper.run
```

Le module produit un dossier de sortie, par exemple :

```text
scraper_output/
├── documents.json
├── 2026-03-27_rapport_marche_paris.pdf
├── 2026-03-15_etude_esg_immobilier.pdf
└── ...
```

`documents.json` contient la liste des documents extraits avec leurs métadonnées et le nom/chemin des PDF locaux.

---

## Module gmail_fetcher

Le module `gmail_fetcher` extrait le contenu d’emails et les pièces jointes PDF à partir d’un label Gmail configuré.

### Structure

```text
gmail_fetcher/
├── __init__.py
├── config.yaml
├── gmail_client.py
├── fetch_gmail.py
└── list_labels.py
```

### Configuration

Fichier `gmail_fetcher/config.yaml` :

```yaml
user_id: "me"                    # ou l'adresse Gmail complète
label_id: "Label_123456"         # ID interne Gmail du label
output_dir: "gmail_output"       # dossier de sortie
credentials_path: "credentials.json"
token_path: "token.json"
```

- `label_id` : ID du label Gmail à utiliser (voir section “Lister les labels”).
- `output_dir` : le dossier contiendra un JSON consolidé + les PDFs extraits.
- `credentials_path` / `token_path` : chemins des fichiers d’authentification.

---

## Création du client OAuth dans Google Cloud

1. Aller sur [https://console.cloud.google.com](https://console.cloud.google.com).
2. Créer un projet (ou en utiliser un existant).
3. Activer l’API Gmail :
   - Menu “API & Services” → “Bibliothèque”.
   - Chercher “Gmail API” → “Activer”.
4. Configurer l’écran de consentement OAuth :
   - “API & Services” → “Écran de consentement OAuth”.
   - Type d’utilisateur : **Externe** (en général).
   - Remplir les champs obligatoires (nom de l’app, mails, etc.).
   - Ajouter le scope :
     - `https://www.googleapis.com/auth/gmail.readonly`
   - Passer l’app en **“En production”** une fois prête.
5. Créer un ID client OAuth 2.0 :
   - “Identifiants” → “Créer des identifiants” → “ID client OAuth”.
   - Type d’application : **Application de bureau**.
   - Donner un nom, puis créer.
   - Télécharger le fichier JSON et le renommer en `credentials.json` à la racine du projet (ou adapter `credentials_path` dans `config.yaml`).

---

## Authentification Gmail & gestion du token

Lors de la première exécution d’un script `gmail_fetcher` :

- Une fenêtre de navigateur s’ouvre pour autoriser l’application à accéder à Gmail en lecture seule.
- Les informations d’authentification sont stockées dans `token.json` (access_token + refresh_token).

Le code gère automatiquement :
- le rafraîchissement de l’access_token quand il expire,
- la réauthentification (ouverture du navigateur) si le refresh_token lui-même est invalide (révoqué, etc.), puis la réécriture de `token.json`.

---

## Lister les labels Gmail

Pour récupérer l’ID du label à utiliser dans `config.yaml` :

```bash
python -m gmail_fetcher.list_labels
```

Ce script :
- charge `credentials.json` / `token.json`,
- affiche la liste des labels et leurs IDs, par exemple :

```text
INBOX                          INBOX                                             (system)
Label_123456                   Mon label SG                                      (user)
Label_ABCDEF                   Autre label                                       (user)
...
```

Copier l’`id` souhaité (ex. `Label_123456`) dans `gmail_fetcher/config.yaml`.

---

## Extraire les emails et PDF d’un label

Une fois le label configuré :

```bash
python -m gmail_fetcher.fetch_gmail
```

Ce script :

- lit `gmail_fetcher/config.yaml`,
- se connecte à l’API Gmail,
- parcourt tous les emails du label configuré,
- pour chaque email :
  - récupère les headers principaux (subject, date, from),
  - extrait le corps en `text/plain` et `text/html`,
  - télécharge les **pièces jointes PDF** dans `output_dir`,
- génère un fichier `gmail_label_dump.json` dans `output_dir` contenant la liste des messages et les PDFs associés.

Exemple de structure JSON (simplifiée) :

```json
[
  {
    "id": "17c8f4b123456789",
    "subject": "Rapport trimestriel",
    "date": "Wed, 27 Mar 2026 10:15:30 +0100",
    "from": "Banque <contact@banque.fr>",
    "label_id": "Label_123456",
    "body_text": "Contenu texte...",
    "body_html": "<p>Contenu HTML...</p>",
    "pdf_attachments": [
      "17c8f4b123456789_rapport_q1.pdf"
    ]
  }
]
```

---

## Architecture

L’architecture générale repose sur deux modules principaux qui produisent des sorties homogènes (JSON + PDF).

### Vue d’ensemble

- **scraper**
  - Input : configuration des sites à crawler (URL, patterns, règles d’extraction).
  - Process :
    - Télécharge des pages web (HTML).
    - Extrait métadonnées (titre, date, tags, etc.).
    - Détecte et télécharge les fichiers PDF liés.
    - Normalise les résultats dans une structure JSON.
  - Output :
    - Dossier `scraper_output/` (nom indicatif) avec :
      - PDF locaux.
      - Fichier(s) JSON listant les documents et leurs attributs.

- **gmail_fetcher**
  - Input : configuration du label Gmail et des chemins (`config.yaml`).
  - Process :
    - Connexion à l’API Gmail via OAuth2 (`credentials.json` + `token.json`).
    - Liste des messages d’un label Gmail donné.
    - Extraction du corps (texte/HTML).
    - Téléchargement des pièces jointes PDF.
    - Normalisation des résultats dans une structure JSON cohérente avec le scraper.
  - Output :
    - Dossier `gmail_output/` avec :
      - PDFs issus des emails.
      - `gmail_label_dump.json` listant les messages et les pièces jointes.

### Schéma textuel des flux

```text
            +------------------+
            |  Config fichiers |
            | (YAML / JSON)    |
            +---------+--------+
                      |
          +-----------+-----------+
          |                       |
   +------+-----+           +-----+--------+
   |  scraper   |           | gmail_fetcher|
   +------+-----+           +------+-------+
          |                         |
   HTML / PDF web             Emails + PDF
          |                         |
   +------+-----+           +------+-------+
   | JSON sortie|           | JSON sortie  |
   | (web docs) |           | (emails)     |
   +------------+           +--------------+
```

### Points clé de conception

- **Séparation des responsabilités** :
  - `scraper` ne gère que les sources web.
  - `gmail_fetcher` ne gère que Gmail et l’authentification OAuth2.
- **Configuration explicite** :
  - Chaque module a ses propres fichiers de configuration, indépendants.
  - `gmail_fetcher` repose sur `config.yaml` pour `label_id`, chemins d’output et de credentials.
- **Sorties homogènes** :
  - Les deux modules produisent :
    - des fichiers JSON décrivant les documents,
    - des PDF stockés localement avec des chemins/références dans le JSON.

---

## Lancer l’environnement de développement

Rappel rapide :

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Puis, au choix :

```bash
# Scraper web
python -m scraper.run

# Lister les labels Gmail
python -m gmail_fetcher.list_labels

# Extraire les emails + PDF d'un label
python -m gmail_fetcher.fetch_gmail
```