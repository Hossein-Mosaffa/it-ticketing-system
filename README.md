# IT Ticketing System (Python & SQL)

A small Flask and SQLite web application for creating, tracking, and managing IT support tickets. The supplied Persian customer-support templates have been adapted into an English IT help-desk workflow.

## Features

- Submit an IT support ticket with a category, description, and optional attachment.
- Generate a unique tracking code for each ticket.
- Track a ticket using its tracking code and phone number.
- Admin sign-in and ticket dashboard.
- Admin responses update the ticket status from Open to Answered.
- Download ticket attachments from the protected admin area.
- Basic reports showing ticket totals and category counts.
- SQLite database created automatically on first run.

## Run locally

Python 3.9 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Admin login

Demo defaults:

- Username: `admin`
- Password: `admin123`

Change these before using the app with real users. On Linux/macOS:

```bash
export ADMIN_USERNAME="your-admin"
export ADMIN_PASSWORD="a-long-unique-password"
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python app.py
```

On Windows PowerShell:

```powershell
$env:ADMIN_USERNAME = "your-admin"
$env:ADMIN_PASSWORD = "a-long-unique-password"
$env:SECRET_KEY = "your-long-random-secret"
python app.py
```

The app stores records in `tickets.db` and uploaded files in `uploads/`. Back up both.

## Project structure

```text
it_ticketing_system/
├── app.py
├── requirements.txt
├── README.md
├── tickets.db             # created automatically after first run
├── uploads/               # created automatically
├── static/
│   └── style.css
└── templates/
    ├── admin.html
    ├── check_status.html
    ├── client.html
    ├── error.html
    ├── login.html
    ├── report.html
    └── ticket_submitted.html
```

## Notes

- This is a starter/internal-use application, not a hardened public production deployment.
- Run behind HTTPS and a production WSGI server before exposing it to the internet.
- Set a strong `SECRET_KEY` and unique admin credentials.
- The app includes basic CSRF checks, input validation, upload extension checks, and a 10 MB upload limit. For a public deployment, consider stronger rate limiting, audit logging, role management, malware scanning, and stricter file-content validation.
