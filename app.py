from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# Database initialization
def init_db():
    conn = sqlite3.connect('clinic.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  phone TEXT,
                  is_admin INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Doctors table
    c.execute('''CREATE TABLE IF NOT EXISTS doctors
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  specialization TEXT NOT NULL,
                  qualifications TEXT,
                  experience INTEGER,
                  email TEXT,
                  phone TEXT,
                  available INTEGER DEFAULT 1,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Appointments table
    c.execute('''CREATE TABLE IF NOT EXISTS appointments
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
    
    # Doctor schedules table
    c.execute('''CREATE TABLE IF NOT EXISTS doctor_schedules
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  doctor_id INTEGER NOT NULL,
                  day_of_week TEXT NOT NULL,
                  start_time TEXT NOT NULL,
                  end_time TEXT NOT NULL,
                  FOREIGN KEY (doctor_id) REFERENCES doctors(id))''')
    
    # Create default admin if not exists
    c.execute("SELECT * FROM users WHERE email = 'admin@clinic.com'")
    if not c.fetchone():
        admin_password = generate_password_hash('admin123')
        c.execute("INSERT INTO users (name, email, password, is_admin) VALUES (?, ?, ?, ?)",
                  ('Admin User', 'admin@clinic.com', admin_password, 1))
    
    # Add sample doctors if table is empty
    c.execute("SELECT COUNT(*) FROM doctors")
    if c.fetchone()[0] == 0:
        sample_doctors = [
            ('Dr. Sarah Johnson', 'Cardiology', 'MD, FACC', 15, 'sarah.j@clinic.com', '555-0101'),
            ('Dr. Michael Chen', 'Pediatrics', 'MD, FAAP', 12, 'michael.c@clinic.com', '555-0102'),
            ('Dr. Emily Williams', 'Dermatology', 'MD, FAAD', 10, 'emily.w@clinic.com', '555-0103'),
            ('Dr. James Davis', 'Orthopedics', 'MD, FAAOS', 18, 'james.d@clinic.com', '555-0104'),
            ('Dr. Lisa Anderson', 'General Medicine', 'MD', 8, 'lisa.a@clinic.com', '555-0105')
        ]
        c.executemany("INSERT INTO doctors (name, specialization, qualifications, experience, email, phone) VALUES (?, ?, ?, ?, ?, ?)",
                      sample_doctors)
        
        # Add schedules for sample doctors
        for doctor_id in range(1, 6):
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                c.execute("INSERT INTO doctor_schedules (doctor_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)",
                          (doctor_id, day, '09:00', '17:00'))
    
    conn.commit()
    conn.close()

# Helper functions
def get_db():
    conn = sqlite3.connect('clinic.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Admin access required', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
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
        
        conn = get_db()
        c = conn.cursor()
        
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        if c.fetchone():
            flash('Email already registered', 'error')
            conn.close()
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        c.execute("INSERT INTO users (name, email, password, phone) VALUES (?, ?, ?, ?)",
                  (name, email, hashed_password, phone))
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()
        
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
@login_required
def patient_dashboard():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""SELECT a.*, d.name as doctor_name, d.specialization 
                 FROM appointments a 
                 JOIN doctors d ON a.doctor_id = d.id 
                 WHERE a.patient_id = ? 
                 ORDER BY a.appointment_date DESC, a.appointment_time DESC""", 
              (session['user_id'],))
    appointments = c.fetchall()
    conn.close()
    
    return render_template('patient_dashboard.html', appointments=appointments)

@app.route('/doctors')
@login_required
def doctors():
    search = request.args.get('search', '')
    specialty = request.args.get('specialty', '')
    
    conn = get_db()
    c = conn.cursor()
    
    query = "SELECT * FROM doctors WHERE available = 1"
    params = []
    
    if search:
        query += " AND (name LIKE ? OR specialization LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    if specialty:
        query += " AND specialization = ?"
        params.append(specialty)
    
    c.execute(query, params)
    doctors_list = c.fetchall()
    
    c.execute("SELECT DISTINCT specialization FROM doctors WHERE available = 1 ORDER BY specialization")
    specialties = c.fetchall()
    
    conn.close()
    
    return render_template('doctors.html', doctors=doctors_list, specialties=specialties)

@app.route('/book/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def book_appointment(doctor_id):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        appointment_date = request.form['date']
        appointment_time = request.form['time']
        notes = request.form.get('notes', '')
        
        # Check if slot is available
        c.execute("""SELECT * FROM appointments 
                     WHERE doctor_id = ? AND appointment_date = ? AND appointment_time = ? 
                     AND status != 'cancelled'""", 
                  (doctor_id, appointment_date, appointment_time))
        
        if c.fetchone():
            flash('This time slot is already booked', 'error')
        else:
            c.execute("""INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, notes) 
                         VALUES (?, ?, ?, ?, ?)""",
                      (session['user_id'], doctor_id, appointment_date, appointment_time, notes))
            conn.commit()
            flash('Appointment booked successfully!', 'success')
            conn.close()
            return redirect(url_for('patient_dashboard'))
    
    c.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = c.fetchone()
    
    c.execute("SELECT * FROM doctor_schedules WHERE doctor_id = ?", (doctor_id,))
    schedules = c.fetchall()
    
    conn.close()
    
    return render_template('book_appointment.html', doctor=doctor, schedules=schedules)

@app.route('/appointment/cancel/<int:appointment_id>')
@login_required
def cancel_appointment(appointment_id):
    conn = get_db()
    c = conn.cursor()
    
    c.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ? AND patient_id = ?", 
              (appointment_id, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Appointment cancelled successfully', 'success')
    return redirect(url_for('patient_dashboard'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""SELECT a.*, u.name as patient_name, u.email as patient_email, 
                 d.name as doctor_name, d.specialization 
                 FROM appointments a 
                 JOIN users u ON a.patient_id = u.id 
                 JOIN doctors d ON a.doctor_id = d.id 
                 ORDER BY a.appointment_date DESC, a.appointment_time DESC""")
    appointments = c.fetchall()
    
    c.execute("SELECT COUNT(*) as total FROM appointments WHERE status = 'pending'")
    pending_count = c.fetchone()['total']
    
    c.execute("SELECT COUNT(*) as total FROM doctors WHERE available = 1")
    doctors_count = c.fetchone()['total']
    
    c.execute("SELECT COUNT(*) as total FROM users WHERE is_admin = 0")
    patients_count = c.fetchone()['total']
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                          appointments=appointments,
                          pending_count=pending_count,
                          doctors_count=doctors_count,
                          patients_count=patients_count)

