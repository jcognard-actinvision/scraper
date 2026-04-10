# Stonelake – Scraper & Gmail Fetcher

Ce projet regroupe :

- un **module `scraper`** pour extraire des contenus web (HTML, PDF, métadonnées) depuis différentes sources,
- un **module `gmail_fetcher`** pour extraire le contenu et les pièces jointes PDF d’emails d’un label Gmail donné,
- une **couche de stockage** factorisée (`common_storage`) permettant d’enregistrer les documents soit en local, soit dans Snowflake,
- une **couche HTTP `FastAPI`** permettant d’exposer des endpoints de lancement pour Docker, Cloud Run et Cloud Scheduler.

L’objectif est de produire des sorties homogènes et de permettre une exécution soit en ligne de commande, soit via des appels HTTP authentifiés dans Google Cloud.

---

## Arborescence du projet

```text
.
├── app.py                    # Entrypoint HTTP FastAPI pour Cloud Run / local
├── common_runtime/           # Paramétrage générique (Settings, env, etc.)
├── common_storage/           # Abstractions de stockage (local, Snowflake, modèles)
├── gmail_fetcher/            # Extraction d’emails et pièces jointes Gmail
├── gmail_tokens/             # Credentials / tokens OAuth Gmail (local)
├── keys/                     # Clé privée Snowflake (local)
├── output/                   # Sorties locales des scrapers (mode Python direct)
├── output_docker/            # Sorties quand le projet tourne en conteneur
├── scraper/                  # Moteur de scraping web (sites, core, adapters)
├── .env.example              # Exemple de configuration par variables d’environnement
├── Dockerfile                # Image Docker de l’application
├── README.md
└── requirements.txt
```

---

## Architecture d’exécution

Le projet peut maintenant être utilisé selon deux modes :

- **mode CLI** : pratique en développement local, via `python -m scraper.run` ou `python -m gmail_fetcher.fetch_gmail`,
- **mode HTTP** : recommandé pour Docker, Cloud Run et Cloud Scheduler, via des endpoints FastAPI appelés en `POST`.

### Endpoints exposés

L’application HTTP expose les endpoints suivants :

- `GET /health` : vérification rapide de disponibilité du service ; utile pour les probes et tests simples.
- `GET /sites` : retourne la liste des scrapers disponibles.
- `POST /run/scrapers` : lance un ou plusieurs scrapers web.
- `POST /run/gmail` : lance le fetch Gmail.
- `POST /run/all` : lance le scraper web puis le fetch Gmail.

Cette approche est adaptée à Cloud Run, qui attend un service HTTP écoutant sur `0.0.0.0:$PORT` dans le conteneur.

---

## Prérequis

- Python **3.11+** recommandé.
- Compte Google avec Gmail activé.
- Accès à la console Google Cloud pour créer des identifiants OAuth Gmail.
- (Optionnel) Un compte Snowflake si on active le backend Snowflake.

Installation des dépendances en local :

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

---

## Configuration par variables d’environnement

La configuration est centralisée via des variables d’environnement lues dans `common_runtime.settings`, `common_storage`, `scraper` et `gmail_fetcher`.

Un fichier `.env.example` est fourni comme modèle.

### Exemple `.env`

```env
# --- Mode d'exécution ---
APP_TARGET=scraper

# --- Backend de stockage ---
STORAGE_BACKEND=local
OUTPUT_DIR=output

# --- Gmail fetcher ---
GMAIL_USER_ID=me
GMAIL_LABEL_ID=Label_123456
GMAIL_CREDENTIALS_PATH=gmail_tokens/credentials.json
GMAIL_TOKEN_PATH=gmail_tokens/token.json
GMAIL_OUTPUT_DIR=gmail_output

# --- Snowflake ---
SNOWFLAKE_ACCOUNT=xxxxxx.eu-central-1
SNOWFLAKE_USER=STONELAKE_SVC
SNOWFLAKE_ROLE=STONELAKE_ROLE
SNOWFLAKE_WAREHOUSE=STONELAKE_WH
SNOWFLAKE_DATABASE=STONELAKE_DB
SNOWFLAKE_SCHEMA=RAW
SNOWFLAKE_PRIVATE_KEY_PATH=keys/rsa_key.p8
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=*****

SNOWFLAKE_STAGE_ROOT=@SCRAPER_STAGE
SCRAPED_DOCUMENTS_TABLE=SCRAPED_DOCUMENTS
SCRAPER_RUNS_TABLE=SCRAPER_RUNS
SCRAPER_ERRORS_TABLE=SCRAPER_ERRORS

# --- SMTP notifications (optionnel) ---
SMTP_ENABLED=false
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_FROM=
SMTP_TO=
SMTP_SUBJECT_PREFIX=[Stonelake]
```

