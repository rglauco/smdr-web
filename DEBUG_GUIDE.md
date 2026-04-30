# Guía de Debug - Registro TCP SMDR non Salvato

## 🐛 Problema Segnalato
"niente da fare non capisco, non salva i dati nel db, li vedo passare via tcpdump ma il db resta vuoto"

## 📊 Analisi del Problema

Il server TCP SMDR considera **VALIDO solo un record se contiene ESATTAMENTE 30 campi separati da virgola e sono su UNA SOLA LINEA**.

### Formati di registro accettati:

✅ **Valido (30 campi da una riga):**
```
28/04/2026 16:34:56,00:02:35,12.5,12345,I,+39 0123456789,ACCT001,Y,...
```

❌ **Non valido (32 campi in più righe):**
```
28/04/2026 16:34:56,00:02:35,12.5,12345,I,+39 0123456789,ACCT001,Y,...
DTMF,Marco Rossi,UO1,Beatrice Rossi,UO2,35.0,0,
Y,CODE123,user,15.50,EUR,ACCT001,15.50,0.052,...
```

### Cosa fare: Allinea i record SMDR in UNA SOLA RIGA

## 🔧 Passaggi per Debug

### Passo 1: Avviate il Server con LOG

```bash
cd smdr-python
python run.py
```

Osservate:
- Devete vedere il server al port 5000
- Devete se avere il container al 3000
- Potete vedere i log in tempo REALE

### Passo 2: Inviate un record dalla vostra sorgente

Avvisate LA VOCCA sorgente SMDR di riportare il record in **una sola riga** di 30+ campo.

Importante: Il formato deve essere esattamente CSV con virgola di separazione, senza newline intermedie.

### Passo 3: Verificate i log

Nel terminal dove avviate il server, dovete vedere:

```
Linea ricevuta (XXX chars):
  Content: 28/04/2026 16:34:56,00:02:35,12.5,12345,I,+39 0123456789,ACCT001,Y,...
  Campi nel record: 10
  Is valid SMDR (30 campi): False  <-- Questo è il problema!
```

VIENE mostrato se il record viene salvato:
```bash
!!! SALVATO IN DB - ID: X
```

## ✅ Soluzioni Proposte

### Soluzione A: Modificate la sorgente C#

Ora che sapete il formato esatto, chi deve modificare il server C#:

1. Raccogliete i singoli buffer ricevuti
2. Raggruppate quando ricevete esattamente:
   - 30 parti con `isSMDRRecord("stringa")` *returns TRUE*

Il server C# potrebbe essere configurato con un controllo diverso. Potrebbe su neon essere decompilabile.

### Soluzione B: Middleware Python

Propongo creare un "gateway" Python che:
1. Riceve i dati TCP (come ora fa)
2. Raggruppa i record parziali
3. Unisce le parti assenti fino a 30 campi
4. Salva UNICA RIGA VALIDA nel database

Voglio vedere ATTRAVERSO `tcpdump` che record STANNO arrivando:

```bash
docker ps | grep smdr
# Controlla quale container sta gestendo il TCP server

docker logs smdr-tcpserver -f
# Vedete i LOG dal server (dovete riavviare con DEBUG)
```

### Soluzione C: Test dal lato del server (come ora fatto)

Inviate un test record MANUALE per vedere se il salvataggio funziona:

```bash
# Finestra 1: Server Python
cd smdr-python
python run.py

# Finestra 2: Client di test
cd smdr-python
python test_record_client.py localhost 3000
```

Guardate cosa succede!

### Soluzione D: Log ravvicinato utilizzando le prime 50 caratteri di ogni buffer

Vedete se il server riceve UN QUALCUO più di quello che mostrate.

#### Il problema INFINITO era nella logica del server TCP:

La `handle_client` in `tcpsmdrserver.py` fa:

```python
lines = buffer.split('\n')
buffer = lines.pop()  # Keep the last incomplete line

for line in lines:
    if self.is_valid_smdr_record(line):
        # salva record
```

Ma se un record ha 30 campi ma è ricevuto su più righe, la prima parte ha meno di 30 campi e NON viene salvata!

#### Il problema è nella codifica/decodizzazione:

Controllate se il serio stiamo ricevendo `строков` con newline nel buffer.

## 📋 Comandi per Verifica Rapida

### Verifica dei log del server (quando riavviate con DEBUG):

```bash
# Finestra 1: Server con log DEBUG
cd smdr-python
python run.py

# Guardate nel terminale per vedere:
Linea ricevuta (XXX chars):
  Campi nel record: 10
  Is valid SMDR (30 campi): False
  → Record NON salvato (non valido)
```

### Verifica del database:

```bash
# Odor substitutazione col container Docker
docker-compose exec smdr-webapp python check_db.py

# O se eseguite qui invece:
cd smdr-python
python check_db.py
```

## 🔍 Fase 2: Analizziamo i buffer

Riavviate il server con questa versione DEBUG e inviate di nuovo un record. Guardate nel terminale:

```
>>> Inviate record da sorgente TCP
>>> Guardate qui cosa appaiono LOG:
Linea ricevuta (len=X chars):
  Campi: Y
  Is valid SMDR: TRUE/FALSE
```

Se è FALSE per tutti, il formato NON è quello aspettato.

## 🎯 Atteso risucitare: Quando la sorgente telecom invia:

```
Record VALIDO (30 campi su UNA RIGA):
28/04/2026 16:34:56,00:02:35,12.5,12345,I,+39 0123456789,ACCT001,Y,123456789,DTMF,Marco Rossi,UO1,Beatrice Rossi,UO2,35.0,0,Y,CODE123,user,15.50,EUR,ACCT001,15.50,0.052,24,123,Call Name,123456,0

DEVE essere una sola riga!
```

Se le comunicazioni arrivano su più righe ATTIVATE, dovrete modificare LISCE in modo che le raggruppi.

Vuoi che creiamo un middleware Python che fa raggruppare le parti del record?