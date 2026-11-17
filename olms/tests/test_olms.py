import os
import tempfile
import unittest

from olms_pkg.auth import AuthError, PermissionDeniedError, authenticate_user, create_user, set_user_status
from olms_pkg.catalog import ValidationError, add_book, add_copy, search_books
from olms_pkg.circulation import (
    BusinessRuleError,
    calculate_overdue_fine,
    issue_book_copy,
    reserve_book,
    return_book_copy,
    settle_fine,
)
from olms_pkg.db import get_connection, init_db


class TestOLMS(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.tmp.close()
        init_db(self.tmp.name, seed=True)
        self.conn = get_connection(self.tmp.name)
        self.admin = authenticate_user(self.conn, "admin@olms.edu", "Admin@123")
        self.librarian = authenticate_user(self.conn, "librarian@olms.edu", "Lib@123")
        self.student1 = authenticate_user(self.conn, "student1@olms.edu", "Stu@123")
        self.student2 = authenticate_user(self.conn, "student2@olms.edu", "Stu@123")

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.tmp.name):
            os.remove(self.tmp.name)

    def test_tc_olms_001_valid_login(self):
        self.assertEqual(self.librarian["role"], "Librarian")

    def test_tc_olms_002_invalid_password(self):
        with self.assertRaises(AuthError):
            authenticate_user(self.conn, "librarian@olms.edu", "WrongPassword")

    def test_tc_olms_003_rbac_member_cannot_create_user(self):
        with self.assertRaises(PermissionDeniedError):
            create_user(self.conn, self.student1, "X", "x@olms.edu", "Pass@123", "Member")

    def test_tc_olms_004_duplicate_accession_rejected(self):
        with self.assertRaises(ValidationError):
            add_copy(self.conn, self.librarian, 1, "ACC-1001", "Rack A-1")

    def test_tc_olms_005_catalog_search(self):
        res = search_books(self.conn, "Algorithms")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["available_copies"], 1)

    def test_tc_olms_006_issue_available_copy(self):
        loan = issue_book_copy(self.conn, self.librarian, self.student1["user_id"], 1, "2026-11-01")
        self.assertEqual(loan["due_date"], "2026-11-15")
        status = self.conn.execute("SELECT status FROM book_copy WHERE copy_id = 1").fetchone()[0]
        self.assertEqual(status, "Issued")

    def test_tc_olms_007_max_loan_limit_enforced(self):
        issue_book_copy(self.conn, self.librarian, self.student1["user_id"], 1, "2026-11-01")
        issue_book_copy(self.conn, self.librarian, self.student1["user_id"], 2, "2026-11-01")
        issue_book_copy(self.conn, self.librarian, self.student1["user_id"], 3, "2026-11-01")
        with self.assertRaises(BusinessRuleError):
            issue_book_copy(self.conn, self.librarian, self.student1["user_id"], 4, "2026-11-01")

    def test_tc_olms_008_cannot_issue_already_issued_copy(self):
        issue_book_copy(self.conn, self.librarian, self.student1["user_id"], 1, "2026-11-01")
        with self.assertRaises(BusinessRuleError):
            issue_book_copy(self.conn, self.librarian, self.student2["user_id"], 1, "2026-11-01")

    def test_tc_olms_009_return_on_time_no_fine(self):
        loan = issue_book_copy(self.conn, self.librarian, self.student1["user_id"], 1, "2026-11-01")
        ret = return_book_copy(self.conn, self.librarian, loan["loan_id"], "2026-11-15")
        self.assertEqual(ret["fine_amount"], 0.0)
        status = self.conn.execute("SELECT status FROM book_copy WHERE copy_id = 1").fetchone()[0]
        self.assertEqual(status, "Available")

    def test_tc_olms_010_return_overdue_4_days_fine_20(self):
        loan = issue_book_copy(self.conn, self.librarian, self.student1["user_id"], 1, "2026-11-01")
        ret = return_book_copy(self.conn, self.librarian, loan["loan_id"], "2026-11-19")
        self.assertEqual(ret["fine_amount"], 20.0)
        settle_fine(self.conn, self.librarian, ret["fine_id"])
        f_status = self.conn.execute("SELECT status FROM fine WHERE fine_id = ?", (ret["fine_id"],)).fetchone()[0]
        self.assertEqual(f_status, "Paid")

    def test_reservation_when_unavailable(self):
        # Book 2 has 1 copy (copy_id = 3)
        issue_book_copy(self.conn, self.librarian, self.student1["user_id"], 3, "2026-11-01")
        res_id = reserve_book(self.conn, self.student2, 2)
        self.assertGreater(res_id, 0)
        with self.assertRaises(BusinessRuleError):
            reserve_book(self.conn, self.student2, 2)


if __name__ == "__main__":
    unittest.main()
