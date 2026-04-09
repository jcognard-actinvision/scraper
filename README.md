# Stonelake – Scraper & Gmail Fetcher

Ce projet regroupe :

- un **module `scraper`** pour extraire des contenus web (HTML, PDF, métadonnées) depuis différentes sources,
- un **module `gmail_fetcher`** pour extraire le contenu et les pièces jointes PDF d’emails d’un label Gmail donné,
- une **couche de stockage** factorisée (`common_storage`) permettant d’enregistrer les documents soit en local, soit dans Snowflake.

L’objectif est de produire des sorties homogènes (JSON + PDF) qui pourront ensuite être exploitées ou adaptées (par exemple pour alimenter Snowflake directement).

---

## Arborescence du projet

```text
.
├── common_runtime/           # Paramétrage générique (Settings, env, etc.)
├── common_storage/           # Abstractions de stockage (local, Snowflake, modèles)
├── docker/                   # Entrypoint Docker (module docker.entrypoint)
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

## Prérequis

- Python **3.11+** recommandé.
- Compte Google avec Gmail activé.
- Accès à la console Google Cloud pour créer des identifiants OAuth Gmail.
- (Optionnel) Un compte Snowflake si on active le backend Snowflake.

Installation des dépendances en local :

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

La configuration est centralisée via des variables d’environnement lues dans `common_runtime.settings`, `common_storage` et `gmail_fetcher`.  
Un fichier `.env.example` est fourni comme modèle.

### Exemple `.env`

```env
# --- Backend de stockage ---
# "local" (par défaut) ou "snowflake"
STORAGE_BACKEND=local

# Répertoire de sortie (local)
OUTPUT_DIR=output

# --- Gmail fetcher ---
GMAIL_USER_ID=me
GMAIL_LABEL_ID=Label_123456
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
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

Le module `scraper` permet d’extraire des pages web et des documents (PDF) à partir de différentes sources configurées, puis de produire un JSON et des fichiers locaux (PDF, HTML, etc.).

### Principales fonctionnalités

- Récupération de pages d’insights / articles (ex. Cushman & Wakefield, banques, notaires, etc.).
- Extraction de métadonnées (titre, date, tags, etc.).
- Détection et téléchargement des pièces jointes PDF.
- Normalisation de la sortie pour qu’elle soit facilement exploitable (fichiers + JSON).

### Sites pris en charge (exemples)

Les implémentations spécifiques se trouvent dans `scraper/sites/` :

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

Chaque module de site s’appuie sur les abstractions de `scraper.core` (`base_site`, `http`, `parsers`, `content_strategies`, etc.).

### Exécution en local

```bash
# Exécuter tous les scrapers configurés
python -m scraper.run

# Exemple : n’exécuter qu’un site avec une pagination limitée
python -m scraper.run --site aspim --max-pages 1
```

La sortie par défaut (en mode stockage local) se fait dans un dossier `output/` ou `output_docker/` avec :

- les pages HTML et/ou PDF téléchargées,
- un ou plusieurs fichiers JSON résumant les documents et leurs métadonnées.

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

Le module `gmail_fetcher` lit sa configuration **via les variables d’environnement**, par exemple :

```env
GMAIL_USER_ID=me
GMAIL_LABEL_ID=Label_123456
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
GMAIL_OUTPUT_DIR=gmail_output
```

- `GMAIL_CREDENTIALS_PATH` : chemin vers le client OAuth Gmail (`credentials.json`).
- `GMAIL_TOKEN_PATH` : chemin vers le token utilisateur (`token.json`), généré après la première authentification.
- `GMAIL_OUTPUT_DIR` : dossier de sortie pour `gmail_label_dump.json` et les PDF.

---

## Création du client OAuth Gmail

1. Aller sur <https://console.cloud.google.com>.
2. Créer un projet (ou en utiliser un existant).
3. Activer l’API Gmail :
   - Menu “API & Services” → “Bibliothèque”.
   - Chercher **“Gmail API”** → “Activer”.
4. Configurer l’écran de consentement OAuth :
   - “API & Services” → “Écran de consentement OAuth”.
   - Type d’utilisateur : **Externe** en général.
   - Remplir les champs obligatoires (nom de l’app, e‑mail, etc.).
   - Scope minimum recommandé :
     - `https://www.googleapis.com/auth/gmail.readonly`
   - Passer l’app en **“En production”** une fois prête.
5. Créer un ID client OAuth 2.0 :
   - “Identifiants” → “Créer des identifiants” → “ID client OAuth”.
   - Type d’application : **Application de bureau**.
   - Télécharger le JSON et le placer sous `gmail_tokens/credentials.json` (ou adapter `GMAIL_CREDENTIALS_PATH`).

---

## Authentification & gestion du token Gmail

