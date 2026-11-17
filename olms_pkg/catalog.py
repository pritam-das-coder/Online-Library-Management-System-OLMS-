import sqlite3
from .auth import require_role


class ValidationError(Exception):
    pass


def search_books(conn, query: str = ""):
    q = f"%{query.strip()}%"
    rows = conn.execute(
        """
        SELECT b.book_id, b.isbn, b.title, b.author, b.category, b.publisher, b.publication_year,
               COUNT(c.copy_id) AS total_copies,
               SUM(CASE WHEN c.status = 'Available' THEN 1 ELSE 0 END) AS available_copies
        FROM book b
        LEFT JOIN book_copy c ON b.book_id = c.book_id
        WHERE b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ? OR b.category LIKE ?
        GROUP BY b.book_id
        ORDER BY b.title ASC
        """,
        (q, q, q, q),
    ).fetchall()
    return [dict(r) for r in rows]


def add_book(conn, actor: dict, isbn: str, title: str, author: str, category: str, publisher: str = "", year: int = None) -> int:
    require_role(actor, {"Librarian", "Administrator"})
    if not isbn.strip() or not title.strip() or not author.strip():
        raise ValidationError("ISBN, title, and author are required.")
    try:
        cur = conn.execute(
            "INSERT INTO book (isbn, title, author, category, publisher, publication_year) VALUES (?, ?, ?, ?, ?, ?)",
            (isbn.strip(), title.strip(), author.strip(), category.strip() or "General", publisher.strip(), year),
        )
        return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValidationError("A book with this ISBN already exists.") from exc


def add_copy(conn, actor: dict, book_id: int, accession_no: str, shelf_location: str = "") -> int:
    require_role(actor, {"Librarian", "Administrator"})
    if not accession_no.strip():
        raise ValidationError("Accession number is required.")
    try:
        cur = conn.execute(
            "INSERT INTO book_copy (book_id, accession_no, shelf_location, status) VALUES (?, ?, ?, 'Available')",
            (book_id, accession_no.strip(), shelf_location.strip()),
        )
        return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValidationError(f"Duplicate or invalid accession number: {accession_no}") from exc


def list_copies(conn):
    rows = conn.execute(
        """
        SELECT c.copy_id, c.accession_no, c.shelf_location, c.status, b.book_id, b.title, b.isbn
        FROM book_copy c
        JOIN book b ON b.book_id = c.book_id
        ORDER BY c.copy_id ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]
