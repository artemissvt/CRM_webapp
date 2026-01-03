from flask import Flask, request, render_template, flash, session, redirect
import sqlite3 
import hashlib 
from functools import wraps

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = "akjdsbkjas&^absdjkajbdkasbdksajbdksadbkbj"


def roles_permitted(roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'uid' in session and session['role'] in roles:
                return f(*args, **kwargs)
            else:
                flash(f'ERROR: you need {roles} role to access this page')
                return redirect('/login')
        return wrapper
    return decorator

def get_db_conn():
    db = sqlite3.connect('task_manager.db')
    db.row_factory = sqlite3.Row
    return db 


def initialize_db():
    db = get_db_conn()
    cursor = db.cursor() 

    cursor.execute("PRAGMA foreign_keys=ON")

    # Users table
    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL, 
                        password TEXT NOT NULL,
                        role TEXT DEFAULT 'member',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                   """)
    
    # Projects table 
    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,  
                        user_id INTEGER NOT NULL, 
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                   """)
    
    # Tasks table 
    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT, 
                        project_id INTEGER NOT NULL,
                        completed INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES projects (id)
                    )        
                   """)
    
    db.commit()
    db.close()


def hash_password(username, password):
    pw = username + password
    hashed = hashlib.sha512(pw.encode('utf-8')).hexdigest()
    return hashed


@app.route('/')
def home():
    return "HOME PAGE"


@app.route('/register', methods=[ 'GET', 'POST' ])
def register():
    username = ''
    db = get_db_conn()
    cursor = db.cursor()
    if request.method == 'POST':
        # return(f"{request.form['username']} {request.form['password']} {request.form['password2']}")
        username = request.form['username']
        password = request.form['password']
        password2 = request.form['password2']
        if password != password2:
            flash("ERROR: Passwords do not match")
            return render_template('register_form.html', username=username)
        else:
            user = cursor.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if user:
                flash("ERROR: Username is taken")
                return render_template('register_form.html', username=username)
            else: 
                hashed_password = hash_password(username, password)
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                               (username, hashed_password))
                db.commit()
                return redirect('/login')
    else:
        return render_template('register_form.html', username=username)


@app.route('/login', methods=[ 'GET', 'POST' ])
def login():
    username = ''
    db = get_db_conn()
    cursor = db.cursor()
    if request.method == 'POST':
        form = request.form
        username = form['username']
        password = form['password']
        user = cursor.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user:
            hashed_password = hash_password(username, password)
            if user['password'] == hashed_password:
                session['uid'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                if user['role'] == 'employee':
                    return redirect('/employee')
                elif user['role'] == 'admin':
                    return redirect('/admin')
                elif user['role'] == 'manager':
                    return redirect('/manager')
            else:
                flash('ERROR: wrong credentials')
                return render_template('login_form.html', username=username)
        else:
            flash('ERROR: username not found')
            return render_template('login_form.html', username=username)
    else: 
        return render_template('login_form.html', username=username)



@app.route('/employee')
@roles_permitted(['employee'])
def employee_dashboard():
    stats = {
        "added_week": 3,
        "added_month": 10,
        "added_total": 60,
        "contacted_today": 5,
        "contacted_week": 25,
        "contacted_month": 45,
    }
    return render_template('employee_dashboard.html', stats=stats)

@app.route('/employee/customers')
@roles_permitted(['employee'])
def employee_view_cus():
    stats = {
        "cus_name": "Example company co",
        "contact_per": "Mr John Doe",
        "email": "examplco@gmail.com",
        "contact_phone": "+30 210 9999999",
        "address": "Vassilisis Amalias 38, Athens 105 58",
        "website": "examplecomco.com",
        "last_contact": "29/10/2025",
        "next_contact": "5/11/2025",
        "notes": "Any notes the employee might have",
        "cus_type": "Lead",
        "industry": "Retail",
        "rev_value": "2.000.000€",
        "date_added": "28/10/2025",
        "added_by": "Luke Danes"

    }
    return render_template('employee_view_cus.html', stats = stats)

@app.route('/employee/customers/<int:customer_id>/contacts/new', methods=['GET', 'POST'])
@roles_permitted(['employee'])
def employee_add_contact(customer_id):
    if request.method == 'POST':
        contacted_at = request.form.get('contacted_at', '').strip()
        contact_type = request.form.get('contact_type', '').strip()
        summary = request.form.get('summary', '').strip()
        notes = request.form.get('notes', '').strip()
        next_contact_at = request.form.get('next_contact_at', '').strip()

        # Basic validation (server-side)
        if not contacted_at or not contact_type or not summary:
            flash("ERROR: Please fill Contact date, Contact type, and Summary.")
            return render_template('employee_add_contact.html', customer_id=customer_id)

        db = get_db_conn()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO customer_contacts
            (customer_id, contacted_at, contact_type, summary, notes, next_contact_at, created_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            customer_id,
            contacted_at,
            contact_type,
            summary,
            notes if notes else None,
            next_contact_at if next_contact_at else None,
            session.get('uid')
        ))

        db.commit()

        return redirect(url_for('employee_view_cus', customer_id=customer_id))

    return render_template('employee_add_contact.html', customer_id=customer_id)

@app.route('/manager')
@roles_permitted(['manager'])
def manager_dashboard():
    #temp list 
    stats = {
    "lead": 206,
    "active": 568,
    "inactive": 126,
    "cancelled": 74
}
    return render_template("manager_dashboard.html", stats=stats)

@app.route('/manager/viewemplo')
@roles_permitted(['manager'])
def manager_view_emplo():
    #temp list 
    stats = {
    "lead": 206,
    "active": 568,
    "inactive": 126,
    "cancelled": 74
}
    return render_template("manager_view_emplo.html", stats=stats)

@app.route('/manager/viewcus')
@roles_permitted(['manager'])
def manager_view_cus():
    #temp list 
    stats = {
    "lead": 206,
    "active": 568,
    "inactive": 126,
    "cancelled": 74
}
    return render_template("manager_view_cus.html", stats=stats)

@app.route('/admin')
@roles_permitted(['admin'])
def admin_dashboard():
    # Temporary demo list
    users = [
        {"name": "Dean Forester", "role": "Employee", "email": "dforester@ourco.com", "status": "Active"},
        {"name": "Skyler White", "role": "Employee", "email": "skylerwh@ourco.com", "status": "Active"},
        {"name": "Susan Collins", "role": "Manager", "email": "susancollins@ourco.com", "status": "Inactive"},
        {"name": "Kimberley Chambers", "role": "Admin", "email": "kimbchamb@ourco.com", "status": "Active"},
    ]
    return render_template("admin_dashboard.html", users=users)


    
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/add/task', methods=[ 'GET', 'POST' ])
@roles_permitted(['employee'])
def add_task():
    if request.method == 'POST':
        pass
    else:
        return render_template('add_task.html')



@app.route('/add/project', methods=[ 'GET', 'POST' ])
@roles_permitted(['employee'])
def add_project():
    db = get_db_conn()
    cursor = db.cursor() 
    if request.method == 'POST':
        form = request.form
        name = form['project_name']
        descr = form['project_descr'] 
        cursor.execute("INSERT INTO projects (name, description, user_id) VALUES (?,?,?)",
                        (name, descr, session['uid']))
        db.commit()
        return redirect('/projects')
    else:
        return render_template('add_project.html')
    

if __name__ == '__main__':
    initialize_db()
    app.run(debug=True)