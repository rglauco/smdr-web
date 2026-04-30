#!/usr/bin/env python3
"""
Client per testare il TCP SMDR Server
Invia record SMDR di esempio alla porta 3000
"""

import socket
import time
from datetime import datetime


def send_smdr_record(sock, record):
    """Send SMDR record to server"""
    message = record.strip()
    try:
        sock.sendall(message.encode('utf-8'))
        print(f"✓ Inviato: {message[:80]}{'...' if len(message) > 80 else ''}")
        time.sleep(0.1)  # Small delay between records
        return True
    except Exception as e:
        print(f"✗ Errore invio: {e}")
        return False


def test_smdr_server(host='localhost', port=3000, num_records=5):
    """Test TCP SMDR Server with example records"""

    print("=" * 70)
    print("TCP SMDR Server Client Test")
    print("=" * 70)
    print(f"Target: {host}:{port}")
    print(f"Records to send: {num_records}")
    print("=" * 70)

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)

        print("\nConnessione al server...")
        sock.connect((host, port))
        print("✓ Connesso con successo!\n")

        # Inward call example
        inward_call = "28/04/2026 12:34:56,00:01:45,8,EXTERNAL,1,+39 0123456789,CLIENT1,Y,CALL123,,,"
        inward_call += "OUTBOUNDED,External User,,DACT800,External,30.0,0,,,,,,,,,,,,"

        # Outward call with repetition (like C# service building multi-line records)
        outward_call = "28/04/2026 12:35:00,00:03:20,15,INTERNAL,1,+39 0123456789,CLIENT2,Y,CALL456,,,"
        outward_call += "INTERNAL,Internal User,Alice,DACT800,,50.0,0,,,,,,MARKUP1,,12345,External,,,"

        print("Invio record SMDR...")
        print("-" * 70)

        # Send multiple test records
        for i in range(num_records):
            if i == 0:
                record = inward_call
                direction = "Inbound"
            else:
                record = outward_call
                direction = "Outbound"

            send_smdr_record(sock, record)

            # After first record, wait to see if server logs it
            if i == 0:
                time.sleep(1.0)

        print("-" * 70)
        print("\n✓ Test completato con successo!")
        print("Verifica i log del server e l'interfaccia web http://localhost:5000")

    except socket.timeout:
        print("\n✗ Connessione scaduta")
    except ConnectionRefusedError:
        print("\n✗ Connessione rifiutata. Il server non è in esecuzione?")
    except Exception as e:
        print(f"\n✗ Errore: {e}")
    finally:
        if sock:
            sock.close()
        print("\nConnessione chiusa (timeout automatico)")


if __name__ == '__main__':
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    num_records = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    print(f"Usage: python client_test.py [host] [port] [num_records]\n")

    test_smdr_server(host, port, num_records)