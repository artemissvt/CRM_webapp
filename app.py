from flask import Flask, request, render_template, flash, session, redirect
import sqlite3 
import hashlib 
from functools import wraps
from flask import session, abort, url_for
from datetime import datetime

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
              AND date(created_at) = date('now');
        """, (user_id,)).fetchone()["cnt"]

        # Last week = previous calendar week (Mon-Sun), not "last 7 days"
        contacted_week = conn.execute("""
            SELECT COUNT(DISTINCT customer_id) AS cnt
            FROM customer_contact
            WHERE created_by_user_id = ?
              AND date(created_at) >= date('now','weekday 1','-14 days')
              AND date(created_at) <  date('now','weekday 1','-7 days');
        """, (user_id,)).fetchone()["cnt"]

        # Last month = previous calendar month
        contacted_month = conn.execute("""
            SELECT COUNT(DISTINCT customer_id) AS cnt
            FROM customer_contact
            WHERE created_by_user_id = ?
              AND date(created_at) >= date('now','start of month','-1 month')
              AND date(created_at) <  date('now','start of month');
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


@app.route("/employee/viewcustomer", methods=["GET"])
@roles_permitted(['employee'])
def employee_view_cus():
    uid = session.get("uid")
    if uid is None:
        abort(401)

    q = (request.args.get("q") or "").strip()

    conn = get_db_connection()
    cur = conn.cursor()

    sql = """
        SELECT id, customer_name, contact_person, email, phone, address, website
        FROM customers
        WHERE created_by_user_id = ?
    """
    params = [uid]

    if q:
        sql += """
            AND (
                customer_name  LIKE ? OR
                contact_person LIKE ? OR
                email          LIKE ? OR
                phone          LIKE ? OR
                address        LIKE ? OR
                website        LIKE ?
            )
        """
        like = f"%{q}%"
        params.extend([like]*6)

    sql += " ORDER BY customer_name ASC"

    cur.execute(sql, params)
    customers = cur.fetchall()
    conn.close()

    return render_template("employee_view_cus.html", customers=customers, q=q)


