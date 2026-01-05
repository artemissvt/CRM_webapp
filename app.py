from flask import Flask, request, render_template, flash, session, redirect
import sqlite3 
import hashlib 
from functools import wraps
from flask import session, abort, url_for

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = "akjdsbkjas&^absdjkajbdkasbdksajbdksadbkbj"

def get_db_connection():
    conn = sqlite3.connect("task_manager.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def roles_permitted(roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'uid' in session and session['role'] in roles:
                return f(*args, **kwargs)
            else:
                flash(f'Login again')
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
    return redirect(url_for('login'))

#login
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

#employee
@app.route('/employee')
@roles_permitted(['employee'])
def employee_dashboard():
    user_id = session.get("uid")
    if not user_id:
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        # -----------------------------
        # Customers added (by this employee)
        # -----------------------------
        added_total = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM customers
            WHERE created_by_user_id = ?;
        """, (user_id,)).fetchone()["cnt"]

        # This week (Monday -> today)
        added_week = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM customers
            WHERE created_by_user_id = ?
              AND date(date_added) >= date('now','weekday 1','-7 days')
              AND date(date_added) <= date('now');
        """, (user_id,)).fetchone()["cnt"]

        # This month (calendar month)
        added_month = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM customers
            WHERE created_by_user_id = ?
              AND date(date_added) >= date('now','start of month')
              AND date(date_added) <  date('now','start of month','+1 month');
        """, (user_id,)).fetchone()["cnt"]

        # Customers contacted (by this employee with session id)
        contacted_today = conn.execute("""
            SELECT COUNT(DISTINCT customer_id) AS cnt
            FROM customer_contact
            WHERE created_by_user_id = ?
              AND date(last_contact) = date('now');
        """, (user_id,)).fetchone()["cnt"]

        # Last week = previous calendar week (Mon-Sun), not "last 7 days"
        contacted_week = conn.execute("""
            SELECT COUNT(DISTINCT customer_id) AS cnt
            FROM customer_contact
            WHERE created_by_user_id = ?
              AND date(last_contact) >= date('now','weekday 1','-14 days')
              AND date(last_contact) <  date('now','weekday 1','-7 days');
        """, (user_id,)).fetchone()["cnt"]

        # Last month = previous calendar month
        contacted_month = conn.execute("""
            SELECT COUNT(DISTINCT customer_id) AS cnt
            FROM customer_contact
            WHERE created_by_user_id = ?
              AND date(last_contact) >= date('now','start of month','-1 month')
              AND date(last_contact) <  date('now','start of month');
        """, (user_id,)).fetchone()["cnt"]

    finally:
        conn.close()

    stats = {
        "added_week": added_week,
        "added_month": added_month,
        "added_total": added_total,
        "contacted_today": contacted_today,
        "contacted_week": contacted_week,
        "contacted_month": contacted_month,
    }

    return render_template('employee_dashboard.html', stats=stats)


@app.route('/employee/customers', methods=['GET'])
@roles_permitted(['employee'])
def employee_view_cus():
    q = (request.args.get("q") or "").strip()
    customer_id = (request.args.get("customer_id") or "").strip()
    conn = get_db_connection()
    

@app.route('/employee/addcustomer', methods=[ 'GET', 'POST' ])
@roles_permitted(['employee'])
def employee_add_cus():
    db = get_db_conn()
    cursor = db.cursor() 
    if request.method == "POST":
        # read + normalize form fields
        customer_name  = (request.form.get("customer_name") or "").strip()

        contact_person = (request.form.get("contact_person") or "").strip()
        email          = (request.form.get("email") or "").strip()
        phone          = (request.form.get("phone") or "").strip()
        address        = (request.form.get("address") or "").strip()
        website        = (request.form.get("website") or "").strip()
        type_          = (request.form.get("type") or "").strip()
        industry       = (request.form.get("industry") or "").strip()
        rev_raw        = (request.form.get("rev_value_euro") or "").strip()

        # data validation
        if not customer_name:
            flash("Customer name is required.", "danger")
            return render_template("employee/addcustomer.html")

        rev_value_euro = None
        if rev_raw:
            try:
                rev_value_euro = float(rev_raw.replace(",", "."))
            except ValueError:
                flash("Revenue value must be numeric (e.g., 10000 or 10000.50).", "danger")
                return render_template("employee/addcustomer.html")

        # Normalize empty strings to None in order for the db to be clean
        contact_person = contact_person or None
        email          = email or None
        phone          = phone or None
        address        = address or None
        website        = website or None
        type_          = type_ or None
        industry       = industry or None

        # store username/email in session and use it for created by user id
        if created_by_user_id is None:
            session_username = session.get("username") 

            if session_username:
                conn = get_db_connection()
                try:
                    row = conn.execute(
                        "SELECT id FROM employees WHERE username = ?",
                        (session_username,)
                    ).fetchone()
                finally:
                    conn.close()

                if row is None:
                    flash("Logged-in employee not found in employees table.", "danger")
                    return render_template("employee/addcustomer.html")

                created_by_user_id = row["id"]

        # data insert into customers table
        conn = get_db_connection()
        try:
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO customers
                (customer_name, contact_person, email, phone,
                 address, website, type, industry, rev_value_euro,
                 created_by_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    customer_name,
                    contact_person,
                    email,
                    phone,
                    address,
                    website,
                    type_,
                    industry,
                    rev_value_euro,
                    created_by_user_id
                )
            )

            conn.commit()
            new_id = cur.lastrowid

        except sqlite3.IntegrityError as e:
            conn.rollback()
            flash(f"Database constraint error: {e}", "danger")
            return render_template("employee/addcustomer.html")

        finally:
            conn.close()

        flash(f"Customer '{customer_name}' was created successfully.", "success")
        return redirect(url_for("employee_add_cus", customer_id=new_id))

    return render_template("employee_add_cus.html")

@app.route("/employee/addcustomercontact", methods=["GET", "POST"])
@roles_permitted(["employee"])
def employee_add_cus_cont():
    if request.method == "POST":
        # --- Read fields exactly as your HTML sends them ---
        customer_name  = (request.form.get("customer_name") or "").strip()
        last_contact = (request.form.get("customer_name") or "").strip()
        contact_person = (request.form.get("contact_person") or "").strip() or None
        email          = (request.form.get("email") or "").strip() or None
        phone          = (request.form.get("phone") or "").strip() or None
        topics         = (request.form.get("topics") or "").strip()
        notes          = (request.form.get("notes") or "").strip() or None
        
        # --- Validate required fields ---
        if not customer_name:
            flash("ERROR: Customer name is required.", "danger")
            return render_template("employee_add_cus_cont.html")

        if not topics:
            flash("ERROR: Topics discussed is required.", "danger")
            return render_template("employee_add_cus_cont.html")

        # Must be logged in (your login sets session['uid'])
        created_by_user_id = session.get("uid")
        if not created_by_user_id:
            flash("ERROR: Session expired. Please log in again.", "danger")
            return redirect(url_for("login"))

        conn = get_db_connection()
        try:
            # 1) Find customer_id by exact name match
            rows = conn.execute("""
                SELECT id
                FROM customers
                WHERE customer_name = ?
            """, (customer_name,)).fetchall()

            if not rows:
                flash("ERROR: Customer not found. Please create the customer first (exact name match).", "danger")
                return render_template("employee_add_cus_cont.html")

            if len(rows) > 1:
                flash("ERROR: Multiple customers have this name. Please use a unique customer name.", "danger")
                return render_template("employee_add_cus_cont.html")

            customer_id = rows[0]["id"]

            # Insert into customer_contact (aligned with your table columns)
            try:
                conn.execute("""
                    INSERT INTO customer_contact
                        (next_contact, topics, notes, created_by_user_id, customer_id, last_contact)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    None,             # next_contact (you don't collect it in this form)
                    topics,           # topics (WARNING: your DB has UNIQUE here)
                    notes,            # notes
                    created_by_user_id,
                    customer_id,
                    last_contact
                ))
                conn.commit()

            except sqlite3.IntegrityError as e:
                conn.rollback()
                flash(f"Database error: {e}", "danger")
                return render_template("employee_add_cus_cont.html")

        finally:
            conn.close()

        flash("New customer contact saved successfully.", "success")
        return redirect(url_for("employee_dashboard"))

    # GET
    return render_template("employee_add_cus_cont.html")

