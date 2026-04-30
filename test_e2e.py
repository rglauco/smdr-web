#!/usr/bin/env python3
"""
Test end-to-end: invia un record SMDR e verifica che finisca nel DB
"""
import socket
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TCP_HOST = 'localhost'
TCP_PORT = 3000

# Record SMDR con ESATTAMENTE 30 campi (come dal C#)
# Formato: CallStart,ConnectedTime,RingTime,Caller,Direction,CalledNumber,DialedNumber,Account,IsInternal,CallID,Continuation,Party1Device,Party1Name,Party2Device,Party2Name,HoldTime,ParkTime,AuthValid,AuthCode,UserCharged,CallCharge,Currency,AccountLastChange,CallUnits,UnitsLastChange,CostPerUnit,Markup,ExternalTargetingCause,ExternalTargeterId,ExternalTargetedNumber
RECORD_30_FIELDS = "28/04/2026 16:34:56,00:02:35,12,12345,I,+390123456789,ACCT001,Y,123456789,,Ext101,Marco Rossi,Ext102,Beatrice Rossi,35,0,Y,CODE123,user1,15.50,EUR,ACCT001,15.50,0.052,24,123,ExternalTarget,Targeter1,Targeted1"


def send_record(host, port, record_str):
    """Invia un record SMDR al server TCP"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        print(f"Connessione a {host}:{port}...")
        sock.connect((host, port))
        print("✓ Connesso!")

        # Importante: inviare con \n finale (come i PBX inviano tipicamente)
        message = record_str + "\n"
        print(f"Invio {len(message)} bytes ({len(record_str.split(','))} campi)...")
        sock.sendall(message.encode('ascii'))

        # Attendi un po' per dare tempo al server di processare
        time.sleep(1)
        print("✓ Record inviato!")
        return True
    except ConnectionRefusedError:
        print(f"✗ Connessione rifiutata su {host}:{port}")
        print("  Il server TCP è in esecuzione?")
        return False
    except Exception as e:
        print(f"✗ Errore: {e}")
        return False
    finally:
        sock.close()


def check_database():
    """Verifica che il record sia stato salvato nel DB"""
    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as total FROM smdr_calls')
    total = cursor.fetchone()['total']
    print(f"\nRecord nel database: {total}")

    if total > 0:
        cursor.execute('SELECT * FROM smdr_calls ORDER BY id DESC LIMIT 3')
        rows = cursor.fetchall()
        for row in rows:
            print(f"  ID={row['id']} | {row['call_start']} | {row['call_direction']} | "
                  f"{row['caller']} -> {row['dialed_number']} | conn={row['connected_time']}s | "
                  f"ring={row['ring_time']}s")
    conn.close()
    return total


def main():
    print("=" * 70)
    print("TEST END-TO-END SMDR")
    print("=" * 70)

    host = sys.argv[1] if len(sys.argv) > 1 else TCP_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else TCP_PORT

    # Record con 30 campi
    n_fields = len(RECORD_30_FIELDS.split(','))
    print(f"\nRecord di test: {n_fields} campi (attesi: 30)")
    print(f"Contenuto: {RECORD_30_FIELDS[:100]}...")
    print()

    success = send_record(host, port, RECORD_30_FIELDS)

    if success:
        print("\nAttendi 2 secondi per il salvataggio...")
        time.sleep(2)

        total = check_database()
        if total > 0:
            print(f"\n✅ SUCCESSO! {total} record nel database")
        else:
            print("\n❌ ERRORE: Nessun record trovato nel database!")
            print("   Controlla i log del server per errori")

    print("\n" + "=" * 70)
    print("Fine test")
    print("=" * 70)


if __name__ == '__main__':
    main()