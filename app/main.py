"""Flask application for SMDR web interface"""
import csv
import hmac
import io
import os
import sys
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, Response, render_template, request, jsonify, redirect, url_for, session, flash
from database import (
    init_database,
    get_db_connection,
    get_calls,
    get_call_stats,
    get_call_by_id,
    count_calls,
    update_smdr_record,
    get_calls_by_date_period,
    get_hourly_stats,
    get_setting,
    set_setting,
    get_app_timezone,
    localize_timestamp,
    get_tz_info,
    get_timestamp_mode,
    get_number_categories,
    get_duration_histogram,
    get_hour_dow_heatmap,
    get_dow_breakdown,
    get_anomalies,
    get_period_comparison,
    get_flow_breakdown,
    get_extension_load,
    get_transfer_matrix,
    iter_calls_for_export,
    get_number_stats,
)

# Load environment variables from .env
load_dotenv(override=True)


def _require_env(name):
    """Read a required env var or fail fast with a helpful message."""
    value = os.environ.get(name)
    if not value:
        sys.stderr.write(
            f"\nERRORE: variabile d'ambiente '{name}' non impostata.\n"
            f"Crea un file .env nella root del progetto con:\n"
            f"  SMDR_USERNAME=<utente>\n"
            f"  SMDR_PASSWORD=<password forte>\n"
            f"  SMDR_SECRET_KEY=<stringa casuale lunga>\n"
            f"Per generare una secret key:\n"
            f"  python -c 'import secrets; print(secrets.token_hex(32))'\n\n"
        )
        sys.exit(1)
    return value


SMDR_USERNAME = _require_env('SMDR_USERNAME')
SMDR_PASSWORD = _require_env('SMDR_PASSWORD')
_SECRET_KEY = _require_env('SMDR_SECRET_KEY')

app = Flask(__name__)
app.config['SECRET_KEY'] = _SECRET_KEY
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'data')

# Session cookie hardening. SECURE defaults to True; set SMDR_COOKIE_SECURE=false
# in dev when serving over plain HTTP on localhost.
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get('SMDR_COOKIE_SECURE', 'true').lower() == 'true',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

# Initialize database on startup
init_database()


# ── Timezone helper for API responses ──────────────────────

def _localize_call(call_dict):
    """Localize the call_start timestamp in a call dict to the configured timezone."""
    if call_dict.get('call_start'):
        call_dict['call_start'] = localize_timestamp(
            call_dict['call_start'],
            mode=get_timestamp_mode()
        )
    return call_dict


def _localize_calls(calls_list):
    """Localize call_start timestamps for a list of call dicts."""
    return [_localize_call(c) for c in calls_list]


# ── Auth helpers ────────────────────────────────────────────

def login_required(f):
    """Decorator that redirects to login if user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    """Decorator that returns 401 for API calls if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


# ── Filter parsing helper ──────────────────────────────────

def _parse_filters_from_args():
    """
    Build the standard filters dict from request.args. Used by all
    statistics endpoints so they accept the same query string shape.
    """
    filters = {}
    for key in ('call_direction', 'is_internal', 'dialed_number', 'caller', 'account'):
        val = request.args.get(key)
        if val:
            filters[key] = val
    flow_type = request.args.get('flow_type')
    if flow_type in ('II', 'IE', 'EI', 'EE'):
        filters['flow_type'] = flow_type
    start_date = request.args.get('start_date')
    if start_date:
        filters['start_date'] = start_date
    end_date = request.args.get('end_date')
    if end_date:
        # End-of-day inclusive when only a date was provided
        if len(end_date) == 10:
            filters['end_date'] = end_date + ' 23:59:59'
        else:
            filters['end_date'] = end_date
    return filters


# ── Auth routes ─────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if session.get('logged_in'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        # Constant-time comparison to avoid leaking timing information.
        # Both branches must run regardless of which one fails.
        username_ok = hmac.compare_digest(username, SMDR_USERNAME)
        password_ok = hmac.compare_digest(password, SMDR_PASSWORD)

        if username_ok and password_ok:
            session.permanent = True
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Credenziali non valide. Riprova.')

    return render_template('login.html', error=None)


