# AGENTS.md

Guida per agenti AI (Claude Code, Codex, Cursor, ecc.) che lavorano su questo repository.

## Panoramica progetto

Applicazione Python/Flask di logging telefonico SMDR (Station Message Detail Recording), porting di un originale C#. Due servizi condividono un unico database SQLite:

- **TCP SMDR server** (`server/tcpsmdrserver.py`, porta 3000) — accetta record CSV da un centralino (PBX) e li persiste.
- **Web app Flask** (`app/main.py`, porta 5000) — UI di ricerca, dashboard statistiche e API JSON sullo stesso database.

Codice, log e la maggior parte dei commenti sono in italiano. Preserva questa lingua quando modifichi stringhe/commenti esistenti, salvo richiesta esplicita dell'utente.

## Avvio

```bash
# Entrambi i servizi in un solo processo (Flask nel thread principale, TCP server in background)
python run.py

# Oppure separatamente
python -m app.main                  # solo Flask
python server/tcpsmdrserver.py      # solo TCP server

# Docker — due container che condividono il volume nominato smdr-data
docker-compose up -d
docker-compose logs -f smdr-webapp
docker-compose logs -f smdr-tcpserver
```

`init_database()` viene eseguito all'avvio di Flask, quindi DB e cartella `data/` vengono creati al primo lancio. Il TCP server scrive anche dump CSV grezzi mensili in `data/reports/YYYY.MM.csv` (mirror del comportamento `OutputSMDR` del C# originale).

**Variabili d'ambiente obbligatorie** (in `.env`, gitignored): `SMDR_USERNAME`, `SMDR_PASSWORD`, `SMDR_SECRET_KEY`. Se una manca, `app/main.py` stampa un messaggio di errore e chiama `sys.exit(1)` — **non esistono credenziali di default hardcoded** nel codice attuale (nonostante quanto suggerito da vecchia documentazione). Opzionale: `SMDR_COOKIE_SECURE=false` per servire su HTTP semplice in locale (di default i cookie di sessione richiedono HTTPS).

## "Test"

Non esiste un framework di test. Gli script `test_*.py` e `check_db.py` nella root sono tool di integrazione manuale da eseguire contro un server live:

```bash
python test_e2e.py            # apre un socket TCP verso localhost:3000, invia un record a 30 campi, verifica il DB
python test_record_client.py  # invia record di esempio in varie forme
python check_db.py            # stampa statistiche DB e righe recenti
python server/read.py 10      # mostra le ultime 10 chiamate
python server/read.py stats   # mostra statistiche aggregate
```

Non aggiungere scaffolding di test framework (pytest, ecc.) senza che sia richiesto esplicitamente.

## Architettura

### Livello dati condiviso — `database.py`

Entrambi i servizi importano da `database.py`. Possiede schema, tutte le query e la logica di timezone/settings.

- `smdr_calls` è una tabella larga (~30 colonne) che rispecchia i campi del record C# originale. `raw_data` conserva la riga CSV originale.
- `app_settings` contiene la config runtime come coppie chiave/valore. Due chiavi rilevanti:
  - `timezone` (default `Europe/Rome`) — nome IANA risolto via `zoneinfo.ZoneInfo`.
  - `timestamp_mode` (`utc` o `local`, default `utc`) — descrive come vanno interpretati i timestamp inviati dal PBX e salvati in `call_start`.
- `localize_timestamp()` è l'unico punto che converte un timestamp naive salvato in una stringa ISO tz-aware per l'API. Le route Flask avvolgono i dict delle chiamate con `_localize_call` / `_localize_calls` prima di restituire il JSON. **Non aggirare questo meccanismo** — le stringhe `call_start` grezze sono timezone-naive e verrebbero mostrate in modo errato nella UI.
- `_build_where_clause()` centralizza il parsing dei filtri per le query statistiche; riusala invece di costruire WHERE ad-hoc.
- Classificazione flusso chiamata (`II`/`IE`/`EI`/`EE`) ed euristica interno/esterno (`get_number_categories`, `_NUMBER_CLASSIFICATION`) si basano sulla **lunghezza** di `caller`/`dialed_number` (soglia `_INTERNAL_LEN = 4`) e su pattern `GLOB` italiani (mobile, verde, premium, internazionale). Non è una vera analisi del piano di numerazione: è un'euristica, documentata come tale nei docstring — trattala di conseguenza se estendi la logica.
- `get_transfer_matrix()` rileva trasferimenti in modo euristico per prossimità temporale (nessun ID di correlazione emesso dal PBX). `get_anomalies()` usa uno z-score sul conteggio giornaliero.
- **Nessuna modalità WAL né `busy_timeout` è configurata** in `get_db_connection()`, nonostante il README affermi il contrario. Il TCP server scrive da thread multipli (uno per client) e Flask legge concorrentemente sullo stesso file SQLite: tienine conto (occhio a `database is locked`) prima di introdurre scritture più pesanti o transazioni lunghe.