En local, Docker et Cloud Run, la même logique s’applique : la configuration est injectée via l’environnement, sans dépendre d’un fichier de configuration spécifique au runtime.

---

## Module `scraper`

Le module `scraper` permet d’extraire des pages web et des documents (PDF) à partir de différentes sources configurées, puis de produire des documents normalisés exploitables en stockage local ou Snowflake.

### Principales fonctionnalités

- Récupération de pages d’insights / articles.
- Extraction de métadonnées.
- Détection et téléchargement des pièces jointes PDF.
- Normalisation de la sortie.
- Gestion d’un mode incrémental basé sur l’existence des documents déjà stockés.

### Sites pris en charge

Les implémentations spécifiques se trouvent dans `scraper/sites/` :

```text
scraper/sites/
├── aspim.py
├── banque_france.py
├── bnp_paribas.py
├── bnppre_market_france.py
├── catella.py
├── credit_agricole_immobilier.py
├── cushman_wakefield.py
├── fbf.py
├── groupe_bpce.py
├── knight_frank.py
├── labanquepostale.py
├── leaseo.py
├── notaires_fr_tendances.py
├── notaires_grand_paris.py
├── observatoire_credit_logement.py
├── savills.py
├── societe_generale.py
└── wargny_katz.py
```

### Exécution en local (CLI)

```bash
# Exécuter tous les scrapers configurés
python -m scraper.run

# Exécuter un site précis
python -m scraper.run --site aspim

# Plusieurs sites
python -m scraper.run --site aspim --site fbf

# Limiter la pagination
python -m scraper.run --site aspim --max-pages 1

# Lister les sites disponibles
python -m scraper.run --list-sites
```

### Exécution via HTTP

L’endpoint `POST /run/scrapers` supporte l’équivalent des arguments CLI via query parameters FastAPI.

Exemples :

```http
POST /run/scrapers
```

```http
POST /run/scrapers?site=aspim
```

```http
POST /run/scrapers?site=aspim&site=fbf&max_pages=1
```

```http
POST /run/scrapers?list_sites=true
```

Paramètres supportés :

- `site` : paramètre répétable, équivalent à `--site`,
- `max_pages` : entier optionnel, équivalent à `--max-pages`,
- `output_dir` : chaîne optionnelle, équivalent à `--output-dir`,
- `list_sites` : booléen optionnel, équivalent à `--list-sites`.

La réponse retourne un JSON contenant un statut global et un détail par scraper exécuté.

---

## Module `gmail_fetcher`

Le module `gmail_fetcher` extrait le contenu d’emails et les pièces jointes PDF à partir d’un label Gmail configuré.

### Structure

```text
gmail_fetcher/
├── __init__.py
├── fetch_gmail.py        # Extraction des emails + pièces jointes
├── gmail_client.py       # Client Gmail + auth
├── init_gmail_token.py   # Initialisation / reset du token
└── list_labels.py        # Listing des labels Gmail
```

### Configuration

Le module `gmail_fetcher` lit sa configuration via les variables d’environnement :

```env
GMAIL_USER_ID=me
GMAIL_LABEL_ID=Label_123456
GMAIL_CREDENTIALS_PATH=gmail_tokens/credentials.json
GMAIL_TOKEN_PATH=gmail_tokens/token.json
GMAIL_OUTPUT_DIR=gmail_output
```

