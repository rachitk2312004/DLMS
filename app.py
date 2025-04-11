from flask import Flask, send_file, render_template, request, redirect, session, flash, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
import hashlib
from datetime import datetime,timedelta
import re
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz
import pandas as pd
import io
from openpyxl import Workbook
from openpyxl.styles import Alignment
import openpyxl.utils


app = Flask(__name__)
app.secret_key = 'super_secret_key'

app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://dlms_ca7f_user:iKXKHL7S9hqJ3XMQnOJ5ohMVpVN84Hud@dpg-cvqvmtre5dus7380ig10-a.oregon-postgres.render.com/dlms_ca7f"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    uid = db.Column(db.String(255), unique=True, nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    coordinator_unique_id = db.Column(db.String(255), nullable=True)
    otp_verified = db.Column(db.Boolean, default=False)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    coordinator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_name = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(255), nullable=False)
    venue = db.Column(db.String(255), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    date = db.Column(db.String(255), nullable=False)
    max_students = db.Column(db.Integer, nullable=False)
    registration_count = db.Column(db.Integer, default=0)

class DutyLeave(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(255), nullable=False)
    unique_key = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='Pending')
    student_name = db.Column(db.String(255), nullable=False)
    student_uid = db.Column(db.String(255), nullable=False)
    time_slots = db.Column(db.String(255), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)
    remarks = db.Column(db.String(255), nullable=True)

class EventRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    attendance = db.Column(db.String(50), default='Not Marked')
    last_updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def send_otp(email):
    otp = random.randint(100000, 999999)
    session['otp'] = otp  # Store OTP in session for later validation

    # Email sending logic (you can use your preferred method here)
    try:
        sender_email = "eventanddutyleave.ms@gmail.com"
        receiver_email = email
        password = "bvmx exti ueof nsxs"

        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = "Your OTP Code"
        
        body = f"Your OTP code is {otp}"
        message.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        
        return True
    except Exception as e:
        print(f"Error sending OTP: {e}")
        return False
    

@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'student':
            return redirect(url_for('student_dashboard'))
        elif session['role'] == 'coordinator':
            return redirect(url_for('coordinator_dashboard'))
    return render_template('index.html')

@app.route('/register_student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        name = request.form['name']
        uid = request.form['uid']
        email = request.form['email']
        password = request.form['password']
        otp = request.form.get('otp')

        # Password validation
        password_pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,}$"
        if not re.match(password_pattern, password):
            flash("Password must be at least 8 characters long, include an uppercase letter, a lowercase letter, a number, and a special character.", "danger")
            return render_template('register_student.html')

        # OTP validation
        if otp != str(session.get('otp')):
            flash("Invalid OTP.", "danger")
            return render_template('register_student.html')

        # Check if UID or email already exists in the database
        existing_user_by_uid = User.query.filter_by(uid=uid).first()
        existing_user_by_email = User.query.filter_by(email=email).first()

        if existing_user_by_uid:
            flash("UID already exists.", "danger")
            return render_template('register_student.html')

        if existing_user_by_email:
            flash("Email already exists.", "danger")
            return render_template('register_student.html')

        # Hash the password
        hashed_password = hash_password(password)

        # Create a new user
        try:
            new_user = User(
                name=name,
                uid=uid,
                email=email,
                password=hashed_password,
                role='student'
            )
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash("An error occurred during registration. Please try again.", "danger")
            return render_template('register_student.html')

        flash("Student registration successful! Please login.", "success")
        return redirect(url_for('login_student'))

    return render_template('register_student.html')



@app.route('/send_otp', methods=['POST'])
def send_otp_route():
    email = request.form['email']
    if send_otp(email):
        return {'success': True}
    else:
        return {'success': False}
    
    

