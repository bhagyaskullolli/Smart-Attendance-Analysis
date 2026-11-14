"""
analysis.py
-----------
All attendance calculations live here (percentages, summaries, chart series,
report tables).  Every function reads REAL rows from the SQLite database -
nothing is hard-coded.

Filter dictionary keys understood by the functions (all optional):
    student_id, subject_id   -> database ids (int)
    date                     -> "YYYY-MM-DD"   (exact day, overrides month)
    month                    -> "YYYY-MM"
    date_from, date_to       -> "YYYY-MM-DD"   (range, used by reports)
"""
from datetime import datetime

DEFAULT_RISK = 75        # below this %  -> "At Risk"
DEFAULT_EXCELLENT = 90   # this % or more -> "Excellent"


# ----------------------------------------------------------------- helpers
def pct(present, total):
    """Percentage rounded to 1 decimal, or None when there is no data."""
    return round(present * 100.0 / total, 1) if total else None


def classify(p, risk=DEFAULT_RISK, excellent=DEFAULT_EXCELLENT):
    """Turn a percentage into a status label."""
    if p is None:
        return "No Data"
    if p < risk:
        return "At Risk"
    if p >= excellent:
        return "Excellent"
    if p < risk + 10:
        return "Low"
    return "Good"


def fmt_pct(p):
    return "-" if p is None else f"{p:.1f}%"


def fmt_day(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b")
    except (TypeError, ValueError):
        return str(iso)


def fmt_month(ym):
    try:
        return datetime.strptime(ym, "%Y-%m").strftime("%b %Y")
    except (TypeError, ValueError):
        return str(ym)


def build_filter(f, include_student=True, include_subject=True):
    """Return (sql_condition, params) for the attendance table aliased as 'a'."""
    clauses, params = [], []
    if include_student and f.get("student_id"):
        clauses.append("a.student_id = ?")
        params.append(int(f["student_id"]))
    if include_subject and f.get("subject_id"):
        clauses.append("a.subject_id = ?")
        params.append(int(f["subject_id"]))
    if f.get("date"):
        clauses.append("a.date = ?")
        params.append(f["date"])
    elif f.get("month"):
        clauses.append("substr(a.date, 1, 7) = ?")
        params.append(f["month"])
    if f.get("date_from"):
        clauses.append("a.date >= ?")
        params.append(f["date_from"])
    if f.get("date_to"):
        clauses.append("a.date <= ?")
        params.append(f["date_to"])
    return (" AND ".join(clauses) if clauses else "1=1"), params


# --------------------------------------------------------------- summaries
def overall(conn, f=None):
    """Total / present / absent / percentage for the given filters."""
    f = f or {}
    clause, params = build_filter(f)
    row = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END),0) AS present "
        f"FROM attendance a WHERE {clause}", params).fetchone()
    total, present = row["total"], row["present"]
    return {"total": total, "present": present, "absent": total - present,
            "percent": pct(present, total)}


def student_summary(conn, f=None, risk=DEFAULT_RISK, excellent=DEFAULT_EXCELLENT):
    """One row per student with total/present/absent/percent/status."""
    f = f or {}
    clause, params = build_filter(f, include_student=False)
    where, wparams = "", []
    if f.get("student_id"):
        where, wparams = "WHERE s.id = ?", [int(f["student_id"])]
    rows = conn.execute(
        "SELECT s.id, s.reg_no, s.name, s.class_name, s.email, s.phone, "
        "COUNT(a.id) AS total, "
        "COALESCE(SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END),0) AS present "
        "FROM students s LEFT JOIN attendance a "
        f"ON a.student_id = s.id AND {clause} {where} "
        "GROUP BY s.id ORDER BY s.name COLLATE NOCASE", params + wparams).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["absent"] = d["total"] - d["present"]
        d["percent"] = pct(d["present"], d["total"])
        d["status"] = classify(d["percent"], risk, excellent)
        out.append(d)
    return out