- `GMAIL_CREDENTIALS_PATH` : chemin vers le client OAuth Gmail.
- `GMAIL_TOKEN_PATH` : chemin vers le token utilisateur généré après authentification.
- `GMAIL_OUTPUT_DIR` : dossier de sortie local si `LocalStorage` est utilisé.

### Exécution CLI

```bash
python -m gmail_fetcher.fetch_gmail
```

### Exécution HTTP

```http
POST /run/gmail
```

Le endpoint lance le fetch Gmail et retourne un JSON de synthèse, par exemple :

```json
{
  "status": "ok",
  "result": {
    "processed": 12,
    "inserted": 5,
    "skipped": 7,
    "errors": 0
  }
}
```

---

## Création du client OAuth Gmail

1. Aller sur <https://console.cloud.google.com>.
2. Créer un projet ou utiliser un projet existant.
3. Activer l’API Gmail.
4. Configurer l’écran de consentement OAuth.
5. Créer un ID client OAuth 2.0 de type **Application de bureau**.
6. Télécharger le JSON et le placer sous `gmail_tokens/credentials.json`.

Le scope minimum recommandé est :

- `https://www.googleapis.com/auth/gmail.readonly`

---

## Authentification et gestion du token Gmail

Lors de la première exécution d’un script `gmail_fetcher` en local :

- une fenêtre de navigateur s’ouvre pour autoriser l’application,
- les informations d’authentification sont stockées dans `gmail_tokens/token.json`.

Le code gère ensuite automatiquement :

- le rafraîchissement de l’`access_token`,
- la réauthentification si le `refresh_token` est révoqué ou invalide.

Pour réinitialiser le token, supprimer `token.json` puis relancer la procédure locale.

> En environnement Cloud Run, le token et les credentials sont généralement injectés via Secret Manager et montés comme fichiers dans le conteneur, plutôt que stockés localement.

---

## Lister les labels Gmail

```bash
python -m gmail_fetcher.list_labels
```

Ce script affiche la liste des labels disponibles afin de renseigner `GMAIL_LABEL_ID`.

---

## Stockage : local vs Snowflake

La couche `common_storage` permet de changer de backend sans modifier les modules métier :

- `LocalStorage` : écrit les fichiers et JSON sur disque.
- `SnowflakeStorage` : insère les documents dans Snowflake avec contenu, texte et métadonnées.

Le backend est choisi via `STORAGE_BACKEND` :

```env
STORAGE_BACKEND=local
# ou
STORAGE_BACKEND=snowflake
```

La configuration Snowflake repose sur les variables `SNOWFLAKE_*`.

---

## Notifications d’erreur par email (SMTP)

Le projet peut envoyer des notifications email lorsqu’une erreur est journalisée, à condition qu’une configuration SMTP valide soit définie dans les variables d’environnement.

Cette fonctionnalité est optionnelle :

- si `SMTP_ENABLED=false`, aucun email n’est envoyé ;
- si les paramètres SMTP requis sont absents, le projet continue de fonctionner ;
- si l’envoi SMTP échoue, cela ne doit pas interrompre le traitement principal.

### Variables SMTP

| Variable | Description |
|----------|-------------|
| `SMTP_ENABLED` | Active ou désactive les notifications email. |
| `SMTP_HOST` | Hôte du serveur SMTP. |
| `SMTP_PORT` | Port SMTP, par exemple `587` ou `465`. |
| `SMTP_USERNAME` | Nom d’utilisateur SMTP. |
| `SMTP_PASSWORD` | Mot de passe SMTP. |
| `SMTP_USE_TLS` | Active STARTTLS. |
| `SMTP_USE_SSL` | Utilise SMTP SSL direct. |
| `SMTP_FROM` | Adresse expéditrice. |
| `SMTP_TO` | Liste des destinataires séparés par des virgules. |
| `SMTP_SUBJECT_PREFIX` | Préfixe de l’objet des emails d’alerte. |

### Bonnes pratiques

- Utiliser soit `SMTP_USE_TLS=true`, soit `SMTP_USE_SSL=true`, mais pas les deux.
- Ne jamais committer `SMTP_PASSWORD`.
- En environnement cloud, injecter les secrets SMTP via Secret Manager.
- Vérifier que l’adresse `SMTP_FROM` est autorisée par le serveur SMTP.