@app.route('/register_coordinator', methods=['GET', 'POST'])
def register_coordinator():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        otp = request.form.get('otp')
        coordinator_unique_id = request.form['unique_id']

        print("Received form data:", name, email, password, otp, coordinator_unique_id)

        password_pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,}$"
        if not re.match(password_pattern, password):
            print("Password validation failed")
            flash("Password must be at least 8 characters long, include an uppercase letter, a lowercase letter, a number, and a special character.", "danger")
            return render_template('register_coordinator.html')

        if otp != str(session.get('otp')):
            print("OTP validation failed")
            flash("Invalid OTP.", "danger")
            return render_template('register_coordinator.html')

        allowed_ids = ["COORD123", "COORD456"]
        if coordinator_unique_id not in allowed_ids:
            print("Coordinator Unique ID validation failed")
            flash("Invalid Coordinator Unique ID", "danger")
            return render_template('register_coordinator.html')

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print("Email already exists")
            flash("Email already exists.", "danger")
            return render_template('register_coordinator.html')

        
        try:
            new_user = User(
                name=name,
                uid=None,
                email=email,
                password=hashed_password,
                role='coordinator',
                coordinator_unique_id=coordinator_unique_id
            )
            db.session.add(new_user)
            db.session.commit()
            print("User successfully added to the database")
            flash("Coordinator registration successful! Please login.", "success")
            return redirect(url_for('login_coordinator'))
        except Exception as e:
            db.session.rollback()
            print("Database error:", e)
            flash("An error occurred. Please try again.", "danger")

    return render_template('register_coordinator.html')



@app.route('/login_student', methods=['GET', 'POST'])
def login_student():
    if request.method == 'POST':
        email = request.form['email']
        password = hash_password(request.form['password'])

        user = User.query.filter_by(email=email, password=password, role='student').first()

        if user:  # ✅ Check if user exists before accessing attributes
            session['user_id'] = user.id
            session['name'] = user.name
            session['uid'] = user.uid
            session['role'] = user.role
            return redirect(url_for('student_dashboard'))
        else:
            flash("Invalid email or password", "danger")

    return render_template('login_student.html')



@app.route('/login_coordinator', methods=['GET', 'POST'])
def login_coordinator():
    if request.method == 'POST':
        email = request.form['email']
        password = hash_password(request.form['password'])

        user = User.query.filter_by(email=email, password=password, role='coordinator').first()

        if user:  # ✅ Check if user exists before accessing attributes
            session['user_id'] = user.id
            session['name'] = user.name
            session['role'] = user.role
            return redirect(url_for('coordinator_dashboard'))
        else:
            flash("Invalid email or password", "danger")

    return render_template('login_coordinator.html')