def subject_summary(conn, f=None, risk=DEFAULT_RISK, excellent=DEFAULT_EXCELLENT):
    """One row per subject with total/present/absent/percent/status."""
    f = f or {}
    clause, params = build_filter(f, include_subject=False)
    where, wparams = "", []
    if f.get("subject_id"):
        where, wparams = "WHERE sub.id = ?", [int(f["subject_id"])]
    rows = conn.execute(
        "SELECT sub.id, sub.code, sub.name, sub.semester, sub.teacher, "
        "COUNT(a.id) AS total, "
        "COALESCE(SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END),0) AS present "
        "FROM subjects sub LEFT JOIN attendance a "
        f"ON a.subject_id = sub.id AND {clause} {where} "
        "GROUP BY sub.id ORDER BY sub.name COLLATE NOCASE", params + wparams).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["absent"] = d["total"] - d["present"]
        d["percent"] = pct(d["present"], d["total"])
        d["status"] = classify(d["percent"], risk, excellent)
        out.append(d)
    return out


# ------------------------------------------------------------ chart series
def _series(conn, f, expr, label_fn):
    clause, params = build_filter(f)
    rows = conn.execute(
        f"SELECT {expr} AS k, COUNT(*) AS total, "
        "COALESCE(SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END),0) AS present "
        f"FROM attendance a WHERE {clause} GROUP BY k ORDER BY k", params).fetchall()
    out = []
    for r in rows:
        out.append({"key": r["k"], "label": label_fn(r["k"]), "total": r["total"],
                    "present": r["present"], "absent": r["total"] - r["present"],
                    "percent": pct(r["present"], r["total"])})
    return out


def daily_series(conn, f=None, limit=30):
    data = _series(conn, f or {}, "a.date", fmt_day)
    return data[-limit:]


def weekly_series(conn, f=None, limit=12):
    # Monday of the week that contains the attendance date
    expr = ("date(a.date, '-' || ((CAST(strftime('%w', a.date) AS INTEGER) + 6) % 7) "
            "|| ' days')")
    data = _series(conn, f or {}, expr, lambda k: "Wk " + fmt_day(k))
    return data[-limit:]


def monthly_series(conn, f=None, limit=12):
    data = _series(conn, f or {}, "substr(a.date, 1, 7)", fmt_month)
    return data[-limit:]


# --------------------------------------------------------------- dashboard
def dashboard_data(conn, today, risk=DEFAULT_RISK, excellent=DEFAULT_EXCELLENT):
    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_subjects = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    t = overall(conn, {"date": today})
    students = student_summary(conn, {}, risk, excellent)
    at_risk = [s for s in students if s["status"] == "At Risk"]
    pct_map = {s["id"]: s["percent"] for s in students}

    recent_rows = conn.execute(
        "SELECT a.student_id, a.date, a.status, s.name, s.reg_no, "
        "sub.name AS subject, sub.code "
        "FROM attendance a JOIN students s ON s.id = a.student_id "
        "JOIN subjects sub ON sub.id = a.subject_id "
        "ORDER BY a.date DESC, a.updated_at DESC, a.id DESC LIMIT 10").fetchall()
    recent = []
    for r in recent_rows:
        d = dict(r)
        d["percent"] = pct_map.get(d["student_id"])
        recent.append(d)

    daily = list(reversed(_series(conn, {}, "a.date", fmt_day)[-7:]))

    ranked = sorted((s for s in students if s["percent"] is not None),
                    key=lambda s: s["percent"])
    return {
        "total_students": total_students,
        "total_subjects": total_subjects,
        "present_today": t["present"],
        "absent_today": t["absent"],
        "marked_today": t["total"],
        "at_risk_count": len(at_risk),
        "overall": overall(conn, {}),
        "monthly": monthly_series(conn, {}, 6),
        "recent": recent,
        "daily": daily,
        "lowest_students": ranked[:8],
    }


