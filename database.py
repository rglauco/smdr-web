"""Database module for SMDR application using SQLite3"""
import sqlite3
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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

    # Create settings table for app configuration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    # Insert default timezone if not exists
    cursor.execute('''
        INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)
    ''', ('timezone', 'Europe/Rome'))

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


def _build_where_clause(filters):
    """Build a WHERE clause and params list from a filters dict.

    Supported filter keys:
      call_direction   → exact match
      is_internal      → exact match
      start_date       → call_start >= (inclusive)
      end_date         → call_start <= (inclusive, end of day)
      dialed_number    → LIKE match
      caller           → LIKE match
      account          → LIKE match
    """
    parts = []
    params = []

    if filters:
        if filters.get('call_direction'):
            parts.append('call_direction = ?')
            params.append(filters['call_direction'])
        if filters.get('is_internal'):
            parts.append('is_internal = ?')
            params.append(filters['is_internal'])
        if filters.get('start_date'):
            parts.append('datetime(call_start) >= datetime(?)')
            params.append(filters['start_date'])
        if filters.get('end_date'):
            parts.append('datetime(call_start) <= datetime(?)')
            params.append(filters['end_date'])
        if filters.get('dialed_number'):
            parts.append('dialed_number LIKE ?')
            params.append(f'%{filters["dialed_number"]}%')
        if filters.get('caller'):
            parts.append('caller LIKE ?')
            params.append(f'%{filters["caller"]}%')
        if filters.get('account'):
            parts.append('account LIKE ?')
            params.append(f'%{filters["account"]}%')

    where = ('WHERE ' + ' AND '.join(parts)) if parts else ''
    return where, params


def get_call_stats(filters=None):
    """
    Get call statistics with optional date/time filters.

    Args:
        filters: dict with filter criteria. Supports:
            start_date, end_date, call_direction, is_internal,
            dialed_number, caller, account

    Returns:
        dict with statistics including period-specific groupings
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    stats = {}
    where, params = _build_where_clause(filters)

    # Helper to execute a query with or without params
    def run(q, p=None):
        cursor.execute(q, p if p else [])
        return cursor.fetchall()

    # ── Basic counts ─────────────────────────────────────────
    row = run(f'SELECT COUNT(*) as total FROM smdr_calls {where}', params or None)
    stats['total_calls'] = row[0]['total']

    # Calls by direction
    rows = run(f'SELECT call_direction, COUNT(*) as count FROM smdr_calls {where} GROUP BY call_direction', params or None)
    stats['by_direction'] = {str(r['call_direction'] or 'Unknown'): r['count'] for r in rows}

    # Calls by internal status
    rows = run(f'SELECT is_internal, COUNT(*) as count FROM smdr_calls {where} GROUP BY is_internal', params or None)
    stats['by_internal'] = {str(r['is_internal'] or 'Unknown'): r['count'] for r in rows}

    # ── Top accounts (date-filtered) ──────────────────────────
    rows = run(f'SELECT account, COUNT(*) as count FROM smdr_calls {where} GROUP BY account ORDER BY count DESC LIMIT 10', params or None)
    stats['top_accounts'] = [{"account": r['account'] or 'Unknown', "count": r['count']} for r in rows if r['account']]

    # ── Top callers (date-filtered) ──────────────────────────
    rows = run(f'SELECT caller, COUNT(*) as count FROM smdr_calls {where} GROUP BY caller ORDER BY count DESC LIMIT 10', params or None)
    stats['top_callers'] = [{"caller": r['caller'] or 'Unknown', "count": r['count']} for r in rows if r['caller']]

    # ── Duration totals ──────────────────────────────────────
    row = run(f'SELECT SUM(connected_time) as total_duration FROM smdr_calls {where}', params or None)
    result = row[0]
    stats['total_connected_seconds'] = result['total_duration'] or 0
    stats['total_duration_hours'] = round(result['total_duration'] / 3600 if result['total_duration'] else 0, 2)

    row = run(f'SELECT SUM(ring_time) as total_ring FROM smdr_calls {where}', params or None)
    result = row[0]
    stats['total_ring_minutes'] = round(result['total_ring'] / 60 if result['total_ring'] else 0, 2)

    # ── Top dialed numbers (date-filtered) ───────────────────
    rows = run(f'SELECT dialed_number, COUNT(*) as count FROM smdr_calls {where} GROUP BY dialed_number ORDER BY count DESC LIMIT 10', params or None)
    stats['top_dialed'] = [{"dialed_number": r['dialed_number'] or 'Unknown', "count": r['count']} for r in rows if r['dialed_number']]

    # ── Period grouping: by_day, by_week, by_month ───────────
    # By day (last 60 days max)
    rows = run(f"""SELECT strftime('%Y-%m-%d', call_start) as day, COUNT(*) as count
                   FROM smdr_calls {where}
                   GROUP BY day ORDER BY day DESC LIMIT 60""", params or None)
    stats['by_day'] = [{"day": r['day'], "count": r['count']} for r in rows if r['day']]

    # By week (ISO week)
    rows = run(f"""SELECT strftime('%Y-W%W', call_start) as week, COUNT(*) as count
                   FROM smdr_calls {where}
                   GROUP BY week ORDER BY week DESC LIMIT 24""", params or None)
    stats['by_week'] = [{"week": r['week'], "count": r['count']} for r in rows if r['week']]

    # By month (last 24 months)
    rows = run(f"""SELECT strftime('%Y-%m', call_start) as month, COUNT(*) as count
                   FROM smdr_calls {where}
                   GROUP BY month ORDER BY month DESC LIMIT 24""", params or None)
    stats['by_month'] = [{"month": r['month'], "count": r['count']} for r in rows if r['month']]

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


def get_hourly_stats(start_date=None, end_date=None):
    """
    Get hourly call distribution for a given date range.

    Args:
        start_date: optional start date string (YYYY-MM-DD HH:MM:SS)
        end_date: optional end date string (YYYY-MM-DD HH:MM:SS)

    Returns:
        dict with 'hours' key containing list of {hour, count} for hours 0-23
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT strftime("%H", call_start) as hour,
               COUNT(*) as count
        FROM smdr_calls
        WHERE 1=1
    '''
    params = []

    if start_date:
        query += ' AND datetime(call_start) >= datetime(?)'
        params.append(start_date)
    if end_date:
        query += ' AND datetime(call_start) <= datetime(?)'
        params.append(end_date)

    query += ' GROUP BY hour ORDER BY hour ASC'

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    # Build full 0-23 hour array
    hourly_data = {str(h).zfill(2): 0 for h in range(24)}
    for row in rows:
        hourly_data[row['hour']] = row['count']

    return {
        'hours': [{'hour': h, 'count': hourly_data[h]} for h in sorted(hourly_data.keys())]
    }


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


# ── Settings helpers ──────────────────────────────────────────

def get_setting(key, default=None):
    """Get a setting value from app_settings table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM app_settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row['value']
    return default


def set_setting(key, value):
    """Set a setting value in app_settings table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO app_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    ''', (key, value))
    conn.commit()
    conn.close()
    return value