#manager
@app.route('/manager')
@roles_permitted(['manager'])
def manager_dashboard():
    conn = get_db_connection()
    try:
        # If your column is not type, change it here once.
        col = "type"

        lead = conn.execute(f"""
            SELECT COUNT(*) AS cnt
            FROM customers
            WHERE {col} = ?;
        """, ("lead",)).fetchone()["cnt"]

        active = conn.execute(f"""
            SELECT COUNT(*) AS cnt
            FROM customers
            WHERE {col} = ?;
        """, ("active",)).fetchone()["cnt"]

        inactive = conn.execute(f"""
            SELECT COUNT(*) AS cnt
            FROM customers
            WHERE {col} = ?;
        """, ("inactive",)).fetchone()["cnt"]

        cancelled = conn.execute(f"""
            SELECT COUNT(*) AS cnt
            FROM customers
            WHERE {col} = ?;
        """, ("cancelled",)).fetchone()["cnt"]

        stats = {
            "lead": lead,
            "active": active,
            "inactive": inactive,
            "cancelled": cancelled
        }

    finally:
        conn.close()

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
    q = (request.args.get("q") or "").strip()

    like = f"%{q}%"

    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT
                c.id AS customer_id,
                c.customer_name AS name,
                COUNT(cc.contact_id) AS contact_count,
                MAX(cc.last_contact) AS last_contact,
  CASE
    WHEN MAX(cc.last_contact) IS NULL THEN NULL
    ELSE CAST((julianday('now') - julianday(MAX(cc.last_contact))) AS INTEGER)
  END AS days_since_last_contact
