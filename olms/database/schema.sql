PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS app_user (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Administrator', 'Librarian', 'Member')),
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS book (
    book_id INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    category TEXT NOT NULL,
    publisher TEXT,
    publication_year INTEGER
);

CREATE TABLE IF NOT EXISTS book_copy (
    copy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
    accession_no TEXT NOT NULL UNIQUE,
    shelf_location TEXT,
    status TEXT NOT NULL DEFAULT 'Available'
        CHECK (status IN ('Available', 'Reserved', 'Issued', 'Overdue', 'Lost'))
);

CREATE TABLE IF NOT EXISTS reservation (
    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL REFERENCES app_user(user_id),
    book_id INTEGER NOT NULL REFERENCES book(book_id),
    reserved_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active'
        CHECK (status IN ('Active', 'Fulfilled', 'Cancelled', 'Expired'))
);

CREATE TABLE IF NOT EXISTS loan (
    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL REFERENCES app_user(user_id),
    copy_id INTEGER NOT NULL REFERENCES book_copy(copy_id),
    issued_by INTEGER NOT NULL REFERENCES app_user(user_id),
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    return_date TEXT NULL,
    CONSTRAINT ck_loan_dates CHECK (due_date >= issue_date)
);

CREATE TABLE IF NOT EXISTS fine (
    fine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id INTEGER NOT NULL UNIQUE REFERENCES loan(loan_id),
    amount REAL NOT NULL CHECK (amount >= 0),
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Unpaid' CHECK (status IN ('Unpaid', 'Paid')),
    settled_at TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_book_title ON book(title);
CREATE INDEX IF NOT EXISTS idx_book_isbn ON book(isbn);
CREATE INDEX IF NOT EXISTS idx_loan_member ON loan(member_id);