@app.route('/student_dashboard', methods=['GET'])
def student_dashboard():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('index'))

    user = User.query.get(session['user_id'])

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('index'))

    # Fetch recent participated events
    participated_events = db.session.query(
        Event.event_name.label("name"), Event.date
    ).join(
        EventRegistration, Event.id == EventRegistration.event_id
    ).filter(
        EventRegistration.user_id == user.id
    ).order_by(
        Event.date.desc()
    ).limit(5).all()

    # Fetch last 5 applied duty leaves and their status (within the last 24 hours)
    duty_leaves = db.session.query(
        DutyLeave.id, DutyLeave.date, DutyLeave.status, DutyLeave.time_slots, DutyLeave.remarks
    ).filter(
        DutyLeave.user_id == user.id,
        DutyLeave.date >= (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d')  # Filter by date
    ).order_by(
        DutyLeave.date.desc()
    ).limit(5).all()

    # Format important messages with DL status
    important_messages = []
    for dl in duty_leaves:
        message = f"Duty Leave ID: {dl.id} - Date: {dl.date} - Time Slots: {dl.time_slots} - Status: {dl.status}"
        if dl.remarks:
            message += f" - Remarks: {dl.remarks}"
        important_messages.append(message)

    # If no duty leaves applied in the last 24 hours, add a default message
    if not important_messages:
        important_messages.append("No duty leaves applied in the last 24 hours.")

    return render_template(
        'student_dashboard.html',
        name=user.name,
        uid=user.uid,
        participated_events=participated_events,
        important_messages=important_messages
    )

@app.route('/apply_duty_leave', methods=['GET', 'POST'])
def apply_duty_leave():
    if 'user_id' not in session:
        return redirect(url_for('login_student'))

    user_id = session['user_id']
    name = session['name']
    uid = session['uid']

    time_slots = [
        "09:30-10:20", "10:20-11:10", "11:20-12:10", "12:10-13:00",
        "13:05-13:55", "13:55-14:45", "14:45-15:35", "15:35-16:25", "9:30-4:25 (Full Day)"
    ]

    if request.method == 'POST':
        if 'event' in request.form:
            event_id = request.form['event']
            selected_slots = request.form.getlist('time_slots')

            if not selected_slots:
                flash("Please select at least one time slot.", "danger")
                return redirect(url_for('apply_duty_leave'))

            if "9:30-4:25 (Full Day)" in selected_slots:
                selected_slots = ["9:30-4:25 (Full Day)"]

            event = Event.query.get(event_id)
            if not event:
                flash("Invalid event selected.", "danger")
            else:
                event_start_time = event.start_time.strftime('%H:%M')
                event_end_time = event.end_time.strftime('%H:%M')

                valid_slots = True
                for slot in selected_slots:
                    if slot != "9:30-4:25 (Full Day)":
                        start, end = slot.split("-")
                        if not (event_start_time <= start <= event_end_time and event_start_time <= end <= event_end_time):
                            valid_slots = False
                            break

                if not valid_slots:
                    flash("Invalid time slot(s) selected for the event.", "danger")
                else:
                    unique_key = f"{uid}_{event_id}"

                    # Debugging: Print values before inserting
                    print(f"Inserting into duty_leave: {user_id}, {event_id}, {unique_key}, {name}, {uid}, {', '.join(selected_slots)}")

                    duty_leave = DutyLeave(
                        user_id=user_id,
                        date=event.date,
                        unique_key=unique_key,
                        status='Pending',
                        student_name=name,
                        student_uid=uid,
                        time_slots=", ".join(selected_slots),
                        event_id=event_id
                    )
                    db.session.add(duty_leave)
                    db.session.commit()
                    flash("Duty leave application submitted successfully.", "success")

        else:
            flash("Invalid request.", "danger")

    # Fetch applied duty leaves from the database for the logged-in user
    applied_leaves = db.session.query(
        DutyLeave.date,
        DutyLeave.time_slots,
        Event.event_name,
        DutyLeave.status,
        DutyLeave.remarks,
        DutyLeave.unique_key
    ).join(Event, DutyLeave.event_id == Event.id
    ).filter(DutyLeave.user_id == user_id
    ).all()

    # Debugging: Print applied leaves fetched from database
    print(f"Applied Leaves: {applied_leaves}")

    return render_template(
        'apply_duty_leave.html',
        time_slots=time_slots,
        applied_leaves=applied_leaves
    )

@app.route('/fetch-events', methods=['POST'])
def fetch_events():
    # Define the timezone you want to use (e.g., 'Asia/Kolkata')
    timezone = pytz.timezone('Asia/Kolkata')

    # Get the current datetime in the specified timezone
    current_datetime = datetime.now(timezone)

    # Format current date and time in the desired timezone
    current_date = current_datetime.strftime('%Y-%m-%d')  # Current date
    current_time = current_datetime.strftime('%H:%M:%S')  # Current time

    if request.is_json:
        data = request.get_json()
        date = data.get('date')

        print(f"Received date: {date}")  # Debugging

        if date < current_date:
            # Fetch all events if the date is in the past
            events = Event.query.filter_by(date=date).all()
        else:
            # Fetch only past events if the date is today
            events = Event.query.filter(
                Event.date == date,
                Event.end_time <= current_time
            ).all()

        # Format the events for the response
        events_data = [{
            "id": event.id,
            "name": event.event_name,
            "start_time": event.start_time.strftime('%H:%M:%S'),
            "end_time": event.end_time.strftime('%H:%M:%S')
        } for event in events]

        print(f"Fetched events: {events_data}")  # Debugging

        return jsonify({"events": events_data})

    return jsonify({"error": "Invalid request"}), 400

@app.route('/validate_duty_leave', methods=['GET', 'POST'])
def validate_duty_leave():
    if 'user_id' not in session or session['role'] != 'coordinator':
        return redirect(url_for('index'))

    if request.method == 'POST':
        if 'date' in request.form:  # First form submission: Fetch events
            date = request.form['date']
            print(f"Received date: {date}")

            # Fetch events for the given date
            events = Event.query.filter_by(date=date).all()

            # Convert events to a list of dictionaries
            event_list = [{"id": event.id, "name": event.event_name, "start_time": event.start_time.strftime('%H:%M'), "end_time": event.end_time.strftime('%H:%M')} for event in events]
            print(f"Fetched events: {event_list}")

            if events:
                return jsonify({"events": event_list})
            else:
                return jsonify({"events": []})

        elif 'event' in request.form:  # Second form submission: Validate leaves
            event_id = request.form['event']
            print(f"Selected Event ID: {event_id}")

            # Fetch attendance data for the event
            attendance_data = db.session.query(
                EventRegistration.user_id,
                EventRegistration.attendance,
                User.name,
                User.uid
            ).join(User, EventRegistration.user_id == User.id
            ).filter(EventRegistration.event_id == event_id
            ).all()
            print(f"Fetched Attendance Data: {attendance_data}")

            # Fetch duty leave applications for the selected event
            event = Event.query.get(event_id)
            duty_leaves = DutyLeave.query.filter_by(event_id=event_id, date=event.date).all()
            print(f"Fetched Duty Leave Applications: {duty_leaves}")

            # Create maps for quick lookup
            attendance_map = {f"{row.uid}_{row.name}": row.attendance for row in attendance_data}  # UID_name as key, attendance as value
            duty_leave_map = {f"{leave.student_uid}_{leave.student_name}": leave for leave in duty_leaves}  # UID_name as key
            print(f"Attendance Map: {attendance_map}")
            print(f"Duty Leave Map: {duty_leave_map}")

            # Initialize results
            to_grant = []
            to_deny = []

            # Process duty leave applications
            for leave in duty_leaves:
                key = f"{leave.student_uid}_{leave.student_name}"  # Consistent key format
                attendance_status = attendance_map.get(key, "Not Marked")
                print(f"Processing Leave ID: {leave.id}, Key: {key}, Attendance Status: {attendance_status}")

                if attendance_status == "Present":
                    to_grant.append(leave.id)
                else:
                    to_deny.append((leave.id, "Registered for the event but not present"))

            # Update duty leave statuses in the database
            for leave_id in to_grant:
                leave = DutyLeave.query.get(leave_id)
                leave.status = 'Granted'
                leave.remarks = None

            for leave_id, remark in to_deny:
                leave = DutyLeave.query.get(leave_id)
                leave.status = 'Denied'
                leave.remarks = remark

            db.session.commit()
            print(f"To Grant: {to_grant}")
            print(f"To Deny: {to_deny}")
            print("Database updated successfully.")
            flash("Duty leave applications validated successfully!", "success")
            return redirect(url_for('coordinator_dashboard'))

    return render_template('validate_duty_leave.html')



@app.route('/join_event', methods=['GET', 'POST'])
def join_event():
    if 'user_id' not in session:
        return redirect(url_for('login_student'))

    user_id = session['user_id']
    events = db.session.query(
        Event.id, Event.event_name, Event.event_type, Event.venue,
        Event.start_time, Event.end_time, Event.date,
        Event.max_students, Event.registration_count,
        EventRegistration.id.label("reg_id")
    ).outerjoin(
        EventRegistration, (Event.id == EventRegistration.event_id) & (EventRegistration.user_id == user_id)
    ).all()

    past_events, live_events, upcoming_events, participated_events = [], [], [], []

    # Define the timezone you want to use (e.g., 'Asia/Kolkata')
    timezone = pytz.timezone('Asia/Kolkata')

    # Get the current datetime in the specified timezone
    current_datetime = datetime.now(timezone)

    for event in events:
        event_data = {
            "id": event.id,
            "name": event.event_name,
            "type": event.event_type,
            "venue": event.venue,
            "timings": f"{event.start_time} - {event.end_time}",
            "date": event.date,
            "max_students": event.max_students,
            "registration_count": event.registration_count,
        }

        # Parse event date and times
        event_date = datetime.strptime(event.date, '%Y-%m-%d').date()
        start_time = event.start_time  # Use directly
        end_time = event.end_time  # Use directly

        # Combine date and time to create datetime objects
        event_start_datetime = timezone.localize(datetime.combine(event_date, start_time))
        event_end_datetime = timezone.localize(datetime.combine(event_date, end_time))

        # Check if the user has registered for the event
        registered = event.reg_id is not None

        # Categorize the event based on its timing and registration status
        if registered:
            if current_datetime > event_end_datetime:
                past_events.append(event_data)  # Event has ended
            elif event_start_datetime <= current_datetime <= event_end_datetime:
                live_events.append(event_data)  # Event is ongoing
            else:
                participated_events.append(event_data)  # Event is in the future
        else:
            if current_datetime < event_start_datetime:
                upcoming_events.append(event_data)  # Event is in the future

    return render_template(
        'join_event.html',
        upcoming_events=upcoming_events,
        live_events=live_events,
        past_events=past_events,
        participated_events=participated_events
    )



@app.route('/register_event/<int:event_id>', methods=['POST'])
def register_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login_student'))

    user_id = session['user_id']
    event = Event.query.filter_by(id=event_id).first()

    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for('join_event'))

    if event.registration_count >= event.max_students:
        flash("Event is full. Unable to register.", "danger")
        return redirect(url_for('join_event'))

    try:
        registration = EventRegistration(event_id=event_id, user_id=user_id)
        event.registration_count += 1
        db.session.add(registration)
        db.session.commit()
        flash("Successfully registered for the event!", "success")
    except Exception:
        db.session.rollback()
        flash("An error occurred during registration. Please try again.", "danger")

    return redirect(url_for('join_event'))