def get_app_timezone():
    """Get the configured application timezone as a ZoneInfo object."""
    tz_name = get_setting('timezone', 'Europe/Rome')
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo('Europe/Rome')


def localize_timestamp(dt_str, tz=None):
    """
    Convert a naive timestamp string to the configured timezone.
    
    Assumes the stored timestamp is a naive datetime in the configured timezone.
    Returns the timestamp with UTC offset appended (ISO 8601 format).
    This allows the frontend to correctly interpret and display the time.
    
    DST is handled automatically via the ZoneInfo database.
    """
    if not dt_str:
        return dt_str
    
    if tz is None:
        tz = get_app_timezone()
    
    # Parse the stored timestamp
    # Handle both '2024-05-07T14:30:00' and '2024-05-07 14:30:00' formats
    ts = dt_str.strip()
    
    # If already timezone-aware (ends with +XX:XX or Z), return as-is
    if ts.endswith('Z') or (len(ts) > 5 and ts[-6] in ('+', '-') and ts[-3] == ':'):
        return ts
    
    try:
        if 'T' in ts:
            dt_naive = datetime.fromisoformat(ts)
        else:
            # Try common formats
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M:%S'):
                try:
                    dt_naive = datetime.strptime(ts, fmt)
                    break
                except ValueError:
                    continue
            else:
                # Last resort
                dt_naive = datetime.fromisoformat(ts)
        
        # Localize the naive datetime to the configured timezone
        # This automatically handles DST!
        dt_aware = dt_naive.replace(tzinfo=tz)
        
        # Return as ISO 8601 with UTC offset
        return dt_aware.isoformat()
    except Exception:
        # If parsing fails, return original string
        return dt_str


def get_tz_info():
    """
    Get timezone info for the frontend: name, UTC offset, DST status.
    Returns dict with timezone details.
    """
    tz = get_app_timezone()
    tz_name = get_setting('timezone', 'Europe/Rome')
    now = datetime.now(tz)
    
    # Get UTC offset
    utc_offset = now.strftime('%z')  # e.g. '+0200'
    # Format as '+02:00'
    offset_hours = utc_offset[:-2]
    offset_minutes = utc_offset[-2:]
    offset_formatted = f'{offset_hours[:3]}:{offset_minutes}'
    if len(offset_hours) == 3:  # +02 => +02:00
        offset_formatted = f'+0{offset_hours[1:]}:{offset_minutes}'
    formatted_offset = f'{utc_offset[:3]}:{utc_offset[3:]}'
    
    # Check if DST is active
    dst_active = bool(now.dst())
    
    return {
        'timezone': tz_name,
        'utc_offset': formatted_offset,
        'utc_offset_minutes': int(now.utcoffset().total_seconds() / 60),
        'dst_active': dst_active,
        'current_time': now.isoformat(),
    }