# ----------------------------------------------------------------- reports
REPORT_TYPES = [
    ("student", "Student Attendance"),
    ("subject", "Subject Attendance"),
    ("daily", "Daily Attendance"),
    ("monthly", "Monthly Attendance"),
    ("overall", "Overall Attendance"),
    ("low", "Low Attendance"),
]


def build_report(conn, rtype, f, today, risk=DEFAULT_RISK, excellent=DEFAULT_EXCELLENT):
    """
    Return a dict: title, columns, rows, note.
    The same dict feeds the HTML table, the CSV export and the PDF export.
    """
    f = dict(f or {})
    title = dict(REPORT_TYPES).get(rtype, "Student Attendance") + " Report"
    note = ""

    if rtype == "subject":
        rows = [[r["code"], r["name"], r["teacher"], r["total"], r["present"],
                 r["absent"], fmt_pct(r["percent"]), r["status"]]
                for r in subject_summary(conn, f, risk, excellent)]
        cols = ["Code", "Subject", "Teacher", "Total", "Present", "Absent", "%", "Status"]

    elif rtype == "daily":
        if not f.get("date_from") and not f.get("date_to") and not f.get("date"):
            f["date_from"] = f["date_to"] = today
            note = f"No date chosen - showing today ({today})."
        clause, params = build_filter(f)
        recs = conn.execute(
            "SELECT a.date, s.reg_no, s.name, sub.code, sub.name AS subject, a.status "
            "FROM attendance a JOIN students s ON s.id = a.student_id "
            "JOIN subjects sub ON sub.id = a.subject_id "
            f"WHERE {clause} ORDER BY a.date DESC, sub.name, s.name", params).fetchall()
        rows = [[r["date"], r["reg_no"], r["name"], f'{r["code"]} - {r["subject"]}',
                 r["status"]] for r in recs]
        cols = ["Date", "Reg. No", "Student", "Subject", "Status"]

    elif rtype == "monthly":
        rows = [[m["label"], m["total"], m["present"], m["absent"], fmt_pct(m["percent"])]
                for m in _series(conn, f, "substr(a.date, 1, 7)", fmt_month)]
        cols = ["Month", "Total Records", "Present", "Absent", "%"]

    elif rtype == "overall":
        o = overall(conn, f)
        studs = student_summary(conn, f, risk, excellent)
        n_students = len(studs)
        n_subjects = len(subject_summary(conn, f, risk, excellent))
        rows = [
            ["Total students", n_students],
            ["Total subjects", n_subjects],
            ["Attendance records", o["total"]],
            ["Present", o["present"]],
            ["Absent", o["absent"]],
            ["Overall attendance", fmt_pct(o["percent"])],
            [f"At-risk students (below {risk}%)",
             sum(1 for s in studs if s["status"] == "At Risk")],
            [f"Excellent students ({excellent}% or more)",
             sum(1 for s in studs if s["status"] == "Excellent")],
        ]
        cols = ["Measure", "Value"]

    elif rtype == "low":
        limit = risk + 10
        studs = [s for s in student_summary(conn, f, risk, excellent)
                 if s["percent"] is not None and s["percent"] < limit]
        studs.sort(key=lambda s: s["percent"])
        rows = [[s["reg_no"], s["name"], s["class_name"], s["total"], s["present"],
                 s["absent"], fmt_pct(s["percent"]), s["status"]] for s in studs]
        cols = ["Reg. No", "Student", "Class", "Total", "Present", "Absent", "%", "Status"]
        note = f"Students below {limit}% (At Risk is below {risk}%)."

    else:  # student (default)
        rows = [[s["reg_no"], s["name"], s["class_name"], s["total"], s["present"],
                 s["absent"], fmt_pct(s["percent"]), s["status"]]
                for s in student_summary(conn, f, risk, excellent)]
        cols = ["Reg. No", "Student", "Class", "Total", "Present", "Absent", "%", "Status"]

    return {"title": title, "columns": cols, "rows": rows, "note": note}