@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if 'user_id' not in session or session['role'] != 'coordinator':
        return redirect(url_for('index'))

    if request.method == 'POST':
        event_name = request.form['event_name']
        event_date = request.form['date']

        # Check if an event with the same name and date already exists
        existing_event = Event.query.filter_by(event_name=event_name, date=event_date).first()

        if existing_event:
            flash("An event with the same name and date already exists.", "danger")
            return redirect(url_for('create_event'))

        # If no duplicate event exists, create the new event
        event = Event(
            event_name=event_name,
            event_type=request.form['event_type'],
            venue=request.form['venue'],
            start_time=request.form['start_time'],
            end_time=request.form['end_time'],
            date=event_date,
            max_students=int(request.form['max_students']),
            coordinator_id=session['user_id']
        )
        db.session.add(event)
        db.session.commit()

        flash("Event created successfully!", "success")
        return redirect(url_for('coordinator_dashboard'))
    
    return render_template('create_event.html')



@app.route('/coordinator_dashboard')
def coordinator_dashboard():
    if 'user_id' not in session or session['role'] != 'coordinator':
        return redirect(url_for('index'))

    tz = pytz.timezone('Asia/Kolkata')
    current_date = datetime.now(tz).date()
    current_time = datetime.now(tz).time()

    created_events = Event.query.filter_by(coordinator_id=session['user_id']).all()
    scheduled_events, live_events, past_events = [], [], []

    for event in created_events:
        event_date = datetime.strptime(event.date, '%Y-%m-%d').date()
        start_time = event.start_time  # ✅ Use directly
        end_time = event.end_time  # ✅ Use directly

        event_data = {
            "id": event.id,
            "name": event.event_name,
            "event_type": event.event_type,
            "venue": event.venue,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "date": event.date,
            "max_students": event.max_students,
            "registration_count": event.registration_count
        }

        if event_date == current_date and start_time <= current_time < end_time:
            live_events.append(event_data)
        elif event_date < current_date or (event_date == current_date and current_time >= end_time):
            past_events.append(event_data)
        else:
            scheduled_events.append(event_data)

    return render_template('coordinator_dashboard.html', scheduled_events=scheduled_events, live_events=live_events, past_events=past_events)


