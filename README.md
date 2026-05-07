# SMDR Python Application

Porting dell'applicazione C# SMDR in Python/Flask/SQLite3.

## 📋 Caratteristiche

### TCP SMDR Server
- Porting fedele del server TCP originale in C#
- Ascolta sulla porta 3000
- Riceve record SMDR come CSV — un record valido è composto da **esattamente 30 campi separati da virgola su una sola riga** (parser permissivo che accetta anche record con ≥6 campi)
- Archivia automaticamente i dati nel database SQLite3 e tiene un dump grezzo mensile in `data/reports/YYYY.MM.csv`

### Flask Web Application
- Web UI interattiva per esplorare i dati
- Ricerche avanzate con filtri multipli
- Statistiche visive (grafici Chart.js)
- Autenticazione via sessione Flask, credenziali da `.env`
- Gestione timezone configurabile a runtime (DST automatico)

### Database
- SQLite3 integrato
- Indici ottimizzati per query rapide
- Supporto per timestamp e duration
- Tabella `app_settings` per configurazione runtime (timezone, modalità timestamp)

## 📁 Struttura Progetto

```
smdr-web/
├── app/                           # Flask application
│   ├── main.py                    # Flask web server e API JSON
│   └── templates/
│       ├── index.html             # Web UI principale
│       └── login.html             # Form di login
├── server/                        # TCP SMDR server
│   ├── tcpsmdrserver.py           # TCP server (porting fedele del C#)
│   └── read.py                    # Utility CLI per leggere il DB
├── data/                          # SQLite database + reports CSV mensili
│   └── reports/                   # Dump grezzi YYYY.MM.csv
├── database.py                    # Schema, query, settings, timezone helpers
├── run.py                         # Entry point: avvia Flask + TCP server
├── check_db.py                    # Script diagnostico per il DB
├── test_e2e.py                    # Test manuale end-to-end (TCP → DB)
├── client_test.py                 # Client TCP di test
├── test_record_client.py          # Invio record SMDR di esempio
├── requirements.txt               # Dipendenze Python
├── Dockerfile.flask               # Dockerfile per Flask
├── Dockerfile.tcpserver           # Dockerfile per TCP server
├── docker-compose.yml             # Configurazione Docker Compose
└── README.md                      # Questo file
```

## 🚀 Avvio Locale

### Opzione 1: Uso di `run.py`

```bash
cd smdr-python
python run.py
```

Questo avvierà sia il server Flask (port 5000) che il TCP Server (port 3000) nello stesso processo (TCP server in thread di background, Flask sul thread principale).

### Opzione 2: Avvio Separato

```bash
# Terminal 1 - Flask Web App
cd smdr-python
python -m app.main

# Terminal 2 - TCP SMDR Server
cd smdr-python
python server/tcpsmdrserver.py
```

### Opzione 3: Docker Compose

```bash
cd smdr-python
docker-compose up -d
```

This avvierà:
- Container Flask: http://localhost:5000
- Container TCP Server: port 3000

## 📡 Formato SMDR

Il server TCP accetta record nel seguente formato:
```
CallStart,ConnectedTime,RingTime,Caller,Direction,DialedNumber,Account,IsInternal,CallID,...
```

**Esempio completo:**
```
28/04/2026 12:34:56,00:02:35,10,12345,I,+39 0123456789,ACCT001,Y,123456789,,
DTMF,Nome1,Phone1,Nome2,Phone2,...,Y,CODE,user,15.50,EUR,...
```

## 🔍 Funzionalità Web

### Dashboard
- Panoramica statistica delle chiamate
- Grafici: chiamate per mese, direzione, top clienti, top numeri chiamati

### API Endpoints

Pagine HTML (richiedono login via sessione):
- `GET /` - Pagina principale
- `GET /login` / `POST /login` - Form di login
- `GET /logout` - Logout

API JSON (richiedono login, restituiscono 401 se non autenticati):
- `GET /search` - Ricerca chiamate con filtri
- `GET /statistics` - Statistiche con filtri di periodo
- `GET /calls/<id>` - Dettagli di una chiamata specifica
- `GET /api/months` - Mesi disponibili (ultimi 24)
- `GET /api/daily` - Chiamate di oggi (timezone configurato)
- `GET /api/daily/<year>` - Chiamate di un anno
- `GET /api/daily/<year>/<month>` - Chiamate di un mese
- `GET /api/daily/<year>/<month>/<day>` - Chiamate di un giorno
- `GET /api/stats/hourly` - Distribuzione oraria (con `start_date` / `end_date`)
- `GET /api/settings` - Legge timezone e `timestamp_mode`
- `POST /api/settings` - Aggiorna timezone e/o `timestamp_mode`

Endpoint pubblico:
- `GET /api/health` - Health check (non richiede autenticazione)

