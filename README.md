# SMDR Python Application

Porting dell'applicazione C# SMDR in Python/Flask/SQLite3.

## 📋 Caratteristiche

### TCP SMDR Server
- Port del server TCP originale in C#
- Ascolta sulla porta 3000
- Riceve record SMDR come CSV (32 campi se completo, approssimativamente 30 per record completo)
- Archive automaticamente i dati nel database SQLite3

### Flask Web Application
- Web UI interattiva per esplorare i dati
- Ricerche avanzate con filtri multipli
- Statistiche visive (grafici Chart.js)
- Nessuna autenticazione configurata

### Database
- SQLite3 integrato
- Indici ottimizzati per query rapide
- Supporto per timestamp e duration

## 📁 Struttura Progetto

```
smdr-python/
├── app/                           # Flask application
│   ├── main.py                    # Flask web server
│   └── templates/
│       └── index.html            # Web UI
├── server/                        # TCP SMDR server
│   ├── tcpsmdrserver.py           # TCP server implementation
│   └── read.py                    # Utility to read database
├── data/                          # SQLite database (volume)
├── database.py                    # Database functions
├── run.py                         # Main entry point
├── requirements.txt              # Python dependencies
├── Dockerfile.flask              # Dockerfile for Flask
├── Dockerfile.tcpserver          # Dockerfile for TCP server
├── docker-compose.yml            # Docker Compose configuration
└── README.md                     # This file
```

## 🚀 Avvio Locale

### Opzione 1: Uso di `run.py`

```bash
cd smdr-python
python run.py
```

Questo avvierà sia il server Flask (port 5000) che il TCP Server (port 3000).

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
- `GET /` - Pagina principale
- `GET /search` - Ricerca chiamate con filtri
- `GET /statistics` - Statistiche completi
- `GET /calls/<id>` - Dettagli di una chiamata specifica
- `GET /api/months` - Mesi disponibili
- `GET /api/daily/<year>/<month>/<day>` - Chiamate di un giorno
- `GET /api/health` - Health check

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

## 🔒 Sicurezza

- Attualmente **NESSUNA autenticazione** configurata
- Il database SQLite è accessibile direttamente
- RESTO IN ATTESA DI INSTRUCTIONS PER GESTIRE CREDENZIALI: l'utente ha detto "al momento non serve user e password per accedere alla interfaccia web". Se cambia idea in futuro, aggiungo:

### Pronto per autenticazione nel futuro:
```python
# Auth example (da implementare quando richiesto)
from functools import wraps
from flask import session, redirect, url_for

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
```

## 📚 Dipendenze

```
Flask==3.0.0
Werkzeug==3.0.1
```

Tutto in un singolo file requirements.txt per facilità, basato sulla versione Python 3.11.

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