@app.route('/view_event_registrations/<int:event_id>')
def view_event_registrations(event_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    event = Event.query.get(event_id)

    if not event:  # ✅ Check if event exists
        flash("Event not found.", "danger")
        return redirect(url_for('coordinator_dashboard'))

    registrations = db.session.query(User.name, User.uid).join(
        EventRegistration, User.id == EventRegistration.user_id
    ).filter(EventRegistration.event_id == event_id).all()

    return render_template('view_event_registrations.html', registrations=registrations, event_name=event.event_name, event_id=event_id)

@app.route('/mark_attendance/<int:event_id>', methods=['GET', 'POST'])
def mark_attendance(event_id):
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login_coordinator'))
    
    # Fetch event name
    event = Event.query.get(event_id)
    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('index'))
    event_name = event.event_name

    # Fetch registrations along with their attendance for the specified event
    registrations = db.session.query(
        User.name,
        User.uid,
        EventRegistration.id.label('registration_id'),
        db.func.coalesce(EventRegistration.attendance, 'Not Marked').label('attendance')
    ).join(EventRegistration, User.id == EventRegistration.user_id
    ).filter(EventRegistration.event_id == event_id
    ).all()

    if request.method == 'POST':
        attendance_data = request.form.getlist('attendance')

        for item in attendance_data:
            try:
                registration_id, status = item.split('-')
                registration_id = int(registration_id)
            except ValueError:
                flash('Invalid form submission.', 'danger')
                return redirect(url_for('mark_attendance', event_id=event_id))
            
            if status not in ['Present', 'Absent', 'Not Marked']:
                flash('Invalid attendance status.', 'danger')
                return redirect(url_for('mark_attendance', event_id=event_id))
            
            # Update attendance in the database
            registration = EventRegistration.query.get(registration_id)
            if registration:
                registration.attendance = status
                registration.last_updated_by = session['user_id']
                registration.last_updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Attendance updated successfully.', 'success')
        return redirect(url_for('mark_attendance', event_id=event_id))

    return render_template('mark_attendance.html', 
                           registrations=registrations, 
                           event_name=event_name, 
                           event_id=event_id)