@app.route('/logout')
def logout():
    """Logout and redirect to login page"""
    session.clear()
    return redirect(url_for('login'))


# ── Protected pages ─────────────────────────────────────────

@app.route('/')
@login_required
def index():
    """Home page with search and statistics"""
    return render_template('index.html')


# ── Settings API ────────────────────────────────────────────

@app.route('/api/settings', methods=['GET'])
@api_login_required
def get_settings():
    """Get current application settings including timezone info."""
    tz_info = get_tz_info()
    return jsonify(tz_info)


@app.route('/api/settings', methods=['POST'])
@api_login_required
def update_settings():
    """Update application settings."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate and update timezone
    if 'timezone' in data:
        tz_name = data['timezone']
        from zoneinfo import ZoneInfo
        try:
            ZoneInfo(tz_name)  # Validate timezone name
            set_setting('timezone', tz_name)
        except Exception:
            return jsonify({'error': f'Invalid timezone: {tz_name}'}), 400

    # Validate and update timestamp_mode
    if 'timestamp_mode' in data:
        mode = data['timestamp_mode']
        if mode not in ('utc', 'local'):
            return jsonify({'error': f'Invalid timestamp_mode: {mode}. Must be "utc" or "local".'}), 400
        set_setting('timestamp_mode', mode)

    return jsonify(get_tz_info())


# ── Protected API ───────────────────────────────────────────

@app.route('/search')
@api_login_required
def search():
    """Search calls"""
    filters = {
        'call_direction': request.args.get('call_direction'),
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'dialed_number': request.args.get('dialed_number'),
        'caller': request.args.get('caller'),
        'account': request.args.get('account'),
        'is_internal': request.args.get('is_internal'),
    }
    ft = request.args.get('flow_type')
    if ft in ('II', 'IE', 'EI', 'EE'):
        filters['flow_type'] = ft

    try:
        limit = int(request.args.get('limit', 100))
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    calls = get_calls(filters, limit, offset)
    total_count = count_calls(filters)

    return jsonify({
        'calls': _localize_calls([dict(row) for row in calls]),
        'total': total_count,
        'limit': limit,
        'offset': offset
    })


@app.route('/statistics')
@api_login_required
def statistics():
    """Statistics dashboard with date range filters and optional flow_type."""
    stats = get_call_stats(_parse_filters_from_args())
    stats['tz_info'] = get_tz_info()
    return jsonify(stats)


@app.route('/calls/<int:call_id>')
@api_login_required
def get_call(call_id):
    """Get details of a specific call"""
    call = get_call_by_id(call_id)
    if call:
        return jsonify(_localize_call(dict(call)))
    return jsonify({'error': 'Call not found'}), 404


@app.route('/api/stats/hourly')
@api_login_required
def get_hourly_stats_route():
    """Get hourly call distribution for a given date range"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    stats = get_hourly_stats(start_date=start_date, end_date=end_date)
    stats['tz_info'] = get_tz_info()
    return jsonify(stats)


