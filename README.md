# SMDR Analytics

Applicazione Python/Flask per la raccolta e l'analisi dei record telefonici SMDR (Station Message Detail Recording). Due servizi condividono un unico database SQLite:

- **TCP Server** (`server/tcpsmdrserver.py`, porta 3000) — riceve i record CSV dal centralino e li persiste nel DB.
- **Web App** (`app/main.py`, porta 5000) — dashboard interattiva, ricerca avanzata e API JSON.

## Caratteristiche

### TCP Server
- Ascolta sulla porta 3000
- Accetta record SMDR in formato CSV — un record valido ha **esattamente 30 campi** su una sola riga; parser permissivo di riserva per record con ≥ 6 campi
- Archivia i dati in SQLite e produce un dump grezzo mensile in `data/reports/YYYY.MM.csv`
- Gestione connessioni concorrenti via thread

### Web App
- Interfaccia dark/day con toggle, font IBM Plex Mono/Sans
- Dashboard con KPI (totale chiamate, tasso di risposta, ACD, ASA, service level)
- Grafici interattivi: andamento temporale, distribuzione oraria, heatmap settimanale, distribuzione durate, flussi E/I, carico estensioni, top account/numeri
- Rilevamento anomalie e confronto tra periodi
- Ricerca con filtri multipli ed export CSV
- Dettaglio per numero: KPI, trend, controparti, ultime chiamate
- Autenticazione via sessione Flask
- Timezone e modalità timestamp configurabili a runtime

### Database
- SQLite3 con WAL mode e busy timeout per accesso concorrente
- Tabella `smdr_calls` (~30 colonne, una per campo SMDR + `raw_data`)
- Tabella `app_settings` per configurazione runtime (`timezone`, `timestamp_mode`)

## Struttura

```
smdr-web/
├── app/
│   ├── main.py                # Flask web server e API JSON
│   └── templates/
│       ├── index.html         # Web UI (dashboard + ricerca)
│       └── login.html         # Form di login
├── server/
│   ├── tcpsmdrserver.py       # TCP server SMDR
│   └── read.py                # Utility CLI per leggere il DB
├── data/                      # Database SQLite + report CSV mensili
│   └── reports/               # Dump grezzi YYYY.MM.csv
├── database.py                # Schema, query, helpers timezone
├── run.py                     # Entry point: Flask + TCP server nello stesso processo
├── docker-entrypoint.sh       # Fix permessi volume Docker (gosu)
├── Dockerfile.flask
├── Dockerfile.tcpserver
├── docker-compose.yml
├── check_db.py                # Script diagnostico DB
├── test_e2e.py                # Test manuale TCP → DB
└── test_record_client.py      # Invio record SMDR di esempio
```

## Avvio

### Locale

```bash
# Flask + TCP server in un unico processo
python run.py

# Oppure separatamente
python -m app.main          # solo Flask  (porta 5000)
python server/tcpsmdrserver.py   # solo TCP    (porta 3000)
```

### Docker

```bash
docker-compose up -d

# Log
docker-compose logs -f smdr-webapp
docker-compose logs -f smdr-tcpserver

# Stop
docker-compose down

# Rebuild immagini
docker-compose build --no-cache && docker-compose up -d
```

Il database è persistito nel volume Docker `smdr-data`. L'entrypoint sistema i permessi della directory montata prima di cedere i privilegi all'utente `smdr`.

## Configurazione

Crea un file `.env` nella root (non committarlo):

```bash
SMDR_USERNAME=admin
SMDR_PASSWORD=cambiami
SMDR_SECRET_KEY=stringa-casuale-lunga
```

Se non impostati, i default sono `admin` / `smdr2024`. Il `SMDR_SECRET_KEY` viene generato casualmente a ogni avvio se assente — questo invalida le sessioni esistenti, vale la pena fissarlo.

**Timezone e modalità timestamp** si configurano a runtime dalla UI (badge orologio in navbar) o via API:

```bash
curl -X POST http://localhost:5000/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"timezone":"Europe/Rome","timestamp_mode":"utc"}'
```

- `timezone` — nome IANA, default `Europe/Rome`. Gestisce DST automaticamente.
- `timestamp_mode` — `utc` se il centralino invia timestamp UTC, `local` se li invia già in orario locale.

## API

Tutte le API JSON richiedono autenticazione (401 se non autenticato), eccetto `/api/health`.

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| `GET` | `/` | Dashboard principale |
| `GET` | `/search` | Ricerca chiamate (`call_direction`, `start_date`, `end_date`, `dialed_number`, `caller`, `account`, `flow_type`, `limit`, `offset`) |
| `GET` | `/statistics` | Statistiche aggregate (stessi filtri di `/search`) |
| `GET` | `/calls/<id>` | Dettaglio singola chiamata |
| `GET` | `/api/settings` | Legge timezone e timestamp_mode |
| `POST` | `/api/settings` | Aggiorna timezone e/o timestamp_mode |
| `GET` | `/api/stats/hourly` | Distribuzione oraria |
| `GET` | `/api/stats/heatmap` | Heatmap giorno × ora |
| `GET` | `/api/stats/duration-histogram` | Istogramma durate |
| `GET` | `/api/stats/number-categories` | Categorie numeri (mobile/fisso/…) |
| `GET` | `/api/stats/dow` | Distribuzione per giorno della settimana |
| `GET` | `/api/stats/anomalies` | Rilevamento anomalie (z-score) |
| `GET` | `/api/stats/compare` | Confronto periodo corrente vs precedente |
| `GET` | `/api/stats/flows` | Distribuzione flussi E→I / I→E / I→I / E→E |
| `GET` | `/api/stats/extension-load` | Carico per estensione |
| `GET` | `/api/stats/transfers` | Trasferimenti rilevati per prossimità temporale |
| `GET` | `/api/stats/number-detail` | KPI + grafici per singolo numero |
| `GET` | `/api/export/calls.csv` | Export CSV delle chiamate filtrate |
| `GET` | `/api/daily[/<year>[/<month>[/<day>]]]` | Chiamate per giorno/mese/anno |
| `GET` | `/api/months` | Mesi disponibili (ultimi 24) |
| `GET` | `/api/health` | Health check (pubblico) |

## Formato SMDR

Il TCP server accetta record nel formato CSV a 30 campi emesso dal centralino:

```
CallStart,ConnectedTime,RingTime,Caller,Direction,DialedNumber,Account,IsInternal,CallID,...
```

La data usa il formato `DD/MM/YYYY HH:MM:SS`. Il parser prova anche ISO e US come fallback.

## Utilità da riga di comando

```bash
# Ultimi N record
python server/read.py 10

# Statistiche aggregate
python server/read.py stats

# Diagnostica DB
python check_db.py

# Test end-to-end (invia un record via TCP e verifica il DB)
python test_e2e.py

# Invio record di esempio
python test_record_client.py
```

## Dipendenze

```
Flask==3.0.0
Werkzeug==3.0.1
python-dotenv==1.0.1
Flask-Login==0.6.3
```

Python 3.11+ (le immagini Docker usano `python:3.14-slim`).