Lors de la première exécution d’un script `gmail_fetcher` :

- une fenêtre de navigateur s’ouvre pour autoriser l’application à accéder à Gmail en lecture seule,
- les informations d’authentification sont stockées dans `gmail_tokens/token.json` (access_token + refresh_token).

Le code gère automatiquement :

- le rafraîchissement de l’`access_token` à l’expiration,
- la réauthentification si le `refresh_token` est révoqué ou invalide.

Pour réinitialiser proprement le token, il suffit de supprimer `token.json` et de relancer le script (une nouvelle fenêtre d’auth s’ouvrira).

---

## Lister les labels Gmail

```bash
python -m gmail_fetcher.list_labels
```

Ce script affiche la liste des labels disponibles :

```text
INBOX                          INBOX                                             (system)
Label_123456                   Mon label SG                                      (user)
Label_ABCDEF                   Autre label                                       (user)
...
```

Recopier ensuite l’ID souhaité dans la variable `GMAIL_LABEL_ID` du fichier `.env`.

---

## Extraire les emails et PDF d’un label

```bash
python -m gmail_fetcher.fetch_gmail
```

Le script :

- lit la configuration via les variables d’environnement,
- se connecte à l’API Gmail,
- parcourt les emails du label,
- extrait headers (subject, date, from), corps text + HTML,
- télécharge les pièces jointes PDF,
- écrit un `gmail_label_dump.json` dans `GMAIL_OUTPUT_DIR` plus les PDF.

Exemple de JSON (simplifié) :

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

Les documents PDF sont en parallèle stockés en tant que `StoredDocument` via `common_storage` (local ou Snowflake selon la configuration).

---

## Stockage : local vs Snowflake

La couche `common_storage` permet de changer de backend sans modifier les modules de scraping / Gmail :

- `LocalStorage` : écrit les fichiers et JSON sur disque (`output/`, `output_docker/`, etc.).
- `SnowflakeStorage` : insère les documents dans une table Snowflake (ex. `SCRAPED_DOCUMENTS`) en stockant :
  - le contenu binaire (PDF),
  - le texte extrait,
  - les métadonnées dans une colonne semi-structurée (type `VARIANT`).

Le backend est choisi via `STORAGE_BACKEND` :

```env
STORAGE_BACKEND=local       # pour tests/dev
# ou
STORAGE_BACKEND=snowflake   # en production
```

La configuration Snowflake (compte, user, rôle, warehouse, DB, schéma, clé privée) est portée par les variables `SNOWFLAKE_*` (voir plus haut).

---

## Notifications d’erreur par email (SMTP)

Le projet peut envoyer des notifications email lorsqu’une erreur est journalisée via `log_error`, à condition qu’une configuration SMTP valide soit définie dans les variables d’environnement.

Cette fonctionnalité est **optionnelle** :
- si `SMTP_ENABLED=false`, aucun email n’est envoyé ;
- si les paramètres SMTP requis sont absents, le projet continue de fonctionner sans notification ;
- si l’envoi SMTP échoue, cela ne doit pas interrompre le traitement principal.

### Variables SMTP

| Variable | Description |
|----------|-------------|
| `SMTP_ENABLED` | Active ou désactive les notifications email (`true` / `false`). |
| `SMTP_HOST` | Hôte du serveur SMTP. |
| `SMTP_PORT` | Port SMTP, par exemple `587` pour STARTTLS ou `465` pour SSL implicite. |
| `SMTP_USERNAME` | Nom d’utilisateur SMTP, si requis par le fournisseur. |
| `SMTP_PASSWORD` | Mot de passe SMTP, si requis. |
| `SMTP_USE_TLS` | Active `STARTTLS` après connexion SMTP. Généralement utilisé avec le port `587`. |
| `SMTP_USE_SSL` | Utilise `SMTP_SSL` dès l’ouverture de la connexion. Généralement utilisé avec le port `465`. |
| `SMTP_FROM` | Adresse email expéditrice. |
| `SMTP_TO` | Liste des destinataires séparés par des virgules. |
| `SMTP_SUBJECT_PREFIX` | Préfixe ajouté à l’objet des emails d’alerte. |

### Exemple Office 365

```env
SMTP_ENABLED=true
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=alertes@mondomaine.fr
SMTP_PASSWORD=**
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_FROM=alertes@mondomaine.fr
SMTP_TO=jerome@mondomaine.fr,ops@mondomaine.fr
SMTP_SUBJECT_PREFIX=[Stonelake PROD]
```

### Exemple SMTP SSL direct

```env
SMTP_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USERNAME=alertes@example.com
SMTP_PASSWORD=**
SMTP_USE_TLS=false
SMTP_USE_SSL=true
SMTP_FROM=alertes@example.com
SMTP_TO=ops@example.com
SMTP_SUBJECT_PREFIX=[Stonelake]
```