### TCP server — porting fedele del C#

`server/tcpsmdrserver.py` è intenzionalmente un porting linea-per-linea del `SMDR_Server.cs` originale. Nomi di metodo (`HandleClientComm`, `ListenForClients`, `isSMDRRecord`, `createBasicSMDRRecordFromString`, `OutputSMDR`) e comportamenti sono mantenuti di proposito — i commenti citano il C# corrispondente. Quando modifichi questo file, preserva la parità con il C# a meno che la modifica non sia esplicitamente pensata per divergere.

Invariante chiave dal C#: `isSMDRRecord()` ritorna true solo per **esattamente 30 campi separati da virgola su una singola riga**. La versione Python aggiunge un fallback permissivo che parsifica comunque righe con ≥ 6 campi (loggato come "tentativo parsing permissivo"). `DEBUG_GUIDE.md` spiega perché questo conta — PBX che spezzano i record su più pacchetti/righe TCP falliscono silenziosamente il controllo stretto.

Il parsing data in `createBasicSMDRRecordFromString` prova prima `%d/%m/%Y %H:%M:%S` (formato PBX), poi fallback ISO/US. Se tutti i parse falliscono, ricade su `datetime.now()` invece di scartare il record.

### Web app Flask

`app/main.py` è un'app Flask a file singolo. L'autenticazione è basata su sessione contro le variabili d'ambiente `SMDR_USERNAME`/`SMDR_PASSWORD` (nessun default — vedi sopra), caricate via `python-dotenv` da `.env`. Il confronto credenziali usa `hmac.compare_digest` per evitare timing attack (entrambi username e password vengono sempre confrontati, indipendentemente da quale fallisce per primo).

- `@login_required` per le pagine HTML (redirect a `/login`), `@api_login_required` per gli endpoint JSON (ritorna 401 invece di redirect).
- `/api/health` è intenzionalmente non autenticato.
- Cookie di sessione hardened: `SESSION_COOKIE_SECURE` di default `True` (override con `SMDR_COOKIE_SECURE=false` in dev su HTTP), `HTTPONLY`, `SAMESITE=Lax`, durata 8 ore.
- `app/templates/index.html` (~3150 righe) è la UI a pagina singola (dashboard + ricerca); `login.html` è il form di login. Il frontend legge `tz_info` (restituito da `/api/settings` e incorporato nelle risposte di `/statistics`) per mostrare correttamente gli orari.

Il README afferma "nessuna autenticazione" in alcuni punti — è obsoleto/errato, l'autenticazione è attiva e obbligatoria (l'app non parte senza le env var). Non fidarti del README su questo punto; verifica sempre contro `app/main.py`.

### Configurazione

- `.env` (gitignored) fornisce `SMDR_USERNAME`, `SMDR_PASSWORD`, `SMDR_SECRET_KEY`, opzionale `SMDR_COOKIE_SECURE`. Non committarlo; non hardcodare segreti in `app/main.py`.
- Timezone e `timestamp_mode` sono impostazioni runtime in `app_settings`, modificabili via `POST /api/settings` — non variabili d'ambiente.
- `requirements.txt` elenca `Flask-Login` ma il codice usa sessioni Flask semplici. Se sei tentato di "ripulire" la dipendenza, verifica prima con l'utente se vuole effettivamente migrare a Flask-Login.

## Cosa evitare

- Non bypassare `localize_timestamp()` / `_localize_call` / `_localize_calls` quando restituisci timestamp dalle API.
- Non introdurre credenziali di default o fallback silenziosi per le variabili d'ambiente di autenticazione: il fail-fast attuale (`_require_env`) è intenzionale.
- Non trattare le euristiche di classificazione numero/flusso/trasferimento come dati esatti quando scrivi documentazione o UI — sono best-effort e documentate come tali nel codice.
- Non aggiungere test framework o dipendenze non richieste esplicitamente.
