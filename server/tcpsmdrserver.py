"""
TCP SMDR Server - Fedele porting del codice C# SMDR_Server.cs
Listens for SMDR records on TCP port 3000
Salva tutto su file di log grezzo + DB SQLite3
"""
import socket
import threading
import time
import os
import sys
import re
from datetime import datetime

# Add parent directory to path so we can import database module
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import add_smdr_record

TCP_PORT = 3000
BUFFER_SIZE = 4096

# Directory per i log grezzi (come il C# che scrive in Reports\)
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'reports')


def ensure_reports_dir():
    """Crea la directory Reports se non esiste"""
    os.makedirs(REPORTS_DIR, exist_ok=True)


def write_raw_to_file(raw_string):
    """
    Fedele porting di OutputSMDR(_record, isRaw=true) del C#
    Salva i dati grezzi in un file CSV mensile nella cartella Reports
    """
    ensure_reports_dir()
    filename = datetime.now().strftime('%Y.%m') + '.csv'
    filepath = os.path.join(REPORTS_DIR, filename)
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(raw_string.rstrip('\r\n') + '\n')
    except Exception as e:
        print(f"[RAW LOG ERROR] {e}")


class TCPSMDRServer:
    def __init__(self, port=3000):
        self.port = port
        self.server_socket = None
        self.listen_thread = None
        self.running = False
        self.log_raw = True

    # ------------------------------------------------------------------ #
    #  Fedele porting di isSMDRRecord() dal C#
    #  Il C# fa: return _in.Split(',').Length == 30;
    #  --> controlla se la stringa ha ESATTAMENTE 30 campi separati da virgola
    # ------------------------------------------------------------------ #
    def isSMDRRecord(self, data_string):
        """
        Fedele porting di C# isSMDRRecord(string _in)
        Verifica se la stringa ha esattamente 30 campi separati da virgola
        """
        if not data_string or not data_string.strip():
            return False
        cleaned = data_string.strip().rstrip('\r\n')
        parts = cleaned.split(',')
        return len(parts) == 30

    # ------------------------------------------------------------------ #
    #  Fedele porting di createBasicSMDRRecordFromString() dal C#
    # ------------------------------------------------------------------ #
    def createBasicSMDRRecordFromString(self, data_string):
        """
        Fedele porting di C# createBasicSMDRRecordFromString(string _in)
        Parsifica i primi 6 campi essenziali come fa il C#
        """
        strArray = data_string.strip().rstrip('\r\n').split(',')

        # -- CallStart: DateTime.Parse(strArray[0]) --
        call_start = None
        for fmt in ('%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S'):
            try:
                call_start = datetime.strptime(strArray[0].strip(), fmt)
                break
            except (ValueError, IndexError):
                continue
        if call_start is None:
            call_start = datetime.now()

        # -- ConnectedTime: TimeSpan.Parse(strArray[1]) --
        connected_secs = 0
        try:
            ct = strArray[1].strip()
            ct_parts = ct.split(':')
            if len(ct_parts) == 3:
                connected_secs = int(ct_parts[0]) * 3600 + int(ct_parts[1]) * 60 + int(float(ct_parts[2]))
            elif len(ct_parts) == 2:
                connected_secs = int(ct_parts[0]) * 60 + int(float(ct_parts[1]))
            else:
                connected_secs = int(float(ct))
        except (ValueError, IndexError):
            pass

        # -- RingTime: TimeSpan.FromSeconds(Convert.ToDouble(strArray[2])) --
        ring_secs = 0.0
        try:
            ring_secs = float(strArray[2].strip())
        except (ValueError, IndexError):
            pass

        # -- Caller: string.IsNullOrEmpty(strArray[3]) ? "Unknown" : strArray[3] --
        caller = "Unknown"
        try:
            if strArray[3].strip():
                caller = strArray[3].strip()
        except IndexError:
            pass

        # -- CallDirection: !(strArray[4] == "I") ? "Outbound" : "Inbound" --
        direction = "Outbound"
        try:
            if strArray[4].strip() == "I":
                direction = "Inbound"
        except IndexError:
            pass

        # -- DialedNumber: string.IsNullOrEmpty(strArray[5]) ? "Unknown" : strArray[5] --
        dialed_number = "Unknown"
        try:
            if strArray[5].strip():
                dialed_number = strArray[5].strip()
        except IndexError:
            pass

        # -- Campi aggiuntivi (non gestiti dal C# originale, ma li salviamo) --
        def safe_get(idx, default=None):
            try:
                v = strArray[idx].strip()
                return v if v else default
            except (IndexError, ValueError):
                return default

        def safe_float(idx, default=None):
            v = safe_get(idx)
            if v is None:
                return default
            try:
                return float(v)
            except ValueError:
                return default

        record = {
            'call_start': call_start.isoformat(),
            'connected_time': connected_secs,
            'ring_time': ring_secs,
            'caller': caller,
            'call_direction': direction,
            'dialed_number': dialed_number,
            'account': safe_get(6),
            'is_internal': safe_get(7),
            'call_id': safe_get(8),
            'continuation': safe_get(9),
            'party1_device': safe_get(10),
            'party1_name': safe_get(11),
            'party2_device': safe_get(12),
            'party2_name': safe_get(13),
            'hold_time': safe_float(14),
            'park_time': safe_float(15),
            'auth_valid': safe_get(16),
            'auth_code': safe_get(17),
            'user_charged': safe_get(18),
            'call_charge': safe_float(19),
            'currency': safe_get(20),
            'account_last_change': safe_get(21),
            'call_units': safe_float(22),
            'units_last_change': safe_float(23),
            'cost_per_unit': safe_float(24),
            'markup': safe_float(25),
            'external_targeting_cause': safe_get(26),
            'external_targeter_id': safe_get(27),
            'external_targeted_number': safe_get(28),
        }
        return record

    # ------------------------------------------------------------------ #
    #  OutputSMDR - salva su file CSV (come il C#)
    # ------------------------------------------------------------------ #
    def OutputSMDR(self, record_string, is_raw):
        """
        Fedele porting di C# OutputSMDR(string _record, bool isRaw)
        Salva su Reports/YYYY.MM.csv
        """
        ensure_reports_dir()
        filename = datetime.now().strftime('%Y.%m') + '.csv'
        filepath = os.path.join(REPORTS_DIR, filename)
        try:
            is_new = not os.path.exists(filepath) or os.path.getsize(filepath) == 0
            with open(filepath, 'a', encoding='utf-8') as f:
                if is_new:
                    if is_raw:
                        f.write("Call Start,Connected Time,Ring Time,Caller,Direction,Called Number,Dialled Number,Account,Is Internal,Call ID,Continuation,Party1Device,Party1Name,Party2Device,Party2Name,Hold Time,Park Time,Auth Valid,Auth Code,User Charged,Call Charge,Currency,Account at Last User Change,Call Units,Units at Last User Change,Cost per Unit,Mark Up,External Targeting Cause,External Targeter Id,External Targeted Number\n")
                    else:
                        f.write("Call Start,Connected Time,Ring Time,Caller,Call Direction,Dialed Number\n")
                f.write(record_string.rstrip('\r\n') + '\n')
        except Exception as e:
            print(f"[CSV WRITE ERROR] {e}")

    # ------------------------------------------------------------------ #
    #  Salvataggio su DB SQLite3
    # ------------------------------------------------------------------ #
    def save_to_database(self, record_data, raw_line):
        """Salva record nel database SQLite3"""
        try:
            call_id = add_smdr_record(record_data, raw_line)
            print(f"  >> SALVATO DB id={call_id} | {record_data['call_direction']:8s} | {record_data['caller']:15s} -> {record_data['dialed_number']}")
            return call_id
        except Exception as e:
            print(f"  >> ERRORE DB: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ------------------------------------------------------------------ #
    #  HandleClientComm - fedele porting del C#
    # ------------------------------------------------------------------ #
    def HandleClientComm(self, client):
        """
        Fedele porting del C# HandleClientComm(object client)
        Legge dati dal socket e per ogni ricezione:
          1. Logga i dati grezzi (come C# logRaw)
          2. Verifica se il buffer ricevuto è un record SMDR completo (30 campi)
          3. Se sì, parsifica e salva nel DB
        """
        client_socket = client
        addr = client_socket.getpeername()
        print(f"\033[96m[{addr[0]}:{addr[1]}] CONNESSIONE STABILITA\033[0m")

        try:
            client_socket.settimeout(30.0)  # timeout lungo, come il C# che non ha timeout
            recv_buffer = b''

            while self.running:
                # -----------------------------------------------------------
                # C#: count = stream.Read(numArray, 0, 4096);
                # -----------------------------------------------------------
                try:
                    data = client_socket.recv(BUFFER_SIZE)
                except (ConnectionResetError, ConnectionAbortedError, OSError):
                    break

                if not data:
                    # C#: if (count != 0) ... else goto label_14 (chiude)
                    break

                # C#: @string = new ASCIIEncoding().GetString(numArray, 0, count);
                raw_string = data.decode('ascii', errors='replace')

                # -----------------------------------------------------------
                # C#: if (this.logRaw) this.OutputSMDR(@string, true);
                # -----------------------------------------------------------
                if self.log_raw:
                    self.OutputSMDR(raw_string, True)
                    # mostra solo i primi 150 caratteri per non intasare la console
                    display = raw_string.strip().rstrip('\r\n')
                    n_fields = len(display.split(','))
                    print(f"\033[93m  RAW ({len(data)} bytes, {n_fields} campi): {display[:120]}\033[0m")

                # -----------------------------------------------------------
                # Il PBX può inviare più record in una sola ricezione TCP,
                # oppure un record parziale. Dividiamo per linea e
                # processiamo ogni riga.
                # -----------------------------------------------------------
                # Puliamo i caratteri di terminazione e splittiamo
                raw_clean = raw_string.replace('\r\n', '\n').replace('\r', '\n')
                lines = raw_clean.split('\n')

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # -----------------------------------------------------------
                    # C#: while (!this.isSMDRRecord(@string));
                    # -----------------------------------------------------------
                    if self.isSMDRRecord(line):
                        print(f"\033[92m  >> RECORD VALIDO (30 campi) - salvo...\033[0m")

                        # C#: this.OutputSMDR(this.createBasicSMDRRecordFromString(@string).ToString(), false);
                        basic = self.createBasicSMDRRecordFromString(line)
                        if basic:
                            # Salva su file CSV (formato semplificato, come il C#)
                            simplified = (f"{basic['call_start']},{basic['connected_time']},"
                                         f"{basic['ring_time']},{basic['caller']},"
                                         f"{basic['call_direction']},{basic['dialed_number']}")
                            self.OutputSMDR(simplified, False)

                            # Salva su DB SQLite3
                            self.save_to_database(basic, line)
                        else:
                            print(f"\033[91m  >> PARSING FALLITO\033[0m")
                    else:
                        # Non è un record completo a 30 campi.
                        # Proviamo comunque a vedere se ha almeno i primi
                        # 6 campi essenziali del formato semplificato.
                        n = len(line.split(','))
                        if n >= 6:
                            # Potrebbe essere un record parziale o con un
                            # numero di campi diverso da 30.
                            # Proviamo a parsificarlo ugualmente (più permissivo del C#)
                            print(f"\033[93m  >> Record con {n} campi (non 30) - tentativo parsing permissivo...\033[0m")
                            try:
                                basic = self.createBasicSMDRRecordFromString(line)
                                if basic:
                                    simplified = (f"{basic['call_start']},{basic['connected_time']},"
                                                 f"{basic['ring_time']},{basic['caller']},"
                                                 f"{basic['call_direction']},{basic['dialed_number']}")
                                    self.OutputSMDR(simplified, False)
                                    self.save_to_database(basic, line)
                                    print(f"\033[92m  >> Salvato comunque (permissivo)\033[0m")
                            except Exception as e:
                                print(f"\033[91m  >> Parsing permissivo fallito: {e}\033[0m")
                        else:
                            print(f"\033[90m  >> Ignorato ({n} campi): {line[:80]}\033[0m")

        except Exception as e:
            print(f"\033[91m[{addr[0]}:{addr[1]}] ERRORE: {e}\033[0m")
            import traceback
            traceback.print_exc()
        finally:
            try:
                client_socket.close()
            except OSError:
                pass
            print(f"\033[91m[{addr[0]}:{addr[1]}] CONNESSIONE CHIUSA\033[0m")

    # ------------------------------------------------------------------ #
    #  ListenForClients - fedele porting del C#
    # ------------------------------------------------------------------ #
    def ListenForClients(self):
        """
        Fedele porting del C# ListenForClients()
        """
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(10)

            print("\033[95m\033[1m")
            print("=" * 60)
            print(f"{'TCP SMDR Server - Python':^60}")
            print("=" * 60)
            print("\033[0m")
            print(f"Porta TCP: {self.port}")
            print(f"Log raw: {self.log_raw}")
            print(f"Reports: {REPORTS_DIR}")
            print(f"DB: SQLite3")
            print("\033[95mIn attesa di connessioni SMDR...\033[0m")
            print("=" * 60)

            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    # Come il C#: nuovo thread per ogni client
                    client_thread = threading.Thread(
                        target=self.HandleClientComm,
                        args=(client_socket,),
                        daemon=True
                    )
                    client_thread.start()
                except OSError:
                    if self.running:
                        print("\033[93mServer interrotto\033[0m")
                    break
        except Exception as e:
            print(f"\033[91mErrore server: {e}\033[0m")
        finally:
            self.stop()

    def start(self):
        """Avvia il server"""
        if self.running:
            print("\033[93mServer già in esecuzione\033[0m")
            return
        self.running = True
        self.listen_thread = threading.Thread(target=self.ListenForClients, daemon=True)
        self.listen_thread.start()
        print(f"\033[92mServer avviato sulla porta {self.port}\033[0m")

    def stop(self):
        """Ferma il server"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
        print("\033[92mServer fermato\033[0m")


if __name__ == '__main__':
    print("\033[95m\033[1m")
    print("=" * 60)
    print(f"{'TCP SMDR Server - Standalone':^60}")
    print("=" * 60)
    print("\033[0m")

    server = TCPSMDRServer(TCP_PORT)
    server.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\033[93mArresto server...\033[0m")
        server.stop()