### Bonnes pratiques

- Utiliser **soit** `SMTP_USE_TLS=true`, **soit** `SMTP_USE_SSL=true`, mais pas les deux en même temps.
- Ne jamais committer `SMTP_PASSWORD` dans le dépôt.
- En environnement conteneurisé ou cloud, injecter `SMTP_PASSWORD` via un secret ou une variable sécurisée.
- Vérifier que l’adresse `SMTP_FROM` est autorisée par le serveur SMTP utilisé.

---

## Utilisation avec Docker

Un `Dockerfile` est fourni pour exécuter le projet dans un conteneur.  
L’image embarque le code et les dépendances, puis exécute par défaut `python -m docker.entrypoint`, mais on peut surcharger la commande au runtime.

### Construction de l’image

Depuis la racine du projet :

```bash
docker build -t stonelake-scraper:local .
```

### Principe d’exécution

Les commandes `docker run` ci-dessous :

- chargent la configuration via `--env-file .env` ;
- montent les répertoires utiles (`output_docker`, `gmail_tokens`, `keys`) ;
- **surchargent la commande par défaut** pour lancer explicitement le module souhaité, par exemple `python -m scraper.run ...` ou `python -m gmail_fetcher.fetch_gmail`.

### Exécuter un scraper précis

Linux / macOS :

```bash
docker run --rm -it \
  --env-file .env \
  -v "$(pwd)/output_docker:/app/output_docker" \
  stonelake-scraper:local \
  python -m scraper.run --site aspim --max-pages 1
```

Windows PowerShell :

```powershell
docker run --rm -it `
  --env-file .env `
  -v "$PWD/output_docker:/app/output_docker" `
  stonelake-scraper:local `
  python -m scraper.run --site aspim --max-pages 1
```

### Exécuter le fetch Gmail

Linux / macOS :

```bash
docker run --rm -it \
  --env-file .env \
  -v "$(pwd)/gmail_tokens:/app/gmail_tokens" \
  -v "$(pwd)/output_docker:/app/output_docker" \
  stonelake-scraper:local \
  python -m gmail_fetcher.fetch_gmail
```

Windows PowerShell :

```powershell
docker run --rm -it `
  --env-file .env `
  -v "$PWD/gmail_tokens:/app/gmail_tokens" `
  -v "$PWD/output_docker:/app/output_docker" `
  stonelake-scraper:local `
  python -m gmail_fetcher.fetch_gmail
```

### Exécution avec Snowflake

Si `STORAGE_BACKEND=snowflake` est défini dans `.env`, il faut aussi monter le répertoire contenant la clé privée :

```bash
docker run --rm -it \
  --env-file .env \
  -v "$(pwd)/keys:/app/keys" \
  -v "$(pwd)/gmail_tokens:/app/gmail_tokens" \
  -v "$(pwd)/output_docker:/app/output_docker" \
  stonelake-scraper:local \
  python -m gmail_fetcher.fetch_gmail
```

Exemple de configuration `.env` associée :

```env
STORAGE_BACKEND=snowflake
SNOWFLAKE_ACCOUNT=xxxxxx.eu-central-1
SNOWFLAKE_USER=STONELAKE_SVC
SNOWFLAKE_ROLE=STONELAKE_ROLE
SNOWFLAKE_WAREHOUSE=STONELAKE_WH
SNOWFLAKE_DATABASE=STONELAKE_DB
SNOWFLAKE_SCHEMA=RAW
SNOWFLAKE_PRIVATE_KEY_PATH=keys/rsa_key.p8
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=*****
```

### Répertoires montés recommandés

| Répertoire local  | Montage conteneur     | Utilité                                      |
|-------------------|-----------------------|----------------------------------------------|
| `./output_docker` | `/app/output_docker`  | Récupérer les sorties générées.             |
| `./gmail_tokens`  | `/app/gmail_tokens`   | Fournir `credentials.json` & `token.json`.  |
| `./keys`          | `/app/keys`           | Fournir la clé privée Snowflake.            |

---

## Lancer rapidement l’environnement de développement

Rappel :

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
python -m scraper.run --site aspim --max-pages 1

# Lister les labels Gmail
python -m gmail_fetcher.list_labels

# Extraire les emails + PDF d'un label
python -m gmail_fetcher.fetch_gmail
```

Pour l’exécution en conteneur :

```bash
docker build -t stonelake-scraper:local .
```

puis, par exemple :

```bash
docker run --rm -it \
  --env-file .env \
  -v "$(pwd)/output_docker:/app/output_docker" \
  stonelake-scraper:local \
  python -m scraper.run --site aspim --max-pages 1
```