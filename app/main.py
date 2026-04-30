"""Flask application for SMDR web interface"""
import os
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
    get_calls_by_date_period
)

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SMDR_SECRET_KEY', os.urandom(32).hex())
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'data')

# Credentials from .env
SMDR_USERNAME = os.environ.get('SMDR_USERNAME', 'admin')
SMDR_PASSWORD = os.environ.get('SMDR_PASSWORD', 'smdr2024')

# Initialize database on startup
init_database()


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

        if username == SMDR_USERNAME and password == SMDR_PASSWORD:
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

    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))

    calls = get_calls(filters, limit, offset)
    total_count = count_calls()

    return jsonify({
        'calls': [dict(row) for row in calls],
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
    return jsonify(stats)


@app.route('/calls/<int:call_id>')
@api_login_required
def get_call(call_id):
    """Get details of a specific call"""
    call = get_call_by_id(call_id)
    if call:
        return jsonify(dict(call))
    return jsonify({'error': 'Call not found'}), 404


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
            'calls': [dict(row) for row in calls],
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
            'calls': [dict(row) for row in calls],
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
            'calls': [dict(row) for row in calls],
            'total_duration_seconds': result['total'] or 0,
            'total_ring_seconds': result['ring_total'] or 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/daily')
@api_login_required
def get_today_calls():
    """Get calls for today"""
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
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
        'calls': [dict(row) for row in calls],
        'total_duration_seconds': result['total'] or 0,
        'total_ring_seconds': result['ring_total'] or 0,
        'date': today
    })


@app.route('/api/health')
def health_check():
    """Health check endpoint (unauthenticated)"""
    conn = get_db_connection()
    count = count_calls()
    conn.close()
    return jsonify({
        'status': 'ok',
        'database': 'connected',
        'total_calls': count
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)