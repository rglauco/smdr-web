"""
Helper script to view SMDR database contents
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection

def show_calls(limit=10):
    """Display recent calls from database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM smdr_calls ORDER BY call_start DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()

    print("=" * 120)
    print(f"ULTIME {limit} CHIAMATE DAL DATABASE")
    print("=" * 120)
    print(f"{'ID':<5} {'Data Inizio':<20} {'Direzione':<10} {'Chiamante':<20} {'Numero':<20} {'Account':<20}")
    print("-" * 120)

    for row in rows:
        call_start = row['call_start'].isoformat() if row['call_start'] else ''
        direction = row['call_direction'] or ''
        caller = row['caller'] or 'Unknown'
        dialed = row['dialed_number'] or 'Unknown'
        account = row['account'] or '-'

        print(f"{row['id']:<5} {call_start:<20} {direction:<10} {caller:<20} {dialed:<20} {account:<20}")

    print("-" * 120)
    print(f"Totale chiamate nel database: {row['total'] if hasattr(row, 'total') else 'N/A' if len(rows) == 0 else rows[-1]['id']}")

    conn.close()


def show_statistics():
    """Show statistics from database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total calls
    cursor.execute('SELECT COUNT(*) as total FROM smdr_calls')
    total = cursor.fetchone()['total']

    # Calls by direction
    cursor.execute('SELECT call_direction, COUNT(*) as count FROM smdr_calls GROUP BY call_direction ORDER BY count DESC')
    by_direction = {row['call_direction']: row['count'] for row in cursor.fetchall()}

    # Calls by account
    cursor.execute('SELECT account, COUNT(*) as count FROM smdr_calls GROUP BY account ORDER BY count DESC LIMIT 5')
    top_accounts = cursor.fetchall()

    print("\n" + "=" * 80)
    print("Statistiche dal Database")
    print("=" * 80)
    print(f"Totale chiamate: {total}")
    print("\nChiamate per direzione:")
    for direction, count in by_direction.items():
        print(f"  • {direction}: {count}")
    print("\nTop 5 account:")
    for row in top_accounts:
        print(f"  • {row['account'] or 'N/A'}: {row['count']} chiamate")

    conn.close()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == 'stats':
            show_statistics()
        else:
            show_calls(int(arg))
    else:
        show_calls(10)