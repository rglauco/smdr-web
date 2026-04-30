"""Database module for SMDR application using SQLite3"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'smdr.db')


def get_db_connection():
    """Create a database connection"""
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize the database with tables"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create smdr_calls table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS smdr_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_start TIMESTAMP NOT NULL,
            connected_time INTEGER NOT NULL,
            ring_time REAL NOT NULL,
            caller TEXT,
            call_direction TEXT NOT NULL,
            dialed_number TEXT,
            account TEXT,
            is_internal TEXT,
            call_id TEXT,
            continuation TEXT,
            party1_device TEXT,
            party1_name TEXT,
            party2_device TEXT,
            party2_name TEXT,
            hold_time REAL,
            park_time REAL,
            auth_valid TEXT,
            auth_code TEXT,
            user_charged TEXT,
            call_charge REAL,
            currency TEXT,
            account_last_change TEXT,
            call_units REAL,
            units_last_change REAL,
            cost_per_unit REAL,
            markup REAL,
            external_targeting_cause TEXT,
            external_targeter_id TEXT,
            external_targeted_number TEXT,
            raw_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create indexes for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_call_start ON smdr_calls(call_start)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_call_direction ON smdr_calls(call_direction)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_dialed_number ON smdr_calls(dialed_number)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_caller ON smdr_calls(caller)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_account ON smdr_calls(account)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_period ON smdr_calls(
            strftime('%Y-%m', call_start)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def add_smdr_record(record_data, raw_data=None):
    """
    Add an SMDR record to the database

    Args:
        record_data: dict with the SMDR record fields
        raw_data: original raw CSV data
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO smdr_calls (
                call_start, connected_time, ring_time, caller, call_direction,
                dialed_number, account, is_internal, call_id, continuation,
                party1_device, party1_name, party2_device, party2_name,
                hold_time, park_time, auth_valid, auth_code, user_charged,
                call_charge, currency, account_last_change, call_units,
                units_last_change, cost_per_unit, markup,
                external_targeting_cause, external_targeter_id,
                external_targeted_number, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record_data.get('call_start'),
            record_data.get('connected_time'),
            record_data.get('ring_time'),
            record_data.get('caller'),
            record_data.get('call_direction'),
            record_data.get('dialed_number'),
            record_data.get('account'),
            record_data.get('is_internal'),
            record_data.get('call_id'),
            record_data.get('continuation'),
            record_data.get('party1_device'),
            record_data.get('party1_name'),
            record_data.get('party2_device'),
            record_data.get('party2_name'),
            record_data.get('hold_time'),
            record_data.get('park_time'),
            record_data.get('auth_valid'),
            record_data.get('auth_code'),
            record_data.get('user_charged'),
            record_data.get('call_charge'),
            record_data.get('currency'),
            record_data.get('account_last_change'),
            record_data.get('call_units'),
            record_data.get('units_last_change'),
            record_data.get('cost_per_unit'),
            record_data.get('markup'),
            record_data.get('external_targeting_cause'),
            record_data.get('external_targeter_id'),
            record_data.get('external_targeted_number'),
            raw_data
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def count_calls():
    """Return total number of calls"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as total FROM smdr_calls')
    result = cursor.fetchone()
    conn.close()
    return result['total']


def get_calls(filters=None, limit=100, offset=0):
    """
    Retrieve calls with optional filters

    Args:
        filters: dict with filter criteria (call_direction, start_date, end_date, etc.)
        limit: maximum number of records to return
        offset: number of records to skip

    Returns:
        list of smdr_calls rows
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = 'SELECT * FROM smdr_calls WHERE 1=1'
    params = []

    if filters:
        if filters.get('call_direction'):
            query += ' AND call_direction = ?'
            params.append(filters['call_direction'])
        if filters.get('start_date'):
            query += ' AND datetime(call_start) >= datetime(?)'
            params.append(filters['start_date'])
        if filters.get('end_date'):
            query += ' AND datetime(call_start) <= datetime(?)'
            params.append(filters['end_date'])
        if filters.get('dialed_number'):
            query += ' AND dialed_number LIKE ?'
            params.append(f'%{filters["dialed_number"]}%')
        if filters.get('caller'):
            query += ' AND caller LIKE ?'
            params.append(f'%{filters["caller"]}%')
        if filters.get('account'):
            query += ' AND account LIKE ?'
            params.append(f'%{filters["account"]}%')
        if filters.get('is_internal'):
            query += ' AND is_internal = ?'
            params.append(filters['is_internal'])

    query += ' ORDER BY call_start DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_call_stats(filters=None):
    """
    Get call statistics (FIXED VERSION)

    Args:
        filters: dict with filter criteria

    Returns:
        dict with statistics
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    stats = {}

    # Build base query and parameters correctly
    base_query_parts = []
    params = []
    if filters:
        for k, v in filters.items():
            if v and v != '':
                base_query_parts.append(f'{k} = ?')
                params.append(v)

    if base_query_parts:
        base_query = 'WHERE ' + ' AND '.join(base_query_parts)
    else:
        base_query = ''

    # Basic counts
    query = f'SELECT COUNT(*) as total FROM smdr_calls {base_query}'
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query, [])
    stats['total_calls'] = cursor.fetchone()['total']

    # Calls by direction
    query = f'SELECT call_direction, COUNT(*) as count FROM smdr_calls {base_query} GROUP BY call_direction'
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query, [])
    stats['by_direction'] = {str(row['call_direction'] or 'Unknown'): row['count'] for row in cursor.fetchall()}

    # Calls by internal status
    query = f'SELECT is_internal, COUNT(*) as count FROM smdr_calls {base_query} GROUP BY is_internal'
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query, [])
    stats['by_internal'] = {str(row['is_internal'] or 'Unknown'): row['count'] for row in cursor.fetchall()}

    # Calls by account
    query = f'SELECT account, COUNT(*) as count FROM smdr_calls {base_query} GROUP BY account ORDER BY count DESC LIMIT 10'
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query, [])
    stats['top_accounts'] = [{"account": row['account'] or 'Unknown', "count": row['count']} for row in cursor.fetchall() if row['account']]

    # Calls by caller
    query = f'SELECT caller, COUNT(*) as count FROM smdr_calls {base_query} GROUP BY caller ORDER BY count DESC LIMIT 10'
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query, [])
    stats['top_callers'] = [{"caller": row['caller'] or 'Unknown', "count": row['count']} for row in cursor.fetchall() if row['caller']]

    # Total duration (connected time)
    query = f'SELECT SUM(connected_time) as total_duration FROM smdr_calls {base_query}'
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query, [])
    result = cursor.fetchone()
    stats['total_connected_seconds'] = result['total_duration'] or 0
    stats['total_duration_hours'] = round(result['total_duration'] / 3600 if result['total_duration'] else 0, 2)

    # Total ring time
    query = f'SELECT SUM(ring_time) as total_ring FROM smdr_calls {base_query}'
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query, [])
    result = cursor.fetchone()
    stats['total_ring_minutes'] = round(result['total_ring'] / 60 if result['total_ring'] else 0, 2)

    # Calls by month
    query = f'SELECT strftime("%Y-%m", call_start) as month, COUNT(*) as count FROM smdr_calls {base_query} GROUP BY month ORDER BY month DESC LIMIT 12'
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query, [])
    stats['by_month'] = [{"month": row['month'] or 'Unknown', "count": row['count']} for row in cursor.fetchall() if row['month']]

    # Top dialed numbers
    query = f'SELECT dialed_number, COUNT(*) as count FROM smdr_calls {base_query} GROUP BY dialed_number ORDER BY count DESC LIMIT 10'
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query, [])
    stats['top_dialed'] = [{"dialed_number": row['dialed_number'] or 'Unknown', "count": row['count']} for row in cursor.fetchall() if row['dialed_number']]

    conn.close()
    return stats


def get_calls_by_date_period(year=None, month=None, day=None):
    """
    Get calls for a specific date period
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if year:
        if month:
            if day:
                query = 'SELECT * FROM smdr_calls WHERE strftime("%Y-%m-%d", call_start) = ? ORDER BY call_start DESC'
                cursor.execute(query, (f'{year:04d}-{month:02d}-{day:02d}',))
            else:
                query = 'SELECT * FROM smdr_calls WHERE strftime("%Y-%m", call_start) = ? ORDER BY call_start DESC'
                cursor.execute(query, (f'{year:04d}-{month:02d}',))
        else:
            query = 'SELECT * FROM smdr_calls WHERE strftime("%Y", call_start) = ? ORDER BY call_start DESC'
            cursor.execute(query, (f'{year:04d}',))
    else:
        query = 'SELECT * FROM smdr_calls ORDER BY call_start DESC LIMIT 100'
        cursor.execute(query)

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_call_by_id(call_id):
    """Get a single call by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM smdr_calls WHERE id = ?', (call_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def update_smdr_record(call_id, updates):
    """Update an SMDR record"""
    conn = get_db_connection()
    cursor = conn.cursor()

    set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
    params = list(updates.values()) + [call_id]

    cursor.execute(f'UPDATE smdr_calls SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', params)
    conn.commit()
    conn.close()
    return cursor.rowcount > 0