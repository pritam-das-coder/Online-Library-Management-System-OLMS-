from datetime import date, timedelta
from . import config
from .auth import require_role
from .db import transaction


class BusinessRuleError(Exception):
    pass


def calculate_overdue_fine(due_date_str: str, return_date_str: str, daily_rate: int = None) -> float:
    rate = config.DAILY_FINE_INR if daily_rate is None else daily_rate
    due_d = date.fromisoformat(due_date_str)
    ret_d = date.fromisoformat(return_date_str)
    overdue_days = max(0, (ret_d - due_d).days)
    return float(overdue_days * rate)


def issue_book_copy(conn, actor: dict, member_id: int, copy_id: int, issue_date_str: str = None, loan_days: int = None, max_loans: int = None) -> dict:
    require_role(actor, {"Librarian", "Administrator"})
    today_d = date.fromisoformat(issue_date_str) if issue_date_str else date.today()
    days = config.LOAN_DAYS if loan_days is None else loan_days
    limit = config.MAX_ACTIVE_LOANS if max_loans is None else max_loans
    due_d = today_d + timedelta(days=days)

    with transaction(conn):
        member = conn.execute(
            "SELECT user_id, role, status FROM app_user WHERE user_id = ?", (member_id,)
        ).fetchone()
        if member is None or member["status"] != "Active":
            raise BusinessRuleError("Target member account does not exist or is inactive.")

        active_count = conn.execute(
            "SELECT COUNT(*) FROM loan WHERE member_id = ? AND return_date IS NULL", (member_id,)
        ).fetchone()[0]
        if active_count >= limit:
            raise BusinessRuleError(f"Member has reached the maximum active loan limit ({limit}).")

        copy = conn.execute(
            "SELECT copy_id, book_id, status FROM book_copy WHERE copy_id = ?", (copy_id,)
        ).fetchone()
        if copy is None:
            raise BusinessRuleError("Book copy not found.")
        if copy["status"] != "Available":
            raise BusinessRuleError(f"Book copy is not available (current status: {copy['status']}).")

        cur = conn.execute(
            "INSERT INTO loan (member_id, copy_id, issued_by, issue_date, due_date) VALUES (?, ?, ?, ?, ?)",
            (member_id, copy_id, actor["user_id"], today_d.isoformat(), due_d.isoformat()),
        )
        conn.execute("UPDATE book_copy SET status = 'Issued' WHERE copy_id = ?", (copy_id,))
        conn.execute(
            "UPDATE reservation SET status = 'Fulfilled' WHERE member_id = ? AND book_id = ? AND status = 'Active'",
            (member_id, copy["book_id"]),
        )
        return {
            "loan_id": cur.lastrowid,
            "member_id": member_id,
            "copy_id": copy_id,
            "issue_date": today_d.isoformat(),
            "due_date": due_d.isoformat(),
        }


def return_book_copy(conn, actor: dict, loan_id: int, return_date_str: str = None) -> dict:
    require_role(actor, {"Librarian", "Administrator"})
    ret_str = return_date_str or date.today().isoformat()

    with transaction(conn):
        loan = conn.execute(
            "SELECT loan_id, copy_id, due_date, return_date FROM loan WHERE loan_id = ?", (loan_id,)
        ).fetchone()
        if loan is None:
            raise BusinessRuleError("Loan record not found.")
        if loan["return_date"] is not None:
            raise BusinessRuleError("This loan has already been returned.")

        fine_amount = calculate_overdue_fine(loan["due_date"], ret_str)
        conn.execute("UPDATE loan SET return_date = ? WHERE loan_id = ?", (ret_str, loan_id))
        conn.execute("UPDATE book_copy SET status = 'Available' WHERE copy_id = ?", (loan["copy_id"],))

        fine_id = None
        if fine_amount > 0:
            cur = conn.execute(
                "INSERT INTO fine (loan_id, amount, reason, status) VALUES (?, ?, ?, 'Unpaid')",
                (loan_id, fine_amount, "Overdue return"),
            )
            fine_id = cur.lastrowid

        return {
            "loan_id": loan_id,
            "return_date": ret_str,
            "fine_amount": fine_amount,
            "fine_id": fine_id,
        }


def reserve_book(conn, actor: dict, book_id: int) -> int:
    require_role(actor, {"Member", "Librarian", "Administrator"})
    avail = conn.execute(
        "SELECT COUNT(*) FROM book_copy WHERE book_id = ? AND status = 'Available'", (book_id,)
    ).fetchone()[0]
    if avail > 0:
        raise BusinessRuleError("Copies are currently available; reservation is not required.")

    dup = conn.execute(
        "SELECT COUNT(*) FROM reservation WHERE member_id = ? AND book_id = ? AND status = 'Active'",
        (actor["user_id"], book_id),
    ).fetchone()[0]
    if dup > 0:
        raise BusinessRuleError("You already have an active reservation for this book.")

    expires = (date.today() + timedelta(days=3)).isoformat()
    cur = conn.execute(
        "INSERT INTO reservation (member_id, book_id, expires_at, status) VALUES (?, ?, ?, 'Active')",
        (actor["user_id"], book_id, expires),
    )
    return cur.lastrowid


def settle_fine(conn, actor: dict, fine_id: int):
    require_role(actor, {"Librarian", "Administrator"})
    conn.execute(
        "UPDATE fine SET status = 'Paid', settled_at = datetime('now') WHERE fine_id = ?",
        (fine_id,),
    )


def get_member_loans(conn, member_id: int):
    rows = conn.execute(
        """
        SELECT l.loan_id, b.title, c.accession_no, l.issue_date, l.due_date, l.return_date,
               COALESCE(f.amount, 0) AS fine_amount, COALESCE(f.status, 'None') AS fine_status, f.fine_id
        FROM loan l
        JOIN book_copy c ON c.copy_id = l.copy_id
        JOIN book b ON b.book_id = c.book_id
        LEFT JOIN fine f ON f.loan_id = l.loan_id
        WHERE l.member_id = ?
        ORDER BY l.loan_id DESC
        """,
        (member_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_active_loans(conn):
    rows = conn.execute(
        """
        SELECT l.loan_id, u.name AS member_name, u.user_id AS member_id, b.title, c.accession_no,
               l.issue_date, l.due_date
        FROM loan l
        JOIN app_user u ON u.user_id = l.member_id
        JOIN book_copy c ON c.copy_id = l.copy_id
        JOIN book b ON b.book_id = c.book_id
        WHERE l.return_date IS NULL
        ORDER BY l.due_date ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]
