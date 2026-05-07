"""Flask application for SMDR web interface"""
import hmac
import os
import sys
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
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
)

# Load environment variables from .env
load_dotenv()


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
    total_count = count_calls()

    return jsonify({
        'calls': _localize_calls([dict(row) for row in calls]),
        'total': total_count,
        'limit': limit,
        'offset': offset
    })


@app.route('/statistics')
@api_login_required
def statistics():
    """Statistics dashboard with date range filters"""
    filters = {}

    call_direction = request.args.get('call_direction')
    if call_direction:
        filters['call_direction'] = call_direction

    is_internal = request.args.get('is_internal')
    if is_internal:
        filters['is_internal'] = is_internal

    start_date = request.args.get('start_date')
    if start_date:
        filters['start_date'] = start_date

    end_date = request.args.get('end_date')
    if end_date:
        # Add time to make it end-of-day inclusive
        if len(end_date) == 10:  # YYYY-MM-DD format
            filters['end_date'] = end_date + ' 23:59:59'
        else:
            filters['end_date'] = end_date

    stats = get_call_stats(filters)

    # Add timezone info to statistics response
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