FROM customers c
LEFT JOIN customer_contact cc
  ON cc.customer_id = c.id
WHERE c.customer_name LIKE ?
GROUP BY c.id, c.customer_name
ORDER BY
  contact_count ASC,
  (last_contact IS NOT NULL) ASC,
  last_contact ASC
LIMIT 5;

        """, 
        (like,)).fetchall()

    finally:
        conn.close()

    # Map DB rows to what your template expects: stats.employee_list with fields:
    # e.name, e.haventresp, e.lastcont
    employee_list = []
    for r in rows:
        last_contact = r["last_contact"]  # may be None if never contacted
        days = r["days_since_last_contact"]

        employee_list.append({
            "name": r["name"],
            "haventresp": ("Never" if last_contact is None else f"{days} days"),
            "lastcont": ("Never" if last_contact is None else last_contact),
        })

    stats = {
        "employee_list": employee_list
    }

    return render_template("manager_view_cus.html", stats=stats, q=q)

#admin
@app.route('/admin')
@roles_permitted(['admin'])
def admin_dashboard():
    q = (request.args.get("q") or "").strip()
    like = f"%{q}%"

    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT
                name,
                role,
                username,
                status
            FROM users
            WHERE name LIKE ? OR username LIKE ?
            ORDER BY name ASC;
        """, (like, like)).fetchall()
    finally:
        conn.close()

    users = [
        {
            "name": r["name"],
            "role": r["role"],
            "username": r["username"],
            "status": r["status"],
        }
        for r in rows
    ]

    return render_template(
        "admin_dashboard.html",
        users=users,
        q=q
    )


@app.route('/admin/adduser', methods=['GET', 'POST'])
@roles_permitted(['admin'])
def admin_add_users():
    if request.method == 'POST':
        fullname = (request.form.get('name') or '').strip()
        username = (request.form.get('username') or '').strip()
        role     = (request.form.get('role') or '').strip()
        password = request.form.get('password') or ''
        repass   = request.form.get('repass') or ''

        if not username or not fullname:
            flash("ERROR: Full name and username are required.", "danger")
            return render_template('admin_add_users.html', username=username)

        if password != repass:
            flash("ERROR: Passwords do not match", "danger")
            return render_template('admin_add_users.html', username=username)

        db = get_db_conn()
        try:
            cursor = db.cursor()
            user = cursor.execute(
                "SELECT 1 FROM users WHERE username=?",
                (username,)
            ).fetchone()

            if user:
                flash("ERROR: Username is taken", "danger")
                return render_template('admin_add_users.html', username=username)

            hashed_password = hash_password(username, password)

            cursor.execute("""
                INSERT INTO users (name, username, password, role, status)
                VALUES (?, ?, ?, ?, ?)
            """, (fullname, username, hashed_password, role, "Active"))

            db.commit()
        finally:
            db.close()

        flash("User created successfully.", "success")
        return redirect(url_for('admin_add_users'))

    return render_template('admin_add_users.html')
    
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