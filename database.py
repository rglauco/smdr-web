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

    # Insert default settings if not exists
    cursor.execute('''
        INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)
    ''', ('timezone', 'Europe/Rome'))
    # timestamp_mode: 'utc' means stored timestamps are UTC,
    #                 'local' means stored timestamps are in the configured timezone
    cursor.execute('''
        INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)
    ''', ('timestamp_mode', 'utc'))

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

    # ── Operational KPIs: answer rate, ACD, ASA, Service Level ─
    sl_threshold = 20  # seconds — industry default for Service Level
    row = run(f"""
        SELECT
            SUM(CASE WHEN connected_time > 0 THEN 1 ELSE 0 END) AS answered,
            SUM(CASE WHEN connected_time = 0 THEN 1 ELSE 0 END) AS abandoned,
            AVG(CASE WHEN connected_time > 0 THEN connected_time END) AS acd,
            AVG(CASE WHEN connected_time > 0 THEN ring_time END) AS asa,
            SUM(CASE WHEN connected_time > 0 AND ring_time <= {sl_threshold} THEN 1 ELSE 0 END) AS answered_in_sl
        FROM smdr_calls {where}
    """, params or None)
    result = row[0]
    total = stats['total_calls']
    answered = result['answered'] or 0
    abandoned = result['abandoned'] or 0
    answered_in_sl = result['answered_in_sl'] or 0
    stats['answered'] = answered
    stats['abandoned'] = abandoned
    stats['answer_rate'] = round(answered / total, 4) if total else 0
    stats['abandonment_rate'] = round(abandoned / total, 4) if total else 0
    stats['acd_seconds'] = round(result['acd'] or 0, 1)
    stats['asa_seconds'] = round(result['asa'] or 0, 1)
    stats['service_level'] = round(answered_in_sl / answered, 4) if answered else 0
    stats['service_level_threshold_seconds'] = sl_threshold

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


# ── Italian-aware number classification ──────────────────────
# Uses GLOB (case-sensitive) on string columns. Order matters: more
# specific patterns first. Falls through to 'Altro' for anything unmatched.
_NUMBER_CLASSIFICATION = """
    CASE
        WHEN {col} IS NULL OR {col} = '' THEN 'Sconosciuto'
        WHEN length({col}) <= 4 THEN 'Interno'
        WHEN {col} GLOB '11[0-9]' THEN 'Servizio'
        WHEN {col} GLOB '+*' OR {col} GLOB '00*' THEN 'Internazionale'
        WHEN {col} GLOB '800*' OR {col} GLOB '803*' THEN 'Verde'
        WHEN {col} GLOB '199*' OR {col} GLOB '899*' OR {col} GLOB '144*' OR {col} GLOB '166*' OR {col} GLOB '892*' THEN 'Premium'
        WHEN {col} GLOB '03[3-9]*' AND length({col}) BETWEEN 10 AND 12 THEN 'Mobile'
        WHEN {col} GLOB '3[3-9]*' AND length({col}) BETWEEN 9 AND 11 THEN 'Mobile'
        WHEN {col} GLOB '0*' THEN 'Fisso'
        ELSE 'Altro'
    END
"""


def get_number_categories(filters=None, field='dialed_number'):
    """
    Categorize numbers (Italian-aware) and return counts + answered + total seconds.
    field: 'dialed_number' (default) or 'caller'.
    """
    if field not in ('dialed_number', 'caller'):
        field = 'dialed_number'

    where, params = _build_where_clause(filters)
    classification = _NUMBER_CLASSIFICATION.format(col=field)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT
            {classification} AS category,
            COUNT(*) AS count,
            SUM(CASE WHEN connected_time > 0 THEN 1 ELSE 0 END) AS answered,
            SUM(connected_time) AS total_seconds
        FROM smdr_calls {where}
        GROUP BY category
        ORDER BY count DESC
    """, params or [])
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'category': r['category'],
            'count': r['count'],
            'answered': r['answered'] or 0,
            'total_seconds': r['total_seconds'] or 0,
        }
        for r in rows
    ]


def get_duration_histogram(filters=None):
    """Return bucketed distribution of connected_time."""
    where, params = _build_where_clause(filters)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT
            CASE
                WHEN connected_time = 0 THEN '0_no_answer'
                WHEN connected_time <= 10 THEN '1_0_10s'
                WHEN connected_time <= 30 THEN '2_10_30s'
                WHEN connected_time <= 60 THEN '3_30_60s'
                WHEN connected_time <= 300 THEN '4_1_5m'
                WHEN connected_time <= 900 THEN '5_5_15m'
                WHEN connected_time <= 1800 THEN '6_15_30m'
                ELSE '7_30m_plus'
            END AS bucket,
            COUNT(*) AS count
        FROM smdr_calls {where}
        GROUP BY bucket
    """, params or [])
    rows = cursor.fetchall()
    conn.close()

    LABELS = [
        ('0_no_answer', 'Non risposte'),
        ('1_0_10s', '0-10s'),
        ('2_10_30s', '10-30s'),
        ('3_30_60s', '30-60s'),
        ('4_1_5m', '1-5min'),
        ('5_5_15m', '5-15min'),
        ('6_15_30m', '15-30min'),
        ('7_30m_plus', '>30min'),
    ]
    counts = {key: 0 for key, _ in LABELS}
    for r in rows:
        if r['bucket'] in counts:
            counts[r['bucket']] = r['count']
    return [{'bucket': label, 'count': counts[key]} for key, label in LABELS]


def get_hour_dow_heatmap(filters=None):
    """7×24 heatmap of calls by day-of-week × hour. Monday-first."""
    where, params = _build_where_clause(filters)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT
            CAST(strftime('%w', call_start) AS INTEGER) AS dow,
            CAST(strftime('%H', call_start) AS INTEGER) AS hour,
            COUNT(*) AS count
        FROM smdr_calls {where}
        GROUP BY dow, hour
    """, params or [])
    rows = cursor.fetchall()
    conn.close()

    # SQLite %w: 0=Sunday..6=Saturday. Remap to 0=Monday..6=Sunday.
    grid = [[0] * 24 for _ in range(7)]
    max_count = 0
    for r in rows:
        eu_dow = (r['dow'] + 6) % 7
        grid[eu_dow][r['hour']] = r['count']
        if r['count'] > max_count:
            max_count = r['count']

    return {
        'days': ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'],
        'hours': [f'{h:02d}' for h in range(24)],
        'grid': grid,
        'max': max_count,
    }


def get_dow_breakdown(filters=None):
    """Day-of-week breakdown with per-day answer rate."""
    where, params = _build_where_clause(filters)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT
            CAST(strftime('%w', call_start) AS INTEGER) AS dow,
            COUNT(*) AS total,
            SUM(CASE WHEN connected_time > 0 THEN 1 ELSE 0 END) AS answered
        FROM smdr_calls {where}
        GROUP BY dow
    """, params or [])
    rows = cursor.fetchall()
    conn.close()

    DAYS = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']
    by_dow = [{'day': d, 'total': 0, 'answered': 0, 'answer_rate': 0.0} for d in DAYS]

    for r in rows:
        eu_dow = (r['dow'] + 6) % 7
        total = r['total']
        answered = r['answered'] or 0
        by_dow[eu_dow]['total'] = total
        by_dow[eu_dow]['answered'] = answered
        by_dow[eu_dow]['answer_rate'] = round(answered / total, 4) if total else 0.0

    return by_dow


def get_anomalies(filters=None, lookback_days=60, z_threshold=2.0):
    """
    Detect anomalous days based on z-score of daily call count over the
    last `lookback_days` days within the filter scope. Returns days where
    |z| >= z_threshold.
    """
    where, params = _build_where_clause(filters)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT strftime('%Y-%m-%d', call_start) AS day, COUNT(*) AS count
        FROM smdr_calls {where}
        GROUP BY day
        ORDER BY day DESC
        LIMIT ?
    """, list(params) + [lookback_days])
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 5:
        return {'baseline': None, 'anomalies': [], 'sample_days': len(rows)}

    counts = [r['count'] for r in rows]
    n = len(counts)
    mean = sum(counts) / n
    var = sum((c - mean) ** 2 for c in counts) / n
    stddev = var ** 0.5

    anomalies = []
    if stddev > 0:
        for r in rows:
            z = (r['count'] - mean) / stddev
            if abs(z) >= z_threshold:
                anomalies.append({
                    'day': r['day'],
                    'count': r['count'],
                    'z_score': round(z, 2),
                    'severity': 'high' if z > 0 else 'low',
                })

    return {
        'baseline': {'mean': round(mean, 1), 'stddev': round(stddev, 1)},
        'anomalies': anomalies,
        'sample_days': n,
        'z_threshold': z_threshold,
    }


def _summary_kpis(filters):
    """Compact KPI block used by period comparison."""
    where, params = _build_where_clause(filters)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN connected_time > 0 THEN 1 ELSE 0 END) AS answered,
            AVG(CASE WHEN connected_time > 0 THEN connected_time END) AS acd,
            AVG(CASE WHEN connected_time > 0 THEN ring_time END) AS asa,
            SUM(connected_time) AS total_seconds
        FROM smdr_calls {where}
    """, params or [])
    row = cursor.fetchone()
    conn.close()
    total = row['total'] or 0
    answered = row['answered'] or 0
    return {
        'total': total,
        'answered': answered,
        'answer_rate': round(answered / total, 4) if total else 0,
        'acd_seconds': round(row['acd'] or 0, 1),
        'asa_seconds': round(row['asa'] or 0, 1),
        'total_seconds': row['total_seconds'] or 0,
    }


def get_period_comparison(filters):
    """
    Compare current filtered period against the same-length previous
    period. Returns None if start_date/end_date aren't both set.
    """
    if not filters or not filters.get('start_date') or not filters.get('end_date'):
        return None

    try:
        start = _parse_timestamp(filters['start_date'])
        end = _parse_timestamp(filters['end_date'])
    except Exception:
        return None

    duration = end - start
    if duration.total_seconds() <= 0:
        return None

    prev_filters = dict(filters)
    prev_filters['start_date'] = (start - duration).strftime('%Y-%m-%d %H:%M:%S')
    prev_filters['end_date'] = start.strftime('%Y-%m-%d %H:%M:%S')

    return {
        'current': _summary_kpis(filters),
        'previous': _summary_kpis(prev_filters),
        'previous_range': {
            'start_date': prev_filters['start_date'],
            'end_date': prev_filters['end_date'],
        },
    }


def iter_calls_for_export(filters=None):
    """
    Generator that yields call rows (as dicts) for streaming CSV export.
    Uses fetchmany to avoid loading the whole result set into memory.
    """
    where, params = _build_where_clause(filters)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT
            id, call_start, call_direction, caller, dialed_number, account,
            connected_time, ring_time, party1_name, party2_name, is_internal
        FROM smdr_calls {where}
        ORDER BY call_start DESC
    """, params or [])
    try:
        while True:
            rows = cursor.fetchmany(500)
            if not rows:
                break
            for r in rows:
                yield dict(r)
    finally:
        conn.close()


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


def get_timestamp_mode():
    """
    Get how timestamps are stored in the database.
    'utc'     → timestamps are in UTC (e.g. from a PBX sending UTC)
    'local'   → timestamps are in the configured timezone (e.g. from a PBX sending local time)
    """
    return get_setting('timestamp_mode', 'utc')


def localize_timestamp(dt_str, tz=None, mode=None):
    """
    Convert a stored timestamp string to an ISO 8601 string with UTC offset,
    so the frontend can correctly display it in the configured timezone.

    The conversion depends on 'timestamp_mode':
      - 'utc':   stored timestamps are in UTC → attach +00:00, then convert to tz
      - 'local': stored timestamps are already in tz → just attach the offset

    DST is handled automatically via the zoneinfo database.

    Examples (with timezone Europe/Rome, summer = CEST +02:00):
      mode='utc',   input='2025-07-15T10:35:19'  → '2025-07-15T12:35:19+02:00'
      mode='local', input='2025-07-15T12:35:19'  → '2025-07-15T12:35:19+02:00'
    """
    if not dt_str:
        return dt_str

    if tz is None:
        tz = get_app_timezone()
    if mode is None:
        mode = get_timestamp_mode()

    ts = dt_str.strip()

    # Already timezone-aware → return as-is
    if ts.endswith('Z') or (len(ts) > 5 and ts[-6] in ('+', '-') and ts[-3] == ':'):
        return ts

    try:
        dt_naive = _parse_timestamp(ts)

        if mode == 'utc':
            # Stored as UTC → mark as UTC, then convert to configured timezone
            dt_utc = dt_naive.replace(tzinfo=timezone.utc)
            dt_local = dt_utc.astimezone(tz)
        else:
            # Stored as local time → treat as in the configured timezone
            dt_local = dt_naive.replace(tzinfo=tz)

        return dt_local.isoformat()
    except Exception:
        return dt_str


def _parse_timestamp(ts):
    """Parse a timestamp string into a naive datetime object."""
    if 'T' in ts:
        return datetime.fromisoformat(ts)
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M:%S'):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(ts)


def get_tz_info():
    """
    Get timezone info for the frontend: name, UTC offset, DST status.
    Returns dict with timezone details.
    """
    tz = get_app_timezone()
    tz_name = get_setting('timezone', 'Europe/Rome')
    mode = get_timestamp_mode()
    now = datetime.now(tz)

    # Format UTC offset as '+02:00' or '-05:00' etc.
    formatted_offset = now.strftime('%z')  # e.g. '+0200' or '-0500'
    formatted_offset = f'{formatted_offset[:3]}:{formatted_offset[3:]}'

    # Check if DST is active
    dst_active = bool(now.dst())

    return {
        'timezone': tz_name,
        'utc_offset': formatted_offset,
        'utc_offset_minutes': int(now.utcoffset().total_seconds() / 60),
        'dst_active': dst_active,
        'current_time': now.isoformat(),
        'timestamp_mode': mode,
    }