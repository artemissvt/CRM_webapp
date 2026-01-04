from flask import Flask, request, render_template, flash, session, redirect
import sqlite3 
import hashlib 
from functools import wraps

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = "akjdsbkjas&^absdjkajbdkasbdksajbdksadbkbj"

def get_db_connection():
    conn = sqlite3.connect("task_manager.db")
    conn.row_factory = sqlite3.Row
    return conn

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

@app.route('/employee/addcustomer', methods=["GET", "POST"])
@roles_permitted(['employee'])
def employee_add_cus():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        customer_name   = request.form["customer_name"]
        contact_person  = request.form.get("contact_person")
        email           = request.form.get("email")
        phone           = request.form.get("phone")
        address         = request.form.get("address")
        website         = request.form.get("website")
        type_           = request.form.get("type")
        industry        = request.form.get("industry")
        rev_value_euro  = request.form.get("rev_value_euro")

        # Who created the customer:
        # ASSUMPTION: you already know the logged-in user
        # For now, we’ll hardcode OR read from session
        cur.execute("""
            SELECT id FROM employees
            WHERE username = ?
        """, ("swhite@crm.gr",))   # replace with session user later
        created_by_user_id = cur.fetchone()["id"]

        cur.execute("""
            INSERT INTO customers
            (customer_name, contact_person, email, phone, address, website,
             type, industry, rev_value_euro, date_added, created_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            customer_name,
            contact_person,
            email,
            phone,
            address,
            website,
            type_,
            industry,
            rev_value_euro,
            date.today().isoformat(),
            created_by_user_id
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("employee_dashboard"))

    conn.close()
    return render_template("employee_add_cus.html")

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

@app.route("/manager/viewemployee")
def manager_view_emplo():
    conn = get_db_connection()
    cur = conn.cursor()

    # Total employees
    cur.execute("SELECT COUNT(*) FROM employees;")
    total_empl = cur.fetchone()[0]

    # Total customers
    cur.execute("SELECT COUNT(*) FROM customers;")
    total_cus = cur.fetchone()[0]

    # Total contacts
    cur.execute("SELECT COUNT(*) FROM customer_contact;")
    total_cont = cur.fetchone()[0]

    # Contacts this month (activity count)
    cur.execute("""
        SELECT COUNT(*)
        FROM customer_contact
        WHERE last_contact >= date('now','start of month')
          AND last_contact <  date('now','start of month','+1 month');
    """)
    contacts_this_month = cur.fetchone()[0]

    # Average contacts per employee (this month / employees)
    average_cont = round(contacts_this_month / total_empl, 2)

    # Best employee of the month = more active
    cur.execute("""
        SELECT e.username, COUNT(*) AS activity_count
        FROM customer_contact cc
        JOIN employees e ON e.id = cc.created_by_user_id
        WHERE cc.last_contact >= date('now','start of month')
          AND cc.last_contact <  date('now','start of month','+1 month')
        GROUP BY e.id
        ORDER BY activity_count DESC
        LIMIT 1;
    """)
    row = cur.fetchone()
    top_employee = row[0] if row else None

    #  Contacts per employee this month (for bar chart)
    cur.execute("""
        SELECT e.username AS name, COUNT(*) AS count
        FROM customer_contact cc
        JOIN employees e ON e.id = cc.created_by_user_id
        WHERE cc.last_contact >= date('now','start of month')
          AND cc.last_contact <  date('now','start of month','+1 month')
        GROUP BY e.id
        ORDER BY count DESC;
    """)
    month_contacts = [{"name": r[0], "count": r[1]} for r in cur.fetchall()]

    # Employee list 
    cur.execute("""
        SELECT
          e.username AS name,

          (SELECT COUNT(*)
           FROM customers c
           WHERE c.created_by_user_id = e.id
          ) AS customers_added_total,

          (SELECT COUNT(DISTINCT cc.customer_id)
           FROM customer_contact cc
           WHERE cc.created_by_user_id = e.id
          ) AS customers_contacted_total

        FROM employees e
        ORDER BY customers_contacted_total DESC, customers_added_total DESC, e.username;
    """)
    employee_list = [
        {
            "name": r[0],
            "customers_added_total": r[1],
            "customers_contacted_total": r[2],
        }
        for r in cur.fetchall()
    ]

    conn.close()

    stats = {
        "total_empl": total_empl,
        "total_cus": total_cus,
        "total_cont": total_cont,
        "average_cont": average_cont,
        "top_employee": top_employee,
        "month_contacts": month_contacts,
        "employee_list": employee_list,
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