@app.route("/employee/customer/<int:customer_id>")
@roles_permitted(['employee'])
def employee_customer_detail(customer_id: int):
    uid = session.get("uid")
    if uid is None:
        abort(401)

    conn = get_db_connection()
    cur = conn.cursor()

    #main, bussiness info
    cur.execute("""
        SELECT
            id,
            customer_name,
            contact_person,
            email,
            phone,
            address,
            website,
            type AS customer_type,
            industry,
            rev_value_euro,
            date_added,
            type
        FROM customers
        WHERE id = ?
          AND created_by_user_id = ?
    """, (customer_id, uid))
    customer_row = cur.fetchone()

    if customer_row is None:
        conn.close()
        abort(404)

    customer = dict(customer_row)

    #activity history
    cur.execute("""
        SELECT
            created_at,
            notes,
            topics,
            next_contact
        FROM customer_contact
        WHERE customer_id = ?
          AND created_by_user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (customer_id, uid))
    latest = cur.fetchone()
    contact = dict(latest) if latest else {
        "created_at": None,
        "notes": None,
        "topics": None,
        "next_contact": None
    }

    #full contact history 
    cur.execute("""
        SELECT
            created_at,
            topics,
            notes,
            next_contact
        FROM customer_contact
        WHERE customer_id = ?
          AND created_by_user_id = ?
        ORDER BY created_at DESC
    """, (customer_id, uid))
    history_rows = cur.fetchall()
    contact_history = [dict(r) for r in history_rows]

    conn.close()

    return render_template(
        "employee_customer_detail.html",
        customer=customer,
        contact=contact,
        contact_history=contact_history
    )


@app.route('/employee/addcustomer', methods=['GET', 'POST'])
@roles_permitted(['employee'])
def employee_add_cus():
    uid = session.get("uid")
    if uid is None:
        abort(401)

    if request.method == "POST":
        customer_name  = (request.form.get("customer_name") or "").strip()
        contact_person = (request.form.get("contact_person") or "").strip() or None
        email          = (request.form.get("email") or "").strip() or None
        phone          = (request.form.get("phone") or "").strip() or None
        address        = (request.form.get("address") or "").strip() or None
        website        = (request.form.get("website") or "").strip() or None
        type_          = (request.form.get("type") or "").strip() or None
        industry       = (request.form.get("industry") or "").strip() or None
        rev_raw        = (request.form.get("rev_value_euro") or "").strip()

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

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO customers
                  (customer_name, contact_person, email, phone,
                   address, website, type, industry, rev_value_euro,
                   created_by_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                uid
            ))
            conn.commit()
            new_id = cur.lastrowid
        finally:
            conn.close()

        flash(f"Customer '{customer_name}' was created successfully.", "success")
        return redirect(url_for("employee_customer_detail", customer_id=new_id))

    return render_template("employee/addcustomer.html")

@app.route("/employee/customer/<int:customer_id>/contact/new", methods=["GET", "POST"])
@roles_permitted(['employee'])
def employee_add_cus_cont(customer_id: int):
    uid = session.get("uid")
    if uid is None:
        abort(401)

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT id, customer_name
            FROM customers
            WHERE id = ?
              AND created_by_user_id = ?
        """, (customer_id, uid))
        customer_row = cur.fetchone()
        if customer_row is None:
            abort(404)

        customer = dict(customer_row)

        if request.method == "POST":
            topics = (request.form.get("topics") or "").strip()
            notes = (request.form.get("notes") or "").strip()
            next_contact = (request.form.get("next_contact") or "").strip()

            if not topics and not notes and not next_contact:
                flash("Please fill at least one field (topics, notes, or next contact).", "error")
                return render_template("employee_add_cus_cont.html", customer=customer)

            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cur.execute("""
                INSERT INTO customer_contact (
                    customer_id,
                    created_by_user_id,
                    created_at,
                    topics,
                    notes,
                    next_contact
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (customer_id, uid, created_at, topics, notes, next_contact))

            conn.commit()
            flash("Contact saved.", "success")
            return redirect(url_for("employee_customer_detail", customer_id=customer_id))

        return render_template("employee_add_cus_cont.html", customer=customer)

    finally:
        conn.close()


@app.route("/employee/customer/<int:customer_id>/edit", methods=["GET", "POST"])
@roles_permitted(['employee'])
def employee_customer_edit(customer_id: int):
    uid = session.get("uid")
    if uid is None:
        abort(401)

    conn = get_db_connection()
    cur = conn.cursor()

    # Load customer (scoped to logged-in user)
    cur.execute("""
        SELECT
            id,
            customer_name,
            contact_person,
            email,
            phone,
            address,
            website,
            type,
            industry,
            rev_value_euro,
            type
        FROM customers
        WHERE id = ?
          AND created_by_user_id = ?
    """, (customer_id, uid))
    customer_row = cur.fetchone()

    if customer_row is None:
        conn.close()
        abort(404)

    customer = dict(customer_row)

    if request.method == "POST":
        form = request.form

        customer_name  = (form.get("customer_name") or "").strip()
        contact_person = (form.get("contact_person") or "").strip()
        email          = (form.get("email") or "").strip()
        phone          = (form.get("phone") or "").strip()
        address        = (form.get("address") or "").strip()
        website        = (form.get("website") or "").strip()

        cust_type      = (form.get("type") or "").strip()
        industry       = (form.get("industry") or "").strip()

        rev_raw = (form.get("rev_value_euro") or "").strip()
        rev_value_euro = None
        if rev_raw != "":
            try:
                rev_value_euro = float(rev_raw)
            except ValueError:
                conn.close()
                flash("Revenue value must be a number.")
                # Re-render with the values the user attempted to submit
                customer.update({
                    "customer_name": customer_name,
                    "contact_person": contact_person,
                    "email": email,
                    "phone": phone,
                    "address": address,
                    "website": website,
                    "type": cust_type,
                    "industry": industry,
                    "rev_value_euro": rev_raw,  # keep raw to show in input
                })
                return render_template("employee_customer_edit.html", customer=customer)

        # Optional: allow editing type from edit page.
        # If you do NOT want type editable here, keep the DB value.
        type = (form.get("type") or customer.get("type") or "").strip()

        # Write ALL fields, even unchanged (your chosen approach)
        cur.execute("""
            UPDATE customers
            SET
                customer_name = ?,
                contact_person = ?,
                email = ?,
                phone = ?,
                address = ?,
                website = ?,
                type = ?,
                industry = ?,
                rev_value_euro = ?,
                type = ?
            WHERE id = ?
              AND created_by_user_id = ?
        """, (
            customer_name,
            contact_person,
            email,
            phone,
            address,
            website,
            cust_type,
            industry,
            rev_value_euro,
            type,
            customer_id,
            uid
        ))

        conn.commit()
        conn.close()

        flash("Customer updated.")
        return redirect(url_for("employee_customer_detail", customer_id=customer_id))

    conn.close()
    return render_template("employee_customer_edit.html", customer=customer)


@app.route("/employee/customer/<int:customer_id>/cancel", methods=["POST"])
@roles_permitted(['employee'])
def employee_customer_cancel(customer_id: int):
    uid = session.get("uid")
    if uid is None:
        abort(401)

    conn = get_db_connection()
    cur = conn.cursor()

    cancel_value = "cancelled"

    cur.execute("""
        UPDATE customers
        SET type = ?
        WHERE id = ?
          AND created_by_user_id = ?
    """, (cancel_value, customer_id, uid))

    conn.commit()
    conn.close()

    flash("Customer cancelled.")
    return redirect(url_for("employee_customer_detail", customer_id=customer_id))


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
        WHERE created_at >= date('now','start of month')
          AND created_at <  date('now','start of month','+1 month');
    """)
    contacts_this_month = cur.fetchone()[0]

    # Average contacts per employee (this month / employees)
    average_cont = round(contacts_this_month / total_empl, 2)

    # Best employee of the month = more active
    cur.execute("""
        SELECT e.username, COUNT(*) AS activity_count
        FROM customer_contact cc
        JOIN employees e ON e.id = cc.created_by_user_id
        WHERE cc.created_at >= date('now','start of month')
          AND cc.created_at <  date('now','start of month','+1 month')
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
        WHERE cc.created_at >= date('now','start of month')
          AND cc.created_at <  date('now','start of month','+1 month')
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
                MAX(cc.created_at) AS created_at,
  CASE
    WHEN MAX(cc.created_at) IS NULL THEN NULL
    ELSE CAST((julianday('now') - julianday(MAX(cc.created_at))) AS INTEGER)
  END AS days_since_created_at
FROM customers c
LEFT JOIN customer_contact cc
  ON cc.customer_id = c.id
WHERE c.customer_name LIKE ?
GROUP BY c.id, c.customer_name
ORDER BY
  contact_count ASC,
  (created_at IS NOT NULL) ASC,
  created_at ASC
LIMIT 5;

        """, 
        (like,)).fetchall()

    finally:
        conn.close()

    # Map DB rows to what your template expects: stats.employee_list with fields:
    # e.name, e.haventresp, e.lastcont
    employee_list = []
    for r in rows:
        created_at = r["created_at"]  # may be None if never contacted
        days = r["days_since_created_at"]

        employee_list.append({
            "name": r["name"],
            "haventresp": ("Never" if created_at is None else f"{days} days"),
            "lastcont": ("Never" if created_at is None else created_at),
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
                id,
                name,
                password,
                role,
                username,
                status
            FROM users
            WHERE name LIKE ? OR username LIKE ?
            ORDER BY name ASC;
        """, (like, like)).fetchall()
    finally:
        conn.close()

    users = [dict(r) for r in rows]   # simplest and keeps id
    return render_template("admin_dashboard.html", users=users, q=q)

@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@roles_permitted(['admin'])
def admin_user_detail(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()

    # Load user
    cur.execute("""
        SELECT id, name, username, role, status, password
        FROM users
        WHERE id = ?
    """, (user_id,))
    row = cur.fetchone()

    if row is None:
        conn.close()
        abort(404)

    user = dict(row)

    if request.method == "POST":
        form = request.form

        name = (form.get("name") or "").strip()
        username = (form.get("username") or "").strip()  # this is your "email" field
        role = (form.get("role") or "").strip()
        status = (form.get("status") or "").strip()
        password = (form.get("password") or "").strip()

        # Write ALL fields (your chosen approach)
        cur.execute("""
            UPDATE users
            SET name = ?, username = ?, role = ?, status = ?, password = ?
            WHERE id = ?
        """, (name, username, role, status, password, user_id))

        conn.commit()
        conn.close()

        flash("User updated.")
        return redirect(url_for("admin_dashboard"))

    conn.close()
    return render_template("admin_user_detail.html", user=user)

@app.route("/admin/users/<int:user_id>/cancel", methods=["POST"])
@roles_permitted(['admin'])
def admin_user_cancel(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()

    # Use EXACT DB enum value
    cancel_value = "Cancelled"  # not "cancelled" unless your DB stores that

    cur.execute("""
        UPDATE users
        SET status = ?
        WHERE id = ?
    """, (cancel_value, user_id))

    conn.commit()
    conn.close()

    flash("User cancelled.")
    return redirect(url_for("admin_dashboard"))


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