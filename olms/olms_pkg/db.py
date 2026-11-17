import os
import sqlite3
from contextlib import contextmanager
from . import config
from .auth import hash_password


def get_connection(db_path=None):
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def transaction(conn):
    conn.execute("BEGIN IMMEDIATE;")
    try:
        yield conn
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise


def init_db(db_path=None, seed=True):
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        if seed:
            seed_demo_data(conn)
    finally:
        conn.close()


def seed_demo_data(conn):
    existing = conn.execute("SELECT COUNT(*) FROM app_user").fetchone()[0]
    if existing > 0:
        return
    users = [
        ("System Admin", "admin@olms.edu", hash_password("Admin@123"), "Administrator", "Active"),
        ("Head Librarian", "librarian@olms.edu", hash_password("Lib@123"), "Librarian", "Active"),
        ("Aarav Sen (Student)", "student1@olms.edu", hash_password("Stu@123"), "Member", "Active"),
        ("Riya Das (Student)", "student2@olms.edu", hash_password("Stu@123"), "Member", "Active"),
    ]
    conn.executemany(
        "INSERT INTO app_user (name, email, password_hash, role, status) VALUES (?, ?, ?, ?, ?)",
        users,
    )
    books = [
        ("978-0-13-110362-7", "The C Programming Language", "Kernighan & Ritchie", "Programming", "Prentice Hall", 1988),
        ("978-0-262-03384-8", "Introduction to Algorithms", "Cormen et al.", "Algorithms", "MIT Press", 2009),
        ("978-0-07-352332-3", "Database System Concepts", "Silberschatz et al.", "Databases", "McGraw-Hill", 2019),
        ("978-0-13-359414-0", "Computer Networking", "Kurose & Ross", "Networks", "Pearson", 2017),
        ("978-1-118-06333-0", "Operating System Concepts", "Silberschatz et al.", "Operating Systems", "Wiley", 2018),
    ]
    conn.executemany(
        "INSERT INTO book (isbn, title, author, category, publisher, publication_year) VALUES (?, ?, ?, ?, ?, ?)",
        books,
    )
    copies = [
        (1, "ACC-1001", "Rack A-1", "Available"),
        (1, "ACC-1002", "Rack A-1", "Available"),
        (2, "ACC-2001", "Rack B-2", "Available"),
        (3, "ACC-3001", "Rack C-1", "Available"),
        (3, "ACC-3002", "Rack C-1", "Available"),
        (4, "ACC-4001", "Rack D-3", "Available"),
        (5, "ACC-5001", "Rack E-1", "Available"),
    ]
    conn.executemany(
        "INSERT INTO book_copy (book_id, accession_no, shelf_location, status) VALUES (?, ?, ?, ?)",
        copies,
    )
