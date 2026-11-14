"""
app.py - Smart Attendance Analyser (Flask + SQLite)

Run locally :  python app.py
On Render   :  gunicorn app:app
"""
import csv
import io
import os
import random
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import analysis

# ------------------------------------------------------------------ config
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get("DATABASE_PATH") or os.path.join(BASE_DIR, "database", "attendance.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

DEFAULT_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
DEFAULT_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

try:  # time zone used for "today" (Render servers run in UTC)
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Kolkata"))
except Exception:  # tzdata missing -> fixed India offset
    TZ = timezone(timedelta(hours=5, minutes=30))

SCHEMA = """
CREATE TABLE IF NOT EXISTS admin (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL DEFAULT 'Administrator',
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS students (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_no     TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    email      TEXT,
    phone      TEXT,
    class_name TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS subjects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    semester   TEXT NOT NULL,
    teacher    TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS attendance (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    date       TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('Present', 'Absent')),
    marked_by  INTEGER REFERENCES admin(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (student_id, subject_id, date)
);
CREATE INDEX IF NOT EXISTS idx_att_date    ON attendance(date);
CREATE INDEX IF NOT EXISTS idx_att_subject ON attendance(subject_id);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

DEFAULT_SETTINGS = {
    "college_name": "Your College Name",
    "department": "Department of Computer Applications (BCA)",
    "address": "",
    "academic_year": "2026-27",
    "risk_threshold": str(analysis.DEFAULT_RISK),
    "excellent_threshold": str(analysis.DEFAULT_EXCELLENT),
}


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def today_str():
    return datetime.now(TZ).date().isoformat()


def init_db():
    """Create tables, default settings and the first admin. Returns a secret key."""
    conn = connect()
    conn.executescript(SCHEMA)
    for k, v in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
    if conn.execute("SELECT COUNT(*) FROM admin").fetchone()[0] == 0:
        conn.execute("INSERT INTO admin(username, password_hash, full_name) VALUES (?,?,?)",
                     (DEFAULT_USERNAME, generate_password_hash(DEFAULT_PASSWORD), "Administrator"))
    row = conn.execute("SELECT value FROM settings WHERE key='secret_key'").fetchone()
    if row:
        secret = row["value"]
    else:
        secret = secrets.token_hex(32)
        conn.execute("INSERT INTO settings(key, value) VALUES ('secret_key', ?)", (secret,))
    conn.commit()
    if os.environ.get("SEED_DEMO") == "1":
        seed_demo(conn)
    conn.close()
    return secret


def seed_demo(conn):
    """Fill an EMPTY database with clearly-labelled demo data (for demonstrations)."""
    if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]:
        return False
    rnd = random.Random(2026)
    students = [
        ("BCA001", "Ananya Gowda", "ananya@example.com", "9876500001"),
        ("BCA002", "Rohan Shetty", "rohan@example.com", "9876500002"),
        ("BCA003", "Meghana Rao", "meghana@example.com", "9876500003"),
        ("BCA004", "Karthik Naik", "karthik@example.com", "9876500004"),
        ("BCA005", "Divya Hegde", "divya@example.com", "9876500005"),
        ("BCA006", "Suresh Patil", "suresh@example.com", "9876500006"),
        ("BCA007", "Pooja Kulkarni", "pooja@example.com", "9876500007"),
        ("BCA008", "Arjun Bhat", "arjun@example.com", "9876500008"),
        ("BCA009", "Sneha Reddy", "sneha@example.com", "9876500009"),
        ("BCA010", "Vikas Kumar", "vikas@example.com", "9876500010"),
    ]
    subjects = [
        ("BCA501", "Python Programming", "5th Sem", "Prof. Lakshmi N"),
        ("BCA502", "Web Technologies", "5th Sem", "Prof. Ramesh K"),
        ("BCA503", "Database Management Systems", "5th Sem", "Prof. Savita M"),
        ("BCA504", "Computer Networks", "5th Sem", "Prof. Girish H"),
    ]
    for reg, name, email, phone in students:
        conn.execute("INSERT INTO students(reg_no,name,email,phone,class_name) VALUES (?,?,?,?,?)",
                     (reg, name, email, phone, "BCA - 5th Sem"))
    for code, name, sem, teacher in subjects:
        conn.execute("INSERT INTO subjects(code,name,semester,teacher) VALUES (?,?,?,?)",
                     (code, name, sem, teacher))
    stu_ids = [r[0] for r in conn.execute("SELECT id FROM students ORDER BY id")]
    sub_ids = [r[0] for r in conn.execute("SELECT id FROM subjects ORDER BY id")]
    # each student has a "attendance habit" so the charts show variety
    habit = {sid: p for sid, p in zip(stu_ids, [0.97, 0.92, 0.88, 0.80, 0.94,
                                               0.66, 0.84, 0.72, 0.91, 0.60])}
    today = datetime.now(TZ).date()
    for back in range(0, 75):
        d = today - timedelta(days=back)
        if d.weekday() == 6:  # no Sunday classes
            continue
        for sub in sub_ids:
            if rnd.random() < 0.55:  # not every subject meets every day
                for sid in stu_ids:
                    status = "Present" if rnd.random() < habit[sid] else "Absent"
                    conn.execute("INSERT OR IGNORE INTO attendance"
                                 "(student_id,subject_id,date,status) VALUES (?,?,?,?)",
                                 (sid, sub, d.isoformat(), status))
    conn.commit()
    return True


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or init_db()
if os.environ.get("SECRET_KEY"):
    init_db()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),  # HTTPS only on Render
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)


# ------------------------------------------------------------ db per request
def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def get_settings(db=None):
    db = db or get_db()
    return {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}


def thresholds(settings=None):
    s = settings or get_settings()
    try:
        risk = int(s.get("risk_threshold", analysis.DEFAULT_RISK))
        exc = int(s.get("excellent_threshold", analysis.DEFAULT_EXCELLENT))
    except ValueError:
        risk, exc = analysis.DEFAULT_RISK, analysis.DEFAULT_EXCELLENT
    return risk, exc


# ------------------------------------------------------------ security bits
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token  # visible inside macros too


@app.before_request
def csrf_protect():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
            abort(400)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def safe_next(target):
    """Only allow redirects to pages on this site."""
    if not target:
        return None
    p = urlparse(target)
    if p.netloc or p.scheme or not target.startswith("/") or target.startswith("//"):
        return None
    return target


@app.context_processor
def inject_globals():
    ctx = {"today": today_str()}
    if session.get("admin_id"):
        db = get_db()
        admin = db.execute("SELECT id, username, full_name FROM admin WHERE id=?",
                           (session["admin_id"],)).fetchone()
        ctx["admin"] = admin
        ctx["college"] = get_settings(db)
    return ctx


# ------------------------------------------------------------- validators
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+\-\s]{7,15}$")
USER_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")


def clean(value, limit=120):
    return (value or "").strip()[:limit]


def valid_date(value):
    try:
        datetime.strptime(value or "", "%Y-%m-%d")
        return True
    except ValueError:
        return False


def valid_month(value):
    try:
        datetime.strptime(value or "", "%Y-%m")
        return True
    except ValueError:
        return False


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def read_filters(args):
    """Validate filter values coming from the URL (never trust the browser)."""
    f = {
        "student_id": to_int(args.get("student_id")) or "",
        "subject_id": to_int(args.get("subject_id")) or "",
        "date": args.get("date", "") if valid_date(args.get("date")) else "",
        "month": args.get("month", "") if valid_month(args.get("month")) else "",
        "date_from": args.get("date_from", "") if valid_date(args.get("date_from")) else "",
        "date_to": args.get("date_to", "") if valid_date(args.get("date_to")) else "",
    }
    return f


def all_students(db):
    return db.execute("SELECT id, reg_no, name FROM students ORDER BY name COLLATE NOCASE").fetchall()


def all_subjects(db):
    return db.execute("SELECT id, code, name FROM subjects ORDER BY name COLLATE NOCASE").fetchall()


# ------------------------------------------------------------------- auth
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_id"):
        return redirect(url_for("dashboard"))
    db = get_db()
    if request.method == "POST":
        username = clean(request.form.get("username"), 50)
        password = request.form.get("password", "")
        row = db.execute("SELECT * FROM admin WHERE username = ?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session["admin_id"] = row["id"]
            session.permanent = True
            csrf_token()
            flash(f"Welcome back, {row['full_name']}!", "success")
            return redirect(safe_next(request.args.get("next")) or url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    # show the demo hint only while the default password is still active
    default_row = db.execute("SELECT password_hash FROM admin WHERE username = ?",
                             (DEFAULT_USERNAME,)).fetchone()
    show_hint = bool(default_row and check_password_hash(default_row["password_hash"],
                                                         DEFAULT_PASSWORD)
                     and DEFAULT_PASSWORD == "admin123")
    return render_template("login.html", show_hint=show_hint)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# -------------------------------------------------------------- dashboard
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    risk, exc = thresholds()
    data = analysis.dashboard_data(db, today_str(), risk, exc)
    return render_template("dashboard.html", d=data, risk=risk, excellent=exc)


# --------------------------------------------------------------- students
def validate_student(form, db, student_pk=None):
    errors = []
    reg_no, name = clean(form.get("reg_no"), 30), clean(form.get("name"), 80)
    email, phone = clean(form.get("email"), 100), clean(form.get("phone"), 20)
    class_name = clean(form.get("class_name"), 50)
    if not reg_no:
        errors.append("Student ID / Register Number is required.")
    if not name:
        errors.append("Student name is required.")
    if not class_name:
        errors.append("Class / Semester is required.")
    if email and not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    if phone and not PHONE_RE.match(phone):
        errors.append("Phone number should have 7-15 digits (you may use + and -).")
    if reg_no:
        dup = db.execute("SELECT id FROM students WHERE reg_no = ? COLLATE NOCASE", (reg_no,)).fetchone()
        if dup and dup["id"] != student_pk:
            errors.append(f"Register number '{reg_no}' already exists.")
    return errors, {"reg_no": reg_no, "name": name, "email": email,
                    "phone": phone, "class_name": class_name}


@app.route("/students")
@login_required
def students():
    db = get_db()
    risk, exc = thresholds()
    q = clean(request.args.get("q"), 60)
    rows = analysis.student_summary(db, {}, risk, exc)
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in " ".join(
            str(r[k] or "") for k in ("reg_no", "name", "email", "phone", "class_name")).lower()]
    return render_template("students.html", students=rows, q=q)


@app.route("/students/add", methods=["GET", "POST"])
@login_required
def student_add():
    db = get_db()
    form = {}
    if request.method == "POST":
        errors, form = validate_student(request.form, db)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            try:
                db.execute("INSERT INTO students(reg_no,name,email,phone,class_name) "
                           "VALUES (:reg_no,:name,:email,:phone,:class_name)", form)
                db.commit()
                flash(f"Student '{form['name']}' added successfully.", "success")
                return redirect(url_for("students"))
            except sqlite3.IntegrityError:
                flash("That register number already exists.", "danger")
    return render_template("student_form.html", form=form, student=None)


@app.route("/students/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def student_edit(sid):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    if not student:
        abort(404)
    form = dict(student)
    if request.method == "POST":
        errors, form = validate_student(request.form, db, sid)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            try:
                db.execute("UPDATE students SET reg_no=:reg_no, name=:name, email=:email, "
                           "phone=:phone, class_name=:class_name WHERE id=:id", {**form, "id": sid})
                db.commit()
                flash("Student details updated.", "success")
                return redirect(url_for("students"))
            except sqlite3.IntegrityError:
                flash("That register number already exists.", "danger")
    return render_template("student_form.html", form=form, student=student)


@app.route("/students/<int:sid>")
@login_required
def student_view(sid):
    db = get_db()
    risk, exc = thresholds()
    rows = analysis.student_summary(db, {"student_id": sid}, risk, exc)
    if not rows:
        abort(404)
    by_subject = analysis.subject_summary(db, {"student_id": sid}, risk, exc)
    by_subject = [s for s in by_subject if s["total"]]
    records = db.execute(
        "SELECT a.date, a.status, sub.code, sub.name AS subject FROM attendance a "
        "JOIN subjects sub ON sub.id = a.subject_id WHERE a.student_id = ? "
        "ORDER BY a.date DESC, a.id DESC LIMIT 25", (sid,)).fetchall()
    monthly = analysis.monthly_series(db, {"student_id": sid}, 12)
    return render_template("student_detail.html", s=rows[0], by_subject=by_subject,
                           records=records, monthly=monthly, risk=risk)


@app.route("/students/<int:sid>/delete", methods=["POST"])
@login_required
def student_delete(sid):
    db = get_db()
    row = db.execute("SELECT name FROM students WHERE id = ?", (sid,)).fetchone()
    if not row:
        abort(404)
    db.execute("DELETE FROM students WHERE id = ?", (sid,))  # attendance cascades
    db.commit()
    flash(f"Student '{row['name']}' and their attendance records were deleted.", "warning")
    return redirect(url_for("students"))


# --------------------------------------------------------------- subjects
def validate_subject(form, db, subject_pk=None):
    errors = []
    code, name = clean(form.get("code"), 20), clean(form.get("name"), 80)
    semester, teacher = clean(form.get("semester"), 30), clean(form.get("teacher"), 80)
    if not code:
        errors.append("Subject code is required.")
    if not name:
        errors.append("Subject name is required.")
    if not semester:
        errors.append("Semester is required.")
    if not teacher:
        errors.append("Subject teacher is required.")
    if code:
        dup = db.execute("SELECT id FROM subjects WHERE code = ? COLLATE NOCASE", (code,)).fetchone()
        if dup and dup["id"] != subject_pk:
            errors.append(f"Subject code '{code}' already exists.")
    return errors, {"code": code, "name": name, "semester": semester, "teacher": teacher}


@app.route("/subjects")
@login_required
def subjects():
    db = get_db()
    risk, exc = thresholds()
    q = clean(request.args.get("q"), 60)
    rows = analysis.subject_summary(db, {}, risk, exc)
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in " ".join(
            str(r[k] or "") for k in ("code", "name", "semester", "teacher")).lower()]
    return render_template("subjects.html", subjects=rows, q=q)


@app.route("/subjects/add", methods=["GET", "POST"])
@login_required
def subject_add():
    db = get_db()
    form = {}
    if request.method == "POST":
        errors, form = validate_subject(request.form, db)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            try:
                db.execute("INSERT INTO subjects(code,name,semester,teacher) "
                           "VALUES (:code,:name,:semester,:teacher)", form)
                db.commit()
                flash(f"Subject '{form['name']}' added successfully.", "success")
                return redirect(url_for("subjects"))
            except sqlite3.IntegrityError:
                flash("That subject code already exists.", "danger")
    return render_template("subject_form.html", form=form, subject=None)


@app.route("/subjects/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def subject_edit(sid):
    db = get_db()
    subject = db.execute("SELECT * FROM subjects WHERE id = ?", (sid,)).fetchone()
    if not subject:
        abort(404)
    form = dict(subject)
    if request.method == "POST":
        errors, form = validate_subject(request.form, db, sid)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            try:
                db.execute("UPDATE subjects SET code=:code, name=:name, semester=:semester, "
                           "teacher=:teacher WHERE id=:id", {**form, "id": sid})
                db.commit()
                flash("Subject updated.", "success")
                return redirect(url_for("subjects"))
            except sqlite3.IntegrityError:
                flash("That subject code already exists.", "danger")
    return render_template("subject_form.html", form=form, subject=subject)


@app.route("/subjects/<int:sid>")
@login_required
def subject_view(sid):
    db = get_db()
    risk, exc = thresholds()
    rows = analysis.subject_summary(db, {"subject_id": sid}, risk, exc)
    if not rows:
        abort(404)
    by_student = analysis.student_summary(db, {"subject_id": sid}, risk, exc)
    daily = list(reversed(analysis.daily_series(db, {"subject_id": sid}, 10)))
    return render_template("subject_detail.html", s=rows[0], by_student=by_student,
                           daily=daily, risk=risk)


@app.route("/subjects/<int:sid>/delete", methods=["POST"])
@login_required
def subject_delete(sid):
    db = get_db()
    row = db.execute("SELECT name FROM subjects WHERE id = ?", (sid,)).fetchone()
    if not row:
        abort(404)
    db.execute("DELETE FROM subjects WHERE id = ?", (sid,))
    db.commit()
    flash(f"Subject '{row['name']}' and its attendance records were deleted.", "warning")
    return redirect(url_for("subjects"))


# ------------------------------------------------------- mark attendance
@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    db = get_db()
    subjects_list = all_subjects(db)
    students_list = db.execute(
        "SELECT id, reg_no, name, class_name FROM students ORDER BY name COLLATE NOCASE").fetchall()

    if request.method == "POST":
        date_val = request.form.get("date", "")
        subject_id = to_int(request.form.get("subject_id"))
        back = url_for("attendance", date=date_val, subject_id=subject_id or "")
        if not valid_date(date_val):
            flash("Please choose a valid date.", "danger")
            return redirect(back)
        if date_val > today_str():
            flash("You cannot mark attendance for a future date.", "danger")
            return redirect(back)
        if not subject_id or not db.execute("SELECT 1 FROM subjects WHERE id=?", (subject_id,)).fetchone():
            flash("Please select a subject.", "danger")
            return redirect(back)

        created = updated = present = absent = 0
        for stu in students_list:
            status = request.form.get(f"status_{stu['id']}")
            if status not in ("Present", "Absent"):
                continue
            exists = db.execute("SELECT id FROM attendance WHERE student_id=? AND subject_id=? AND date=?",
                                (stu["id"], subject_id, date_val)).fetchone()
            if exists:  # duplicate prevented -> update the existing row
                db.execute("UPDATE attendance SET status=?, marked_by=?, updated_at=CURRENT_TIMESTAMP "
                           "WHERE id=?", (status, session["admin_id"], exists["id"]))
                updated += 1
            else:
                db.execute("INSERT INTO attendance(student_id,subject_id,date,status,marked_by) "
                           "VALUES (?,?,?,?,?)", (stu["id"], subject_id, date_val, status, session["admin_id"]))
                created += 1
            present += status == "Present"
            absent += status == "Absent"
        db.commit()
        if created + updated == 0:
            flash("No attendance was submitted.", "warning")
        else:
            flash(f"Attendance saved for {date_val}: {present} present, {absent} absent "
                  f"({created} new, {updated} updated).", "success")
        return redirect(back)

    date_val = request.args.get("date") if valid_date(request.args.get("date")) else today_str()
    subject_id = to_int(request.args.get("subject_id"))
    if not subject_id and subjects_list:
        subject_id = subjects_list[0]["id"]
    existing = {}
    if subject_id:
        for r in db.execute("SELECT student_id, status FROM attendance WHERE subject_id=? AND date=?",
                            (subject_id, date_val)):
            existing[r["student_id"]] = r["status"]
    return render_template("attendance.html", subjects=subjects_list, students=students_list,
                           date_val=date_val, subject_id=subject_id, existing=existing)


@app.route("/attendance/delete", methods=["POST"])
@login_required
def attendance_delete():
    db = get_db()
    date_val = request.form.get("date", "")
    subject_id = to_int(request.form.get("subject_id"))
    if not valid_date(date_val) or not subject_id:
        abort(400)
    cur = db.execute("DELETE FROM attendance WHERE subject_id=? AND date=?", (subject_id, date_val))
    db.commit()
    flash(f"Deleted {cur.rowcount} attendance record(s) for {date_val}.", "warning")
    return redirect(url_for("attendance", date=date_val, subject_id=subject_id))


# --------------------------------------------------------------- analysis
@app.route("/analysis")
@login_required
def analysis_page():
    db = get_db()
    risk, exc = thresholds()
    f = read_filters(request.args)
    f["date_from"] = f["date_to"] = ""  # ranges are only for reports
    students_all = analysis.student_summary(db, f, risk, exc)
    with_data = [s for s in students_all if s["percent"] is not None]
    data = {
        "overall": analysis.overall(db, f),
        "students": students_all,
        "subjects": analysis.subject_summary(db, f, risk, exc),
        "daily": analysis.daily_series(db, f, 30),
        "weekly": analysis.weekly_series(db, f, 12),
        "monthly": analysis.monthly_series(db, f, 12),
        "low": sorted((s for s in with_data if s["status"] == "Low"), key=lambda s: s["percent"]),
        "at_risk": sorted((s for s in with_data if s["status"] == "At Risk"), key=lambda s: s["percent"]),
        "excellent": sorted((s for s in with_data if s["status"] == "Excellent"),
                            key=lambda s: -s["percent"]),
    }
    return render_template("analysis.html", f=f, data=data, risk=risk, excellent=exc,
                           students_list=all_students(db), subjects_list=all_subjects(db))


# ---------------------------------------------------------------- reports
def report_context():
    db = get_db()
    risk, exc = thresholds()
    rtype = request.args.get("type", "student")
    if rtype not in dict(analysis.REPORT_TYPES):
        rtype = "student"
    f = read_filters(request.args)
    f["month"] = f["date"] = ""  # reports use the from/to range only
    report = analysis.build_report(db, rtype, f, today_str(), risk, exc)
    parts = []
    if f["student_id"]:
        r = db.execute("SELECT name FROM students WHERE id=?", (f["student_id"],)).fetchone()
        parts.append(f"Student: {r['name']}" if r else "")
    if f["subject_id"]:
        r = db.execute("SELECT name FROM subjects WHERE id=?", (f["subject_id"],)).fetchone()
        parts.append(f"Subject: {r['name']}" if r else "")
    if f["date_from"]:
        parts.append(f"From: {f['date_from']}")
    if f["date_to"]:
        parts.append(f"To: {f['date_to']}")
    report["filters_text"] = " | ".join(p for p in parts if p) or "No filters (all records)"
    return rtype, f, report


@app.route("/reports")
@login_required
def reports():
    db = get_db()
    rtype, f, report = report_context()
    base_args = {k: v for k, v in f.items() if v and k not in ("date", "month")}
    qargs = dict(base_args, type=rtype)
    return render_template("reports.html", rtype=rtype, f=f, report=report, qargs=qargs,
                           base_args=base_args,
                           report_types=analysis.REPORT_TYPES,
                           students_list=all_students(db), subjects_list=all_subjects(db),
                           generated=datetime.now(TZ).strftime("%d %b %Y, %I:%M %p"))


@app.route("/reports/export.csv")
@login_required
def report_csv():
    rtype, _f, report = report_context()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([report["title"]])
    writer.writerow([report["filters_text"]])
    writer.writerow([])
    writer.writerow(report["columns"])
    writer.writerows(report["rows"])
    data = "﻿" + buf.getvalue()  # BOM so Excel opens it correctly
    return Response(data, mimetype="text/csv; charset=utf-8", headers={
        "Content-Disposition": f"attachment; filename=attendance_{rtype}_report_{today_str()}.csv"})


@app.route("/reports/export.pdf")
@login_required
def report_pdf():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        flash("PDF library missing. Run: pip install reportlab", "danger")
        return redirect(url_for("reports"))

    rtype, _f, report = report_context()
    college = get_settings()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=28, rightMargin=28,
                            topMargin=28, bottomMargin=28, title=report["title"])
    styles = getSampleStyleSheet()
    story = [Paragraph(f"<b>{college['college_name']}</b>", styles["Title"]),
             Paragraph(f"{college['department']} &nbsp;|&nbsp; Academic Year {college['academic_year']}",
                       styles["Normal"]),
             Spacer(1, 8),
             Paragraph(f"<b>{report['title']}</b>", styles["Heading2"]),
             Paragraph(f"{report['filters_text']} &nbsp;|&nbsp; Generated: "
                       f"{datetime.now(TZ).strftime('%d %b %Y, %I:%M %p')}", styles["Normal"])]
    if report["note"]:
        story.append(Paragraph(report["note"], styles["Italic"]))
    story.append(Spacer(1, 10))
    if report["rows"]:
        table_data = [report["columns"]] + [[str(c) for c in row] for row in report["rows"]]
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eff6ff")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No attendance records match the selected filters.", styles["Normal"]))
    doc.build(story)
    return Response(buf.getvalue(), mimetype="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=attendance_{rtype}_report_{today_str()}.pdf"})


# --------------------------------------------------------------- settings
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        admin_row = db.execute("SELECT * FROM admin WHERE id=?", (session["admin_id"],)).fetchone()

        if action == "profile":
            name = clean(request.form.get("full_name"), 60)
            if not name:
                flash("Full name is required.", "danger")
            else:
                db.execute("UPDATE admin SET full_name=? WHERE id=?", (name, admin_row["id"]))
                db.commit()
                flash("Profile updated.", "success")

        elif action == "username":
            new_user = clean(request.form.get("new_username"), 30)
            if not check_password_hash(admin_row["password_hash"], request.form.get("current_password", "")):
                flash("Current password is incorrect.", "danger")
            elif not USER_RE.match(new_user):
                flash("Username must be 3-30 characters: letters, numbers, dot or underscore.", "danger")
            elif db.execute("SELECT 1 FROM admin WHERE username=? AND id<>?",
                            (new_user, admin_row["id"])).fetchone():
                flash("That username is already taken.", "danger")
            else:
                db.execute("UPDATE admin SET username=? WHERE id=?", (new_user, admin_row["id"]))
                db.commit()
                flash("Username changed. Use the new username next time you log in.", "success")

        elif action == "password":
            cur, new, conf = (request.form.get("current_password", ""),
                              request.form.get("new_password", ""),
                              request.form.get("confirm_password", ""))
            if not check_password_hash(admin_row["password_hash"], cur):
                flash("Current password is incorrect.", "danger")
            elif len(new) < 6:
                flash("New password must be at least 6 characters.", "danger")
            elif new != conf:
                flash("New password and confirmation do not match.", "danger")
            else:
                db.execute("UPDATE admin SET password_hash=? WHERE id=?",
                           (generate_password_hash(new), admin_row["id"]))
                db.commit()
                flash("Password changed successfully.", "success")

        elif action == "college":
            vals = {k: clean(request.form.get(k), 150) for k in
                    ("college_name", "department", "address", "academic_year")}
            risk, exc = to_int(request.form.get("risk_threshold")), to_int(request.form.get("excellent_threshold"))
            if not vals["college_name"] or not vals["academic_year"]:
                flash("College name and academic year are required.", "danger")
            elif risk is None or exc is None or not (1 <= risk < exc <= 100):
                flash("Thresholds must be numbers: 1 <= at-risk % < excellent % <= 100.", "danger")
            else:
                vals["risk_threshold"], vals["excellent_threshold"] = str(risk), str(exc)
                for k, v in vals.items():
                    db.execute("INSERT INTO settings(key,value) VALUES (?,?) "
                               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))
                db.commit()
                flash("College information saved.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html")


# ----------------------------------------------------------- error pages
@app.errorhandler(400)
def bad_request(_e):
    return render_template("error.html", code=400, title="Request expired",
                           message="Your form session expired or the request was invalid. "
                                   "Go back, refresh the page and try again."), 400


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, title="Page not found",
                           message="The page or record you are looking for does not exist."), 404


@app.errorhandler(500)
def server_error(_e):
    return render_template("error.html", code=500, title="Something went wrong",
                           message="An unexpected error occurred. Please try again."), 500


# ------------------------------------------------------------ CLI helpers
@app.cli.command("seed-demo")
def cli_seed_demo():
    """flask --app app seed-demo   -> add demo students/subjects/attendance."""
    conn = connect()
    print("Demo data added." if seed_demo(conn) else "Database already has students - nothing added.")
    conn.close()


@app.cli.command("reset-admin")
def cli_reset_admin():
    """flask --app app reset-admin   -> reset login to admin / admin123."""
    conn = connect()
    conn.execute("DELETE FROM admin")
    conn.execute("INSERT INTO admin(username,password_hash,full_name) VALUES (?,?,?)",
                 ("admin", generate_password_hash("admin123"), "Administrator"))
    conn.commit()
    conn.close()
    print("Admin reset. Login with admin / admin123")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("FLASK_DEBUG") == "1")