@app.route('/view_attendance/<int:event_id>', methods=['GET', 'POST'])
def view_attendance(event_id):
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('index'))

    # Fetch event name
    event = Event.query.get(event_id)
    if not event:
        return "Event not found", 404
    event_name = event.event_name

    # Fetch registrations along with their attendance for the specified event
    registrations = db.session.query(
        User.name,
        User.uid,
        EventRegistration.id.label('registration_id'),
        db.func.coalesce(EventRegistration.attendance, 'Not Marked').label('attendance')
    ).join(EventRegistration, User.id == EventRegistration.user_id
    ).filter(EventRegistration.event_id == event_id
    ).all()

    if request.method == 'POST':
        # Handle attendance updates
        updates = request.form.getlist('attendance')
        for update in updates:
            registration_id, status = update.split('-')
            registration = EventRegistration.query.get(registration_id)
            if registration:
                registration.attendance = status
                registration.last_updated_by = session['user_id']
                registration.last_updated_at = datetime.utcnow()
        
        db.session.commit()
        return redirect(url_for('view_attendance', event_id=event_id))

    return render_template('view_attendance.html', 
                           registrations=registrations, 
                           event_name=event_name, 
                           event_id=event_id)


@app.route('/download_registrations/<int:event_id>')
def download_registrations(event_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    event = Event.query.get(event_id)
    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for('coordinator_dashboard'))

    registrations = db.session.query(User.name, User.uid).join(EventRegistration, User.id == EventRegistration.user_id).filter(EventRegistration.event_id == event_id).all()
    df = pd.DataFrame(registrations, columns=['Name', 'User ID'])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Registrations', startrow=1)
        workbook = writer.book
        worksheet = writer.sheets['Registrations']
        worksheet.merge_cells('A1:B1')
        worksheet.cell(row=1, column=1, value=event.event_name).alignment = Alignment(horizontal='center', vertical='center')
        for col in worksheet.columns:
            max_length = 0
            column_letter = col[0].column
            for cell in col:
                if not isinstance(cell, openpyxl.cell.cell.MergedCell):
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
            adjusted_width = max_length + 2
            worksheet.column_dimensions[openpyxl.utils.get_column_letter(column_letter)].width = adjusted_width
    
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f'{event.event_name}_registrations.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/download_attendance/<int:event_id>')
def download_attendance(event_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    event = Event.query.get(event_id)
    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for('coordinator_dashboard'))

    registrations = db.session.query(User.name, User.uid, EventRegistration.attendance).join(EventRegistration, User.id == EventRegistration.user_id).filter(EventRegistration.event_id == event_id).all()
    df = pd.DataFrame(registrations, columns=['Name', 'UID', 'Attendance_Status'])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance', startrow=2, header=False)
        worksheet = writer.sheets['Attendance']
        worksheet.merge_cells('A1:C1')
        worksheet.cell(row=1, column=1, value=f"Event name: {event.event_name}").alignment = Alignment(horizontal='center')
        headers = ['Name', 'UID', 'Attendance_Status']
        for col_num, header in enumerate(headers, 1):
            worksheet.cell(row=2, column=col_num).value = header
        for col_num, column_cells in enumerate(worksheet.columns, 1):
            column_letter = openpyxl.utils.get_column_letter(col_num)
            max_length = max(len(str(cell.value)) for cell in column_cells if cell.value is not None)
            adjusted_width = max_length + 2
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f'{event.event_name}_Attendance.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')



# Route for About Us page
@app.route('/about_us')
def about_us():
    return render_template('about_us.html')

@app.route('/contact_us', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        # Validate form data
        if not name or not email or not message:
            flash("Please fill out all fields.", "danger")
            return redirect(url_for('contact_us'))

        # Validate email format (basic check)
        if "@" not in email or "." not in email:
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for('contact_us'))

        # Save the message to the database
        try:
            new_message = ContactMessage(name=name, email=email, message=message)
            db.session.add(new_message)
            db.session.commit()
            flash("Thank you for your message! We'll get back to you shortly.", "success")
        except Exception as e:
            db.session.rollback()
            flash("An error occurred while submitting your message. Please try again.", "danger")

        return redirect(url_for('contact_us'))

    # For GET requests, render the contact form
    return render_template('contact_us.html')

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))
    

if __name__ == '__main__':
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.get_table_names():  # Check if tables exist
            db.create_all()
            print("Tables created successfully")
        else:
            print("Tables already exist, skipping creation.")
    app.run(debug=True)