@app.route('/admin/appointment/update/<int:appointment_id>/<status>')
@admin_required
def update_appointment_status(appointment_id, status):
    conn = get_db()
    c = conn.cursor()
    
    c.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id))
    conn.commit()
    conn.close()
    
    flash(f'Appointment {status} successfully', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/doctors')
@admin_required
def manage_doctors():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM doctors ORDER BY name")
    doctors_list = c.fetchall()
    conn.close()
    
    return render_template('manage_doctors.html', doctors=doctors_list)

@app.route('/admin/doctor/add', methods=['GET', 'POST'])
@admin_required
def add_doctor():
    if request.method == 'POST':
        name = request.form['name']
        specialization = request.form['specialization']
        qualifications = request.form['qualifications']
        experience = request.form['experience']
        email = request.form['email']
        phone = request.form['phone']
        
        conn = get_db()
        c = conn.cursor()
        c.execute("""INSERT INTO doctors (name, specialization, qualifications, experience, email, phone) 
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (name, specialization, qualifications, experience, email, phone))
        conn.commit()
        conn.close()
        
        flash('Doctor added successfully', 'success')
        return redirect(url_for('manage_doctors'))
    
    return render_template('add_doctor.html')

@app.route('/admin/doctor/toggle/<int:doctor_id>')
@admin_required
def toggle_doctor_availability(doctor_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE doctors SET available = NOT available WHERE id = ?", (doctor_id,))
    conn.commit()
    conn.close()
    
    flash('Doctor availability updated', 'success')
    return redirect(url_for('manage_doctors'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)