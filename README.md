# Online Library Management System (OLMS)

Academic prototype for the **Software Engineering Laboratory (KGEC)**.
Built using the Python 3 standard library (`http.server`, `sqlite3`, `hashlib`, `unittest`) with zero external third-party dependencies.

## Prerequisites

- **Python 3.8 or higher** installed and added to `PATH`
- A modern desktop web browser (Chrome, Firefox, or Edge)

Check your Python command before running:
- **Windows (PowerShell / CMD):** `python --version` (or `py --version`)
- **Linux / macOS:** `python3 --version`

## Quick Start

### Windows (PowerShell / Command Prompt)

1. *(Optional)* Copy `.env.example` to `.env` (defaults work out of the box):
   ```powershell
   copy .env.example .env
   ```
2. Start the application:
   ```powershell
   python app.py
   ```
   *(If `python` is not recognized, use `py app.py`.)*

### Linux / macOS

1. *(Optional)* Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Start the application:
   ```bash
   python3 app.py
   ```

Once started, open `http://127.0.0.1:8000` in your browser. Press `Ctrl + C` in the terminal to stop the server.

## Synthetic Demo Accounts

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@olms.edu` | `Admin@123` |
| Librarian | `librarian@olms.edu` | `Lib@123` |
| Member / Student 1 | `student1@olms.edu` | `Stu@123` |
| Member / Student 2 | `student2@olms.edu` | `Stu@123` |

*(All accounts and book records are synthetic demonstration data.)*

## Running Automated Tests

- **Windows:**
  ```powershell
  python -m unittest discover -s tests -v
  ```
- **Linux / macOS:**
  ```bash
  python3 -m unittest discover -s tests -v
  ```

## Database Backup & Restore (Cross-Platform)

Using Python's built-in `sqlite3` module works on Windows, Linux, and macOS without requiring the `sqlite3` CLI tool:

- **Create Backup (`olms_backup.db`):**
  ```bash
  python -c "import sqlite3; s=sqlite3.connect('olms.db'); d=sqlite3.connect('olms_backup.db'); s.backup(d); d.close(); s.close(); print('Backup OK')"
  ```
  *(Use `python3` instead of `python` on Linux/macOS if needed.)*

- **Restore Backup & Verify Integrity:**
  ```bash
  python -c "import sqlite3; s=sqlite3.connect('olms_backup.db'); d=sqlite3.connect('olms.db'); s.backup(d); d.close(); s.close(); print('Restore OK')"
  ```
