import os
import secrets
import sqlite3
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, abort, flash, redirect, render_template, request,
    send_from_directory, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "tickets.db"
UPLOAD_FOLDER = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "pdf", "txt", "doc", "docx",
    "xls", "xlsx", "csv", "zip", "log"
}
MAX_UPLOAD_MB = 10

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment"),
    MAX_CONTENT_LENGTH=MAX_UPLOAD_MB * 1024 * 1024,
    UPLOAD_FOLDER=str(UPLOAD_FOLDER),
)
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Configure these environment variables before using the app outside a demo.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin123"))
)

CATEGORIES = ["Hardware", "Software", "Network", "Account & Access", "Other"]


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                response TEXT NOT NULL DEFAULT '',
                attachment TEXT,
                tracking_code TEXT NOT NULL UNIQUE
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_tracking ON tickets(tracking_code)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": csrf_token}


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        sent_token = request.form.get("_csrf_token", "")
        if not sent_token or not secrets.compare_digest(sent_token, session.get("_csrf_token", "")):
            abort(400, description="Invalid or missing security token. Refresh the page and try again.")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def make_tracking_code():
    return uuid.uuid4().hex[:10].upper()


@app.route("/")
def home():
    return render_template("client.html", categories=CATEGORIES)


@app.route("/submit_ticket", methods=["POST"])
def submit_ticket():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    category = request.form.get("problem_select", "").strip()
    description = request.form.get("problem", "").strip()

    if not name or not phone or not category or not description:
        flash("Please complete all required fields.", "danger")
        return redirect(url_for("home"))
    if len(name) > 120 or len(description) > 5000:
        flash("The name or description is too long.", "danger")
        return redirect(url_for("home"))
    if not phone.isdigit() or not 7 <= len(phone) <= 15:
        flash("Enter a valid phone number using digits only.", "danger")
        return redirect(url_for("home"))
    if category not in CATEGORIES:
        abort(400)

    attachment_name = None
    uploaded = request.files.get("attachment")
    if uploaded and uploaded.filename:
        if not allowed_file(uploaded.filename):
            flash("This file type is not allowed.", "danger")
            return redirect(url_for("home"))
        safe_name = secure_filename(uploaded.filename)
        attachment_name = f"{uuid.uuid4().hex}_{safe_name}"
        uploaded.save(UPLOAD_FOLDER / attachment_name)

    tracking_code = make_tracking_code()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_db() as db:
            db.execute("""
                INSERT INTO tickets
                (name, phone, category, description, created_at, status, response, attachment, tracking_code)
                VALUES (?, ?, ?, ?, ?, 'Open', '', ?, ?)
            """, (name, phone, category, description, created_at, attachment_name, tracking_code))
    except Exception:
        if attachment_name:
            (UPLOAD_FOLDER / attachment_name).unlink(missing_ok=True)
        raise

    return render_template("ticket_submitted.html", tracking_code=tracking_code)


@app.route("/check_status", methods=["GET", "POST"])
def check_status():
    ticket = None
    if request.method == "POST":
        tracking_code = request.form.get("tracking_code", "").strip().upper()
        phone = request.form.get("phone", "").strip()
        with get_db() as db:
            ticket = db.execute("""
                SELECT id, name, category, description, created_at, status, response, tracking_code
                FROM tickets
                WHERE tracking_code = ? AND phone = ?
            """, (tracking_code, phone)).fetchone()
        if ticket is None:
            flash("No ticket matched that tracking code and phone number.", "warning")
    return render_template("check_status.html", ticket=ticket)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            flash("You are now signed in.", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("admin"))
        flash("Incorrect username or password.", "danger")
    return render_template("login.html")


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        ticket_id = request.form.get("ticket_id", type=int)
        response = request.form.get("response", "").strip()
        if not ticket_id or not response:
            flash("Enter a response before submitting.", "warning")
        else:
            with get_db() as db:
                cursor = db.execute("""
                    UPDATE tickets SET response = ?, status = 'Answered'
                    WHERE id = ?
                """, (response[:5000], ticket_id))
            if cursor.rowcount:
                flash("The ticket response has been saved.", "success")
            else:
                flash("Ticket not found.", "danger")
        return redirect(url_for("admin"))

    with get_db() as db:
        tickets = db.execute("""
            SELECT id, name, phone, category, description, created_at,
                   status, response, attachment, tracking_code
            FROM tickets ORDER BY
                CASE status WHEN 'Open' THEN 0 ELSE 1 END,
                id DESC
        """).fetchall()
    return render_template("admin.html", tickets=tickets)


@app.route("/download_attachment/<path:filename>")
@admin_required
def download_attachment(filename):
    # Only serve files stored in the upload directory.
    if Path(filename).name != filename:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


@app.route("/report")
@admin_required
def report():
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        open_count = db.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Open'").fetchone()[0]
        answered_count = db.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Answered'").fetchone()[0]
        by_category = db.execute("""
            SELECT category, COUNT(*) AS count
            FROM tickets GROUP BY category ORDER BY count DESC
        """).fetchall()
    return render_template(
        "report.html", total=total, open_count=open_count,
        answered_count=answered_count, by_category=by_category
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


@app.errorhandler(413)
def too_large(_error):
    flash(f"File is too large. Maximum size is {MAX_UPLOAD_MB} MB.", "danger")
    return redirect(request.referrer or url_for("home"))


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=getattr(error, "description", "Bad request")), 400


init_db()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1"
    )
