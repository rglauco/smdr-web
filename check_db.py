#!/usr/bin/env python3
"""
Script per verificare il contenuto del database SMDR
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection


def main():
    print("=" * 80)
    print("DATABASE SMDR - VERIFICA CONTESSO")
    print("=" * 80)
    print()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Totali
        print("1. STATISTICHE GENERALI")
        print("-" * 80)

        cursor.execute('SELECT COUNT(*) as total FROM smdr_calls')
        total = cursor.fetchone()['total']
        print(f"   Totali chiamate nel database: {total}")

        if total > 0:
            # Da ipotesi dei minuti
            cursor.execute('SELECT SUM(connected_time) as total_duration FROM smdr_calls')
            durata = cursor.fetchone()['total_duration'] or 0
            ore = durata / 3600
            print(f"   Durata totale connessione: {durata} secondi ({ore:.2f} ore)")

            cursor.execute('SELECT SUM(ring_time) as total_ring FROM smdr_calls')
            ring = cursor.fetchone()['total_ring'] or 0
            minuti = ring / 60
            print(f"   Tempo totale anello (ring): {ring} secondi ({minuti:.2f} minuti)")

            cursor.execute('SELECT COUNT(DISTINCT call_direction) as dir_count FROM smdr_calls')
            dir_count = cursor.fetchone()['dir_count']
            directions = []
            cursor.execute('SELECT DISTINCT call_direction FROM smdr_calls ORDER BY call_direction')
            for row in cursor.fetchall():
                directions.append(row['call_direction'])
            print(f"   Direzioni trovate: {dir_count} ({', '.join(directions)})")

        print()

        # 2. Last 10 chiamate
        print("2. ULTIME 10 CHIAMATE")
        print("-" * 80)

        cursor.execute('''
            SELECT id, call_start, call_direction, caller, dialed_number, account,
                   connected_time, ring_time
            FROM smdr_calls
            ORDER BY call_start DESC
            LIMIT 10
        ''')

        rows = cursor.fetchall()
        if rows:
            print(f"{'ID':<6} {'DateTime':<20} {'Dir':<10} {'Caller':<15} {'Number':<15} {'Acc':<10} {'Conn':<10} {'Ring':<10}")
            print("-" * 100)
            for row in rows:
                dt = row['call_start'].isoformat() if row['call_start'] else 'N/A'
                print(f"{row['id']:<6} {dt:<20} {row['call_direction']:<10} {str(row['caller'] or '-'):<15} {str(row['dialed_number'] or '-'):<15} {str(row['account'] or '-'):<10} {row['connected_time']:<10} {row['ring_time']:<10}")
        else:
            print("   Nessuna chiamata trovata nel database!")
        print()

        # 3. Chiamate per direzione
        if total > 0:
            print("3. CHIAMATE PER DIREZIONE")
            print("-" * 80)

            cursor.execute('''
                SELECT call_direction, COUNT(*) as count, SUM(ring_time) as total_ring, SUM(connected_time) as total_conn
                FROM smdr_calls
                GROUP BY call_direction
                ORDER BY count DESC
            ''')

            for row in cursor.fetchall():
                print(f"   {row['call_direction']:<10} {row['count']:>6} chiamate   "
                      f"Ring: {row['total_ring']/60:>6.2f} min   Conn: {row['total_conn']/3600:>6.2f} ore")

        print()

        # 4. Top 5 account
        if total > 0:
            print("4. TOP 5 ACCOUNT")
            print("-" * 80)

            cursor.execute('''
                SELECT account, COUNT(*) as count, SUM(connected_time) as total
                FROM smdr_calls
                WHERE account IS NOT NULL AND account != ''
                GROUP BY account
                ORDER BY count DESC
                LIMIT 5
            ''')

            for row in cursor.fetchall():
                print(f"   {row['account']:<15} {row['count']:>3} chiamate   "
                      f"Durata: {row['total']/60:>6.2f} min")

        print()

        # 5. Top chiamanti
        if total > 0:
            print("5. TOP 5 CHIAMANTI")
            print("-" * 80)

            cursor.execute('''
                SELECT caller, COUNT(*) as count, SUM(ring_time) as total_ring
                FROM smdr_calls
                WHERE caller IS NOT NULL AND caller != ''
                GROUP BY caller
                ORDER BY count DESC
                LIMIT 5
            ''')

            for row in cursor.fetchall():
                print(f"   {row['caller']:<15} {row['count']:>3} chiamate   "
                      f"Ring: {row['total_ring']/60:>6.2f} min")

        print()

    except Exception as e:
        print(f"ERRORE: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if conn:
            conn.close()

    print("=" * 80)
    print("FINE VERIFICA")
    print("=" * 80)


if __name__ == '__main__':
    main()