### Filtri di Ricerca
- Direzione (Inbound/Outbound)
- Data di inizio
- Data di fine
- Numero chiamato
- Chiamante
- Account
- Is Internal (Y/N)

## 🛠️ Comandi Docker

### Costruire e avviare
```bash
docker-compose up -d
```

### Vedere log
```bash
docker-compose logs -f smdr-webapp
docker-compose logs -f smdr-tcpserver
```

### Stop
```bash
docker-compose down
```

### Riavviare
```bash
docker-compose restart
```

### Rimuovere e ricreare
```bash
docker-compose down -v
docker-compose up -d
```

## 📊 Statistiche Calcolate

- Totale chiamate
- Chiamate per direzione (Inbound/Outbound)
- Chiamate per internal (Internal/External)
- Top 10 account
- Top 10 chiamanti
- Top 10 numeri chiamati
- Totale durata connessione (ore)
- Totale tempo di suono (minuti)
- Chiamate per mese (ultimi 12 mesi)

## 🔧 Utilità Database

Per leggere il database da command line dentro il container:

```bash
# Entrare nel container
docker-compose exec smdr-webapp bash

# Eseguire script di lettura
python -c "from database import get_db_connection; print(get_db_connection().execute('SELECT * FROM smdr_calls').fetchone())"
```

Oppure usare lo script read.py:

```bash
# Vedi ultimi 10 record
python server/read.py 10

# Vedi statistiche
python server/read.py stats
```

## 📝 Verifica del Codice C#

Il codice C# è stato esaminato scrupolosamente:

1. **SMDR_Server.cs**: Server TCP che ascolta sulla porta 3000
   - ✅ Accetta connessioni TCP
   - ✅ Legge buffer di 4096 byte
   - ✅ Riconosce record completi (30 campi separati da virgola)
   - ✅ Salva record nella forma semplificata (6 campi)
   - ✅ Logga record grezzi
   - ✅ Usa thread per gestire clients

2. **SMDRRecord.cs**: Struttura dati del record
   - ✅ Campi corretti: CallStart, ConnectedTime, RingTime, Caller, CallDirection, DialedNumber
   - ✅ Metodo toString() con formato CSV corretto

3. **Service1.cs**: Service Windows
   - ✅ Avvia server TCP su port 3000
   - ✅ Usa EventLog per log

## 🔒 Autenticazione

L'interfaccia web e tutte le API JSON (eccetto `/api/health`) richiedono login via sessione Flask. Le credenziali sono lette da variabili d'ambiente / file `.env`:

```bash
# .env (NON committare)
SMDR_USERNAME=admin
SMDR_PASSWORD=cambiami
SMDR_SECRET_KEY=stringa-casuale-lunga
```

Default se non impostate: `admin` / `smdr2024` (da cambiare in produzione). Il `SMDR_SECRET_KEY` viene generato casualmente a ogni riavvio se non specificato — questo invalida le sessioni esistenti, quindi vale la pena fissarlo.

I decoratori applicati:
- `@login_required` sulle pagine HTML → redirect a `/login`
- `@api_login_required` sulle API JSON → risposta 401

## 🌍 Timezone e Timestamp

I timestamp ricevuti dal PBX vengono salvati nel DB così come arrivano (naive). L'interpretazione e la conversione per il frontend sono guidate da due chiavi nella tabella `app_settings`, modificabili a runtime tramite `POST /api/settings`:

- `timezone` — nome IANA (default `Europe/Rome`), risolto via `zoneinfo.ZoneInfo`. Gestisce DST automaticamente.
- `timestamp_mode` — `utc` (default) se il PBX invia timestamp UTC, `local` se invia già nella timezone configurata.

`localize_timestamp()` in `database.py` è l'unico punto che converte i timestamp grezzi in stringhe ISO 8601 timezone-aware per le risposte API. Le route Flask usano `_localize_call` / `_localize_calls` prima di restituire JSON.

## 📚 Dipendenze

```
Flask==3.0.0
Werkzeug==3.0.1
python-dotenv==1.0.1
Flask-Login==0.6.3
```

> Nota: `Flask-Login` è elencato ma non attualmente usato — l'auth è implementata con sessioni Flask "vanilla". Mantenuto per eventuale migrazione futura.

Basato su Python 3.11+ (le immagini Docker usano `python:3.14-slim`).

## 🐛 Troubleshooting

### Porta già in uso
```bash
# Windows
netstat -ano | findstr :5000
# kill process con PID trovato

# Linux/Mac
lsof -ti:5000 | xargs kill -9
```

### Database permission error
Assicurarsi che il volume Docker abbia i permessi corretti (default docker-compose gestisce questo).

### Ticket closed channel
Se il canale verra' chiuso prematuramente, verrà inviato un backup completo prima della chiusura.