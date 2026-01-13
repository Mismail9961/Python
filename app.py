from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = 'change-this-secret-key-in-production'

def get_database():
    connection = sqlite3.connect('clinic.db')
    connection.row_factory = sqlite3.Row
    return connection

def create_tables():
    connection = sqlite3.connect('clinic.db')
    cursor = connection.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  phone TEXT,
                  is_admin INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS doctors
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  specialization TEXT NOT NULL,
                  qualifications TEXT,
                  experience INTEGER,
                  email TEXT,
                  phone TEXT,
                  available INTEGER DEFAULT 1,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS appointments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  patient_id INTEGER NOT NULL,
                  doctor_id INTEGER NOT NULL,
                  appointment_date DATE NOT NULL,
                  appointment_time TEXT NOT NULL,
                  status TEXT DEFAULT 'pending',
                  notes TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (patient_id) REFERENCES users(id),
                  FOREIGN KEY (doctor_id) REFERENCES doctors(id))''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS doctor_schedules
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  doctor_id INTEGER NOT NULL,
                  day_of_week TEXT NOT NULL,
                  start_time TEXT NOT NULL,
                  end_time TEXT NOT NULL,
                  FOREIGN KEY (doctor_id) REFERENCES doctors(id))''')
    
    cursor.execute("SELECT * FROM users WHERE email = 'admin@clinic.com'")
    admin_exists = cursor.fetchone()
    
    if not admin_exists:
        admin_password = generate_password_hash('admin123')
        cursor.execute("INSERT INTO users (name, email, password, is_admin) VALUES (?, ?, ?, ?)",
                  ('Admin User', 'admin@clinic.com', admin_password, 1))
    
    cursor.execute("SELECT COUNT(*) FROM doctors")
    doctor_count = cursor.fetchone()[0]
    
    if doctor_count == 0:
        sample_doctors = [
            ('Dr. Sarah Johnson', 'Cardiology', 'MD, FACC', 15, 'sarah.j@clinic.com', '555-0101'),
            ('Dr. Michael Chen', 'Pediatrics', 'MD, FAAP', 12, 'michael.c@clinic.com', '555-0102'),
            ('Dr. Emily Williams', 'Dermatology', 'MD, FAAD', 10, 'emily.w@clinic.com', '555-0103'),
            ('Dr. James Davis', 'Orthopedics', 'MD, FAAOS', 18, 'james.d@clinic.com', '555-0104'),
            ('Dr. Lisa Anderson', 'General Medicine', 'MD', 8, 'lisa.a@clinic.com', '555-0105')
        ]
        
        for doctor in sample_doctors:
            cursor.execute("INSERT INTO doctors (name, specialization, qualifications, experience, email, phone) VALUES (?, ?, ?, ?, ?, ?)", doctor)
        
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        for doctor_id in range(1, 6):
            for day in weekdays:
                cursor.execute("INSERT INTO doctor_schedules (doctor_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)",
                          (doctor_id, day, '09:00', '17:00'))
    
    connection.commit()
    connection.close()

def check_login(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return function(*args, **kwargs)
    return wrapper

def check_admin(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Admin access required', 'error')
            return redirect(url_for('index'))
        return function(*args, **kwargs)
    return wrapper

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        
        connection = get_database()
        cursor = connection.cursor()
        
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            flash('Email already registered', 'error')
            connection.close()
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO users (name, email, password, phone) VALUES (?, ?, ?, ?)",
                  (name, email, hashed_password, phone))
        connection.commit()
        connection.close()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        connection = get_database()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        connection.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['is_admin'] = user['is_admin']
            
            if user['is_admin']:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('patient_dashboard'))
        
        flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/patient/dashboard')
@check_login
def patient_dashboard():
    connection = get_database()
    cursor = connection.cursor()
    
    cursor.execute("""SELECT a.*, d.name as doctor_name, d.specialization 
                 FROM appointments a 
                 JOIN doctors d ON a.doctor_id = d.id 
                 WHERE a.patient_id = ? 
                 ORDER BY a.appointment_date DESC, a.appointment_time DESC""", 
              (session['user_id'],))
    appointments = cursor.fetchall()
    connection.close()
    
    return render_template('patient_dashboard.html', appointments=appointments)

@app.route('/doctors')
@check_login
def doctors():
    search = request.args.get('search', '')
    specialty = request.args.get('specialty', '')
    
    connection = get_database()
    cursor = connection.cursor()
    
    query = "SELECT * FROM doctors WHERE available = 1"
    params = []
    
    if search:
        query += " AND (name LIKE ? OR specialization LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    if specialty:
        query += " AND specialization = ?"
        params.append(specialty)
    
    cursor.execute(query, params)
    doctors_list = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT specialization FROM doctors WHERE available = 1 ORDER BY specialization")
    specialties = cursor.fetchall()
    
    connection.close()
    
    return render_template('doctors.html', doctors=doctors_list, specialties=specialties)

@app.route('/book/<int:doctor_id>', methods=['GET', 'POST'])
@check_login
def book_appointment(doctor_id):
    connection = get_database()
    cursor = connection.cursor()
    
    if request.method == 'POST':
        appointment_date = request.form['date']
        appointment_time = request.form['time']
        notes = request.form.get('notes', '')
        
        cursor.execute("""SELECT * FROM appointments 
                     WHERE doctor_id = ? AND appointment_date = ? AND appointment_time = ? 
                     AND status != 'cancelled'""", 
                  (doctor_id, appointment_date, appointment_time))
        
        existing_appointment = cursor.fetchone()
        
        if existing_appointment:
            flash('This time slot is already booked', 'error')
        else:
            cursor.execute("""INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, notes) 
                         VALUES (?, ?, ?, ?, ?)""",
                      (session['user_id'], doctor_id, appointment_date, appointment_time, notes))
            connection.commit()
            flash('Appointment booked successfully!', 'success')
            connection.close()
            return redirect(url_for('patient_dashboard'))
    
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    
    cursor.execute("SELECT * FROM doctor_schedules WHERE doctor_id = ?", (doctor_id,))
    schedules = cursor.fetchall()
    
    connection.close()
    
    return render_template('book_appointment.html', doctor=doctor, schedules=schedules)

@app.route('/appointment/cancel/<int:appointment_id>')
@check_login
def cancel_appointment(appointment_id):
    connection = get_database()
    cursor = connection.cursor()
    
    cursor.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ? AND patient_id = ?", 
              (appointment_id, session['user_id']))
    connection.commit()
    connection.close()
    
    flash('Appointment cancelled successfully', 'success')
    return redirect(url_for('patient_dashboard'))

@app.route('/admin/dashboard')
@check_admin
def admin_dashboard():
    connection = get_database()
    cursor = connection.cursor()
    
    cursor.execute("""SELECT a.*, u.name as patient_name, u.email as patient_email, 
                 d.name as doctor_name, d.specialization 
                 FROM appointments a 
                 JOIN users u ON a.patient_id = u.id 
                 JOIN doctors d ON a.doctor_id = d.id 
                 ORDER BY a.appointment_date DESC, a.appointment_time DESC""")
    appointments = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as total FROM appointments WHERE status = 'pending'")
    pending_count = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM doctors WHERE available = 1")
    doctors_count = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE is_admin = 0")
    patients_count = cursor.fetchone()['total']
    
    connection.close()
    
    return render_template('admin_dashboard.html', 
                          appointments=appointments,
                          pending_count=pending_count,
                          doctors_count=doctors_count,
                          patients_count=patients_count)

@app.route('/admin/appointment/update/<int:appointment_id>/<status>')
@check_admin
def update_appointment_status(appointment_id, status):
    connection = get_database()
    cursor = connection.cursor()
    
    cursor.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id))
    connection.commit()
    connection.close()
    
    flash(f'Appointment {status} successfully', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/doctors')
@check_admin
def manage_doctors():
    connection = get_database()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM doctors ORDER BY name")
    doctors_list = cursor.fetchall()
    connection.close()
    
    return render_template('manage_doctors.html', doctors=doctors_list)

@app.route('/admin/doctor/add', methods=['GET', 'POST'])
@check_admin
def add_doctor():
    if request.method == 'POST':
        name = request.form['name']
        specialization = request.form['specialization']
        qualifications = request.form['qualifications']
        experience = request.form['experience']
        email = request.form['email']
        phone = request.form['phone']
        
        connection = get_database()
        cursor = connection.cursor()
        cursor.execute("""INSERT INTO doctors (name, specialization, qualifications, experience, email, phone) 
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (name, specialization, qualifications, experience, email, phone))
        connection.commit()
        connection.close()
        
        flash('Doctor added successfully', 'success')
        return redirect(url_for('manage_doctors'))
    
    return render_template('add_doctor.html')

@app.route('/admin/doctor/toggle/<int:doctor_id>')
@check_admin
def toggle_doctor_availability(doctor_id):
    connection = get_database()
    cursor = connection.cursor()
    cursor.execute("UPDATE doctors SET available = NOT available WHERE id = ?", (doctor_id,))
    connection.commit()
    connection.close()
    
    flash('Doctor availability updated', 'success')
    return redirect(url_for('manage_doctors'))

if __name__ == '__main__':
    create_tables()
    app.run(debug=True)