---

## Utilisation locale en mode HTTP

Une fois `app.py` ajouté, tu peux démarrer le service localement avec Uvicorn :

```bash
uvicorn app:app --host 0.0.0.0 --port 8080
```

Puis tester :

```bash
curl http://localhost:8080/health
curl http://localhost:8080/sites
curl -X POST "http://localhost:8080/run/scrapers?site=aspim&max_pages=1"
curl -X POST "http://localhost:8080/run/gmail"
curl -X POST "http://localhost:8080/run/all?site=aspim&max_pages=1"
```

Sous Windows PowerShell :

```powershell
Invoke-RestMethod http://localhost:8080/health
Invoke-RestMethod http://localhost:8080/sites
Invoke-RestMethod -Method Post "http://localhost:8080/run/scrapers?site=aspim&max_pages=1"
Invoke-RestMethod -Method Post "http://localhost:8080/run/gmail"
Invoke-RestMethod -Method Post "http://localhost:8080/run/all?site=aspim&max_pages=1"
```

---

## Utilisation avec Docker

Le conteneur exécute maintenant l’application HTTP FastAPI au lieu de lancer directement un module Python ponctuel. Cette approche est adaptée à Cloud Run, qui attend un service HTTP écoutant sur le port fourni par la variable `PORT`.

### Construction de l’image

```bash
docker build -t stonelake-scraper:local .
```

### Lancer le service HTTP localement

Linux / macOS :

```bash
docker run --rm -it \
  --env-file .env \
  -p 8080:8080 \
  -v "$(pwd)/gmail_tokens:/app/gmail_tokens" \
  -v "$(pwd)/keys:/app/keys" \
  -v "$(pwd)/output_docker:/app/output_docker" \
  stonelake-scraper:local
```

Windows PowerShell :

```powershell
docker run --rm -it `
  --env-file .env `
  -p 8080:8080 `
  -v "$PWD/gmail_tokens:/app/gmail_tokens" `
  -v "$PWD/keys:/app/keys" `
  -v "$PWD/output_docker:/app/output_docker" `
  stonelake-scraper:local
```

Ensuite, appelle les endpoints HTTP depuis ta machine hôte.

### Dockerfile attendu

Le `Dockerfile` doit lancer Uvicorn, par exemple :

```dockerfile
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

Cloud Run fournit `PORT` automatiquement, et en local la valeur par défaut `8080` permet de tester le service facilement.

---

## Déploiement Cloud Run

L’application est conçue pour être déployée sur Cloud Run derrière un service HTTP authentifié.

Principes recommandés :

- service non public avec `--no-allow-unauthenticated`,
- secrets injectés depuis Secret Manager,
- compte de service dédié pour le runtime,
- appels planifiés via Cloud Scheduler en OIDC.

Exemple d’endpoints ciblables par Scheduler :

- `POST /run/gmail`
- `POST /run/scrapers?site=aspim&max_pages=1`
- `POST /run/all`

---

## Lancer rapidement l’environnement de développement

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Puis, au choix :

### Mode CLI

```bash
python -m scraper.run --site aspim --max-pages 1
python -m gmail_fetcher.list_labels
python -m gmail_fetcher.fetch_gmail
```

### Mode HTTP

```bash
uvicorn app:app --host 0.0.0.0 --port 8080
```

Puis :

```bash
curl http://localhost:8080/health
curl -X POST "http://localhost:8080/run/scrapers?site=aspim&max_pages=1"
curl -X POST "http://localhost:8080/run/gmail"
```

---

## Notes de conception

- Le mode CLI reste utile pour le développement et le debug local.
- Le mode HTTP est la cible privilégiée pour Docker, Cloud Run et Cloud Scheduler.
- Les fonctions métier doivent rester appelables depuis Python sans dépendre directement d’`argparse`, afin d’être réutilisées à la fois par la CLI et par FastAPI.
- Pour Cloud Run, il est recommandé de conserver `concurrency=1` si l’on veut éviter des exécutions concurrentes sur les mêmes sources batch.