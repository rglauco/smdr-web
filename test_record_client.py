#!/usr/bin/env python3
"""
Test client che invia un singolo record SMDR nella FORMA ORIGINALE C#
Requisiti: il record deve essere su UNA SOLA LINEA da 30+ campi separati da virgola
"""

import socket
import json


# UN SOLO RECORD SMDR COMPLETO - FORMATO ORIGINALE (30 campi + più dettagli)
# Genereato secondo il pattern C# SMDR_Server.cs

VALID_SMDR_RECORD_COMPLETE = (
    "28/04/2026 16:34:56,00:02:35,12.5,12345,I,+39 0123456789,ACCT001,Y,"
    "123456789,,DTMF,Marco Rossi,UO1,Beatrice Rossi,UO2,35.0,0,Y,CODE123,user,15.50,EUR,"
    "ACCT001,,15.50,0.052,,EUR,24,123,Call Name,123456,0"
)

# RECORD CHE DOVEVA ESSERE SPERSO SU PIU' LINEE DALL'CLIENT ANTICO
RECORD_INCOMPLETE = (
    "28/04/2026 16:35:00,00:03:20,18,EXTERNAL,1,"
    "+39 0123456789,ACCT002,Y,CALL_789,,OUTBOUNDED,"
    "External User,,DACT800,External,45.0,0,,,,,TARGET1,,12345,External,,"
    "60.0,0.082,Y,USER2,22.5,EUR,ACCT002,"
    "22.5,0.067,,,EXTERNAL,,12345,Call_External,0,0,0"
)


def send_smdr_record(sock, record_data, record_type=""):
    """Send SMDR record to server"""
    record = record_data.strip()
    num_parts = len(record.split(','))

    print(f"\n{'='*70}")
    print(f"RECORD {record_type}")
    print(f"{'='*70}")
    print(f"Numero parti: {num_parts}")
    print(f"Contenuto: {record}")
    print(f"{'='*70}\n")

    try:
        # Invia con newline finale (questo è importante!)
        message = record + "\n"
        print(f"Inviando {len(message)} bytes...")
        sock.sendall(message.encode('utf-8'))

        # Attendiamo 1 secondo per dare al server tempo di processare
        import time
        time.sleep(1.0)

        print("✓ Inviato con successo!")
        return True
    except Exception as e:
        print(f"✗ Errore invio: {e}")
        return False


def test_server(host='localhost', port=3000):
    """Test SMDR Server sending complete records"""

    print("=" * 70)
    print("Client Test per SMDR Server")
    print("=" * 70)
    print(f"Target: {host}:{port}")
    print("=" * 70)

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)

        print("\nConnessione al server...")
        sock.connect((host, port))
        print("✓ Connesso con successo!\n")

        # Test 1: Record completo con 32 parti (COMPLETAMENTE VALIDO)
        print("\n" + "="*70)
        print("TEST 1: Record completo (32 parti)")
        print("="*70)
        send_smdr_record(sock, VALID_SMDR_RECORD_COMPLETE, "CAPOLUOGO")

        # Test 2: Altro record completo
        print("\n" + "="*70)
        print("TEST 2: Record completo (32 parti)")
        print("="*70)
        send_smdr_record(sock, RECORD_INCOMPLETE, "SECONDARIA")

        # Attendi che il server processi
        import time
        time.sleep(3)

        print("\n" + "="*70)
        print("Test completato!")
        print("Controlla:")
        print("  - Terminal con Python Server (dovrebbe mostrare log)")
        print("  - Web UI http://localhost:5000 (dovrebbe mostrare 2 chiamate)")
        print("  - Database con 'sqlite3': SELECT * FROM smdr_calls LIMIT 5;")
        print("="*70)

        # Teste anche tramite server Python per leggere il DB
        print("\nManuale verifica:")
        print("1. Finestra 1: python run.py")
        print("2. Finestra 2: python test_server.py")
        print("3. Vedere che i log mostrano 'SALVATO IN DB'")
        print("4. http://localhost:5000 per vedere i risultati")

    except socket.timeout:
        print("\n✗ Connessione scaduta")
    except ConnectionRefusedError:
        print("\n✗ Connessione rifiutata. Il server non è in esecuzione su " + host)
        print("Avvia il server con: python run.py")
    except Exception as e:
        print(f"\n✗ Errore: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if sock:
            sock.close()
        print("\nConnessione chiusa")


if __name__ == '__main__':
    import sys

    # Usa il file di configurazione per parametri
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 3000

    print(f"Usage: python test_record_client.py [host] [port]")
    print()

    test_server(host, port)