@app.route('/api/months')
@api_login_required
def get_months():
    """Get available months with data"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT strftime("%Y-%m", call_start) as month,
               COUNT(*) as count,
               MIN(call_start) as first_call,
               MAX(call_start) as last_call
        FROM smdr_calls
        GROUP BY month
        ORDER BY month DESC
        LIMIT 24
    ''')

    months = []
    for row in cursor.fetchall():
        month = dict(row)
        month['first_call'] = month['first_call'].isoformat() if month['first_call'] else None
        month['last_call'] = month['last_call'].isoformat() if month['last_call'] else None
        months.append(month)

    conn.close()
    return jsonify(months)


@app.route('/api/daily/<year>/<month>/<day>')
@api_login_required
def get_daily_calls(year, month, day):
    """Get calls for a specific day"""
    try:
        calls = get_calls_by_date_period(int(year), int(month), int(day))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT SUM(connected_time) as total, SUM(ring_time) as ring_total FROM smdr_calls WHERE strftime("%Y-%m-%d", call_start) = ?',
            (f'{year:04d}-{month:02d}-{day:02d}',)
        )
        result = cursor.fetchone()
        conn.close()

        return jsonify({
            'calls': _localize_calls([dict(row) for row in calls]),
            'total_duration_seconds': result['total'] or 0,
            'total_ring_seconds': result['ring_total'] or 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/daily/<year>/<month>')
@api_login_required
def get_monthly_calls(year, month):
    """Get calls for a specific month"""
    try:
        calls = get_calls_by_date_period(int(year), int(month))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT SUM(connected_time) as total, SUM(ring_time) as ring_total FROM smdr_calls WHERE strftime("%Y-%m", call_start) = ?',
            (f'{year:04d}-{month:02d}',)
        )
        result = cursor.fetchone()
        conn.close()

        return jsonify({
            'calls': _localize_calls([dict(row) for row in calls]),
            'total_duration_seconds': result['total'] or 0,
            'total_ring_seconds': result['ring_total'] or 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/daily/<year>')
@api_login_required
def get_yearly_calls(year):
    """Get calls for a specific year"""
    try:
        calls = get_calls_by_date_period(int(year))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT SUM(connected_time) as total, SUM(ring_time) as ring_total FROM smdr_calls WHERE strftime("%Y", call_start) = ?',
            (f'{year:04d}',)
        )
        result = cursor.fetchone()
        conn.close()

        return jsonify({
            'calls': _localize_calls([dict(row) for row in calls]),
            'total_duration_seconds': result['total'] or 0,
            'total_ring_seconds': result['ring_total'] or 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/daily')
@api_login_required
def get_today_calls():
    """Get calls for today in the configured timezone"""
    tz = get_app_timezone()
    today = datetime.now(tz).strftime('%Y-%m-%d')
    calls = get_calls_by_date_period(None, None, today)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT SUM(connected_time) as total, SUM(ring_time) as ring_total FROM smdr_calls WHERE strftime("%Y-%m-%d", call_start) = ?',
        (today,)
    )
    result = cursor.fetchone()
    conn.close()

    return jsonify({
        'calls': _localize_calls([dict(row) for row in calls]),
        'total_duration_seconds': result['total'] or 0,
        'total_ring_seconds': result['ring_total'] or 0,
        'date': today
    })


@app.route('/api/stats/heatmap')
@api_login_required
def get_heatmap_route():
    """Day-of-week × hour heatmap (7×24)."""
    return jsonify(get_hour_dow_heatmap(_parse_filters_from_args()))


@app.route('/api/stats/duration-histogram')
@api_login_required
def get_duration_histogram_route():
    """Bucketed call duration distribution."""
    return jsonify({'buckets': get_duration_histogram(_parse_filters_from_args())})


@app.route('/api/stats/number-categories')
@api_login_required
def get_number_categories_route():
    """Italian-aware number categorization. ?field=dialed_number|caller"""
    field = request.args.get('field', 'dialed_number')
    return jsonify({
        'field': field if field in ('dialed_number', 'caller') else 'dialed_number',
        'categories': get_number_categories(_parse_filters_from_args(), field=field),
    })


@app.route('/api/stats/dow')
@api_login_required
def get_dow_route():
    """Day-of-week breakdown (Mon-first) with answer rate."""
    return jsonify({'days': get_dow_breakdown(_parse_filters_from_args())})


@app.route('/api/stats/anomalies')
@api_login_required
def get_anomalies_route():
    """Anomalous days (|z-score| >= threshold) over the last N days."""
    try:
        lookback = int(request.args.get('lookback_days', 60))
    except (TypeError, ValueError):
        lookback = 60
    try:
        z_threshold = float(request.args.get('z_threshold', 2.0))
    except (TypeError, ValueError):
        z_threshold = 2.0
    lookback = max(7, min(lookback, 365))
    z_threshold = max(1.0, min(z_threshold, 5.0))
    return jsonify(get_anomalies(_parse_filters_from_args(), lookback_days=lookback, z_threshold=z_threshold))


@app.route('/api/stats/compare')
@api_login_required
def get_compare_route():
    """Compare current period vs previous period of equal length."""
    result = get_period_comparison(_parse_filters_from_args())
    if result is None:
        return jsonify({'error': 'start_date e end_date richiesti per il confronto'}), 400
    return jsonify(result)


@app.route('/api/export/calls.csv')
@api_login_required
def export_calls_csv():
    """Stream the filtered call list as CSV."""
    filters = _parse_filters_from_args()
    tz_mode = get_timestamp_mode()

    columns = [
        'id', 'call_start', 'call_direction', 'caller', 'dialed_number',
        'account', 'connected_time', 'ring_time',
        'party1_name', 'party2_name', 'is_internal',
    ]

    def generate():
        # UTF-8 BOM so Excel opens it as UTF-8 by default
        buf = io.StringIO()
        buf.write('﻿')
        writer = csv.writer(buf, delimiter=',', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(columns)
        yield buf.getvalue()

        for row in iter_calls_for_export(filters):
            buf = io.StringIO()
            writer = csv.writer(buf, delimiter=',', quoting=csv.QUOTE_MINIMAL)
            row_localized = dict(row)
            if row_localized.get('call_start'):
                row_localized['call_start'] = localize_timestamp(row_localized['call_start'], mode=tz_mode)
            writer.writerow([row_localized.get(c, '') for c in columns])
            yield buf.getvalue()

    filename = f'smdr_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
    return Response(
        generate(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@app.route('/api/stats/flows')
@api_login_required
def get_flows_route():
    """Breakdown per tipo flusso: E→I, I→E, I→I, E→E."""
    return jsonify({'flows': get_flow_breakdown(_parse_filters_from_args())})


@app.route('/api/stats/extension-load')
@api_login_required
def get_extension_load_route():
    """Top extensions by call volume. ?role=inbound|outbound|internal&limit=N"""
    role = request.args.get('role', 'inbound')
    if role not in ('inbound', 'outbound', 'internal'):
        role = 'inbound'
    try:
        limit = int(request.args.get('limit', 15))
    except (TypeError, ValueError):
        limit = 15
    limit = max(1, min(limit, 100))
    return jsonify({
        'role': role,
        'limit': limit,
        'extensions': get_extension_load(_parse_filters_from_args(), role=role, limit=limit),
    })


@app.route('/api/stats/transfers')
@api_login_required
def get_transfers_route():
    """Heuristic transfer detection. ?max_lag_seconds=N&limit=N"""
    try:
        lag = int(request.args.get('max_lag_seconds', 60))
    except (TypeError, ValueError):
        lag = 60
    try:
        limit = int(request.args.get('limit', 30))
    except (TypeError, ValueError):
        limit = 30
    lag = max(5, min(lag, 600))
    limit = max(1, min(limit, 100))
    return jsonify(get_transfer_matrix(_parse_filters_from_args(), max_lag_seconds=lag, limit=limit))


@app.route('/api/stats/number-detail')
@api_login_required
def get_number_detail_route():
    """Detailed statistics for a single phone number or extension."""
    number = request.args.get('number', '').strip()
    field = request.args.get('field', 'dialed_number')
    if not number:
        return jsonify({'error': 'Parametro number richiesto'}), 400
    if field not in ('dialed_number', 'caller'):
        field = 'dialed_number'
    result = get_number_stats(number, field, _parse_filters_from_args())
    result['recent_calls'] = _localize_calls(result['recent_calls'])
    return jsonify(result)


@app.route('/api/health')
def health_check():
    """Health check endpoint (unauthenticated)"""
    count = count_calls()
    return jsonify({
        'status': 'ok',
        'database': 'connected',
        'total_calls': count
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)