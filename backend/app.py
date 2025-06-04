from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, time, datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_migrate import Migrate
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///worktime.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Define Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False) # Store hashed passwords
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee') # e.g., employee, manager, admin
    # Add relationships
    shifts = db.relationship('Shift', backref='employee', lazy=True)
    time_entries = db.relationship('TimeEntry', backref='employee', lazy=True)
    vacation_requests = db.relationship('VacationRequest', backref='employee', lazy=True)
    overtime_entries = db.relationship('OvertimeEntry', backref='employee', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    location = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # status (e.g., pending, confirmed, cancelled) - can be added later

    def __repr__(self):
        return f'<Shift {self.date} {self.start_time}-{self.end_time}>'

class TimeEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    clock_in_time = db.Column(db.DateTime, nullable=False)
    clock_out_time = db.Column(db.DateTime)
    date = db.Column(db.Date, nullable=False)

    def __repr__(self):
        return f'<TimeEntry {self.user_id} on {self.date}>'

class VacationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending') # pending, approved, rejected
    reason = db.Column(db.String(200))
    requested_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<VacationRequest {self.user_id} from {self.start_date} to {self.end_date}>'

class OvertimeEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    hours = db.Column(db.Float, nullable=False)
    overtime_type = db.Column(db.String(50)) # e.g., weekday, weekend, holiday
    notes = db.Column(db.String(200))
    status = db.Column(db.String(20), nullable=False, default='pending') # pending, approved, rejected
    requested_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<OvertimeEntry {self.user_id} on {self.date} for {self.hours} hours>'

if __name__ == '__main__':
    app.run(debug=True)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    role = data.get('role', 'employee') # Default role

    if not username or not password or not email:
        return jsonify({'message': 'Missing username, password, or email'}), 400

    if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
        return jsonify({'message': 'User already exists'}), 409

    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password_hash=hashed_password, email=email, role=role)

    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Failed to create user', 'error': str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Missing username or password'}), 400

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password_hash, password):
        # For now, just return a success message.
        # Later, implement session management or token generation here.
        # For example, using Flask-Login: login_user(user)
        return jsonify({'message': 'Login successful', 'user_id': user.id, 'username': user.username, 'email': user.email, 'role': user.role}), 200
    else:
        return jsonify({'message': 'Invalid username or password'}), 401

# --- Shift Management ---
@app.route('/shifts', methods=['POST'])
def create_shift():
    data = request.get_json()

    user_id = data.get('user_id')
    shift_date_str = data.get('date') # Expected format: YYYY-MM-DD
    start_time_str = data.get('start_time') # Expected format: HH:MM
    end_time_str = data.get('end_time') # Expected format: HH:MM
    location = data.get('location')

    if not all([user_id, shift_date_str, start_time_str, end_time_str]):
        return jsonify({'message': 'Missing required fields (user_id, date, start_time, end_time)'}), 400

    try:
        shift_date = datetime.strptime(shift_date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
    except ValueError:
        return jsonify({'message': 'Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time.'}), 400

    # Check if user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    new_shift = Shift(
        user_id=user_id,
        date=shift_date,
        start_time=start_time,
        end_time=end_time,
        location=location
    )

    try:
        db.session.add(new_shift)
        db.session.commit()
        return jsonify({
            'message': 'Shift created successfully',
            'shift': {
                'id': new_shift.id,
                'user_id': new_shift.user_id,
                'date': new_shift.date.isoformat(),
                'start_time': new_shift.start_time.isoformat(),
                'end_time': new_shift.end_time.isoformat(),
                'location': new_shift.location
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Failed to create shift', 'error': str(e)}), 500

@app.route('/shifts', methods=['GET'])
def get_shifts():
    # Get query parameters
    user_id = request.args.get('user_id', type=int)
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    query = Shift.query

    if user_id:
        query = query.filter_by(user_id=user_id)

    if year and month:
        # Filter by shifts within the given month and year
        # This requires ensuring the date column in Shift model is compatible
        # For SQLite, we might need to extract year and month from the date
        # For more complex queries, SQLAlchemy's func might be needed, e.g. db.extract
        # For now, let's assume a simple filter that might need adjustment based on DB
        # A more robust way for date filtering:
        # from sqlalchemy import extract
        # query = query.filter(extract('year', Shift.date) == year, extract('month', Shift.date) == month)
        # For simplicity here, we'll retrieve all and let frontend filter, or refine this if subtask fails.
        # Let's try a direct string comparison approach first for SQLite if date is stored as string,
        # or rely on Python filtering after fetching if it's too complex for a quick subtask.
        # Given Shift.date is db.Column(db.Date), direct filtering should work.
        query = query.filter(db.extract('year', Shift.date) == year, db.extract('month', Shift.date) == month)


    shifts_list = []
    for shift in query.all():
        shifts_list.append({
            'id': shift.id,
            'user_id': shift.user_id,
            'username': shift.employee.username, # Accessing username via backref
            'date': shift.date.isoformat(),
            'start_time': shift.start_time.isoformat(),
            'end_time': shift.end_time.isoformat(),
            'location': shift.location
        })

    return jsonify(shifts_list), 200

# --- Time Tracking (Clock-in/Clock-out) ---
@app.route('/time_entries/clock_in', methods=['POST'])
def clock_in():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'message': 'Missing user_id'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    now = datetime.now()
    today = now.date()

    # Check if there's already an open clock-in for today for this user
    existing_open_entry = TimeEntry.query.filter_by(user_id=user_id, date=today, clock_out_time=None).first()
    if existing_open_entry:
        return jsonify({'message': 'User already clocked in today and not clocked out'}), 409

    new_time_entry = TimeEntry(
        user_id=user_id,
        clock_in_time=now,
        date=today
    )

    try:
        db.session.add(new_time_entry)
        db.session.commit()
        return jsonify({
            'message': 'Clock-in successful',
            'time_entry': {
                'id': new_time_entry.id,
                'user_id': new_time_entry.user_id,
                'clock_in_time': new_time_entry.clock_in_time.isoformat(),
                'date': new_time_entry.date.isoformat()
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Failed to clock in', 'error': str(e)}), 500

@app.route('/time_entries/clock_out', methods=['POST'])
def clock_out():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'message': 'Missing user_id'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    now = datetime.now()
    today = now.date()

    # Find the most recent open time entry for this user for today
    time_entry = TimeEntry.query.filter_by(user_id=user_id, date=today, clock_out_time=None).order_by(TimeEntry.clock_in_time.desc()).first()

    if not time_entry:
        # Option 1: Create a new entry with only clock-out (might be problematic for duration calculation)
        # Option 2: Return an error, user must clock in first. This is generally safer.
        return jsonify({'message': 'No open clock-in found for today. Please clock in first.'}), 404

    time_entry.clock_out_time = now

    try:
        db.session.commit()
        # Calculate duration
        duration = time_entry.clock_out_time - time_entry.clock_in_time
        duration_hours = duration.total_seconds() / 3600

        return jsonify({
            'message': 'Clock-out successful',
            'time_entry': {
                'id': time_entry.id,
                'user_id': time_entry.user_id,
                'clock_in_time': time_entry.clock_in_time.isoformat(),
                'clock_out_time': time_entry.clock_out_time.isoformat(),
                'date': time_entry.date.isoformat(),
                'duration_hours': round(duration_hours, 2)
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Failed to clock out', 'error': str(e)}), 500

@app.route('/time_entries', methods=['GET'])
def get_time_entries():
    user_id = request.args.get('user_id', type=int)
    start_date_str = request.args.get('start_date') # YYYY-MM-DD
    end_date_str = request.args.get('end_date')     # YYYY-MM-DD

    if not user_id:
        return jsonify({'message': 'Missing user_id parameter'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    query = TimeEntry.query.filter_by(user_id=user_id)

    try:
        if start_date_str:
            start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(TimeEntry.date >= start_date_obj)
        if end_date_str:
            end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(TimeEntry.date <= end_date_obj)
    except ValueError:
        return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    query = query.order_by(TimeEntry.date.desc(), TimeEntry.clock_in_time.desc())

    time_entries_list = []
    for entry in query.all():
        duration_hours = None
        if entry.clock_in_time and entry.clock_out_time:
            duration = entry.clock_out_time - entry.clock_in_time
            duration_hours = round(duration.total_seconds() / 3600, 2)

        time_entries_list.append({
            'id': entry.id,
            'user_id': entry.user_id,
            'date': entry.date.isoformat(),
            'clock_in_time': entry.clock_in_time.isoformat() if entry.clock_in_time else None,
            'clock_out_time': entry.clock_out_time.isoformat() if entry.clock_out_time else None,
            'duration_hours': duration_hours
        })

    return jsonify(time_entries_list), 200

# --- Vacation Management ---
@app.route('/vacation_requests', methods=['POST'])
def create_vacation_request():
    data = request.get_json()
    user_id = data.get('user_id')
    start_date_str = data.get('start_date') # Expected format: YYYY-MM-DD
    end_date_str = data.get('end_date')     # Expected format: YYYY-MM-DD
    reason = data.get('reason')

    if not all([user_id, start_date_str, end_date_str]):
        return jsonify({'message': 'Missing required fields (user_id, start_date, end_date)'}), 400

    try:
        start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    if start_date_obj > end_date_obj:
        return jsonify({'message': 'Start date cannot be after end date.'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    new_request = VacationRequest(
        user_id=user_id,
        start_date=start_date_obj,
        end_date=end_date_obj,
        reason=reason,
        status='pending' # Default status
    )

    try:
        db.session.add(new_request)
        db.session.commit()
        return jsonify({
            'message': 'Vacation request created successfully',
            'request': {
                'id': new_request.id,
                'user_id': new_request.user_id,
                'start_date': new_request.start_date.isoformat(),
                'end_date': new_request.end_date.isoformat(),
                'reason': new_request.reason,
                'status': new_request.status,
                'requested_at': new_request.requested_at.isoformat()
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Failed to create vacation request', 'error': str(e)}), 500

@app.route('/vacation_requests', methods=['GET'])
def get_vacation_requests():
    user_id = request.args.get('user_id', type=int)
    status = request.args.get('status') # e.g., pending, approved, rejected
    # Additional filters for 'upcoming', 'past' can be added based on current date
    # For 'upcoming': query where start_date >= today and status == 'approved'
    # For 'history': query where end_date < today or status in ['rejected', 'approved'] (and in the past)

    if not user_id:
        return jsonify({'message': 'Missing user_id parameter'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    query = VacationRequest.query.filter_by(user_id=user_id)

    if status:
        query = query.filter(VacationRequest.status == status)

    # Example for 'Prossime' (Upcoming approved):
    # if request.args.get('view') == 'upcoming':
    #    today = date.today()
    #    query = query.filter(VacationRequest.status == 'approved', VacationRequest.start_date >= today)
    # Example for 'Storico' (Past or decided):
    # if request.args.get('view') == 'history':
    #    today = date.today()
    #    query = query.filter((VacationRequest.status == 'approved' & VacationRequest.end_date < today) | VacationRequest.status == 'rejected')
    # For simplicity, these specific views ('Prossime', 'In Attesa', 'Storico') might be handled by combining status and date range filters on the client or specific server-side flags.
    # The current GET allows filtering by status, which covers 'In Attesa'. 'Prossime' and 'Storico' would need date logic.

    query = query.order_by(VacationRequest.start_date.desc())

    requests_list = []
    for req in query.all():
        requests_list.append({
            'id': req.id,
            'user_id': req.user_id,
            'username': req.employee.username,
            'start_date': req.start_date.isoformat(),
            'end_date': req.end_date.isoformat(),
            'reason': req.reason,
            'status': req.status,
            'requested_at': req.requested_at.isoformat()
        })

    return jsonify(requests_list), 200

# TODO for later: Add endpoints for updating status (approve/reject) by a manager
# @app.route('/vacation_requests/<int:request_id>/approve', methods=['POST']) (Manager role)
# @app.route('/vacation_requests/<int:request_id>/reject', methods=['POST']) (Manager role)

# --- Overtime Management ---
@app.route('/overtime_entries', methods=['POST'])
def create_overtime_entry():
    data = request.get_json()
    user_id = data.get('user_id')
    overtime_date_str = data.get('date') # Expected format: YYYY-MM-DD
    hours = data.get('hours')
    overtime_type = data.get('overtime_type')
    notes = data.get('notes')

    if not all([user_id, overtime_date_str, hours, overtime_type]):
        return jsonify({'message': 'Missing required fields (user_id, date, hours, overtime_type)'}), 400

    try:
        overtime_date_obj = datetime.strptime(overtime_date_str, '%Y-%m-%d').date()
        hours_float = float(hours)
        if hours_float <= 0:
            raise ValueError("Hours must be positive")
    except ValueError:
        return jsonify({'message': 'Invalid date or hours format. Use YYYY-MM-DD for date and a positive number for hours.'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    new_entry = OvertimeEntry(
        user_id=user_id,
        date=overtime_date_obj,
        hours=hours_float,
        overtime_type=overtime_type,
        notes=notes,
        status='pending' # Default status
    )

    try:
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({
            'message': 'Overtime entry created successfully',
            'entry': {
                'id': new_entry.id,
                'user_id': new_entry.user_id,
                'date': new_entry.date.isoformat(),
                'hours': new_entry.hours,
                'overtime_type': new_entry.overtime_type,
                'notes': new_entry.notes,
                'status': new_entry.status,
                'requested_at': new_entry.requested_at.isoformat()
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Failed to create overtime entry', 'error': str(e)}), 500

@app.route('/overtime_entries', methods=['GET'])
def get_overtime_entries():
    user_id = request.args.get('user_id', type=int)
    status = request.args.get('status') # e.g., pending, approved, rejected

    if not user_id:
        return jsonify({'message': 'Missing user_id parameter'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    query = OvertimeEntry.query.filter_by(user_id=user_id)

    if status:
        query = query.filter(OvertimeEntry.status == status)

    # Consider adding date range filters if needed for history views later
    query = query.order_by(OvertimeEntry.date.desc())

    entries_list = []
    for entry in query.all():
        entries_list.append({
            'id': entry.id,
            'user_id': entry.user_id,
            'username': entry.employee.username,
            'date': entry.date.isoformat(),
            'hours': entry.hours,
            'overtime_type': entry.overtime_type,
            'notes': entry.notes,
            'status': entry.status,
            'requested_at': entry.requested_at.isoformat()
        })

    return jsonify(entries_list), 200

# TODO for later: Add endpoints for updating status (approve/reject) by a manager
# @app.route('/overtime_entries/<int:entry_id>/approve', methods=['POST']) (Manager role)
# @app.route('/overtime_entries/<int:entry_id>/reject', methods=['POST']) (Manager role)

# --- Reporting ---
@app.route('/reports/annual_hours/<int:user_id>/<int:year>', methods=['GET'])
def get_annual_hours_report(user_id, year):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # --- Calculate Total Annual Hours ---
    # We need to sum durations of time entries for the user and year.
    # Duration is clock_out_time - clock_in_time.
    # This is a bit complex with SQLAlchemy's sum over timedeltas directly.
    # An alternative is to iterate and sum in Python, or use database-specific functions.

    # Let's iterate and sum in Python for clarity here.
    # For performance on large datasets, a raw SQL or more advanced SQLAlchemy query might be better.

    time_entries_for_year = TimeEntry.query.filter(
        TimeEntry.user_id == user_id,
        db.extract('year', TimeEntry.date) == year,
        TimeEntry.clock_out_time.isnot(None) # Only include completed entries
    ).all()

    total_annual_seconds = 0
    monthly_hours = {month: 0 for month in range(1, 13)} # Initialize all months to 0 hours

    for entry in time_entries_for_year:
        if entry.clock_in_time and entry.clock_out_time:
            duration = entry.clock_out_time - entry.clock_in_time
            duration_seconds = duration.total_seconds()
            total_annual_seconds += duration_seconds

            entry_month = entry.date.month
            monthly_hours[entry_month] += duration_seconds / 3600 # Convert seconds to hours for monthly sum

    total_annual_hours = round(total_annual_seconds / 3600, 2)

    # Prepare monthly breakdown for JSON response
    monthly_breakdown = []
    for month_num, hours_sum in monthly_hours.items():
        monthly_breakdown.append({
            'month': month_num,
            # 'month_name': datetime(year, month_num, 1).strftime('%b'), # Optional: month name
            'total_hours': round(hours_sum, 2)
        })

    return jsonify({
        'user_id': user_id,
        'year': year,
        'total_annual_hours': total_annual_hours,
        'monthly_breakdown': monthly_breakdown
    }), 200

# --- Static File Serving ---
# Serve login.html at /login.html and at /
@app.route('/')
@app.route('/login.html')
def serve_login_page():
    return send_from_directory(os.path.join(os.path.dirname(app.root_path)), 'login.html')

@app.route('/register.html')
def serve_register_page():
    return send_from_directory(os.path.join(os.path.dirname(app.root_path)), 'register.html')

# Generic route for other HTML files in the root directory
@app.route('/<path:filename>.html')
def serve_html_page(filename):
    return send_from_directory(os.path.join(os.path.dirname(app.root_path)), f"{filename}.html")

# If you have CSS/JS files in a subfolder (e.g., static/):
# @app.route('/static/<path:filename>')
# def serve_static_files(filename):
#     return send_from_directory(os.path.join(os.path.dirname(app.root_path), 'static'), filename)
