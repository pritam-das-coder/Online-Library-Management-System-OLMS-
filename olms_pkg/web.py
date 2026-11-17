import html
import secrets
from http import cookies
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from .auth import AuthError, PermissionDeniedError, authenticate_user, create_user, set_user_status
from .catalog import ValidationError, add_book, add_copy, list_copies, search_books
from .circulation import (
    BusinessRuleError,
    get_active_loans,
    get_member_loans,
    issue_book_copy,
    reserve_book,
    return_book_copy,
    settle_fine,
)
from .db import get_connection

SESSIONS = {}

STYLE = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #f4f6f9; color: #1f2937; }
  header { background: #1c386b; color: #fff; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; }
  header h1 { margin: 0; font-size: 18px; }
  nav { background: #eaf0f8; padding: 10px 24px; border-bottom: 1px solid #cbd5e1; display: flex; gap: 16px; flex-wrap: wrap; }
  nav a { color: #1c386b; text-decoration: none; font-weight: 600; font-size: 14px; }
  main { max-width: 1040px; margin: 24px auto; padding: 0 16px; }
  .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 18px; margin-bottom: 20px; }
  .alert { padding: 10px 14px; border-radius: 4px; margin-bottom: 16px; font-size: 14px; }
  .alert-ok { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
  .alert-err { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { padding: 9px 10px; border-bottom: 1px solid #e2e8f0; text-align: left; }
  th { background: #f8fafc; color: #1c386b; }
  input, select { padding: 7px 10px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 14px; }
  button { background: #1c386b; color: #fff; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 14px; }
  button.secondary { background: #475569; }
  .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
</style>
"""


def page_shell(title, user, body_html, msg=None, err=None):
    nav_html = ""
    user_bar = ""
    if user:
        user_bar = f"<span>{html.escape(user['name'])} ({html.escape(user['role'])}) | <a href='/logout' style='color:#cbd5e1'>Logout</a></span>"
        links = ["<a href='/'>Catalog Search</a>", "<a href='/my-loans'>My Loans &amp; Fines</a>"]
        if user["role"] in ("Librarian", "Administrator"):
            links.append("<a href='/circulation'>Issue / Return</a>")
            links.append("<a href='/manage-books'>Manage Books</a>")
        if user["role"] == "Administrator":
            links.append("<a href='/admin/users'>Users &amp; Roles</a>")
        nav_html = f"<nav>{''.join(links)}</nav>"
    flash = ""
    if msg:
        flash += f"<div class='alert alert-ok'>{html.escape(msg)}</div>"
    if err:
        flash += f"<div class='alert alert-err'>{html.escape(err)}</div>"
    return f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>{html.escape(title)} - OLMS</title>{STYLE}</head>
<body>
<header><h1>OLMS | Kalyani Government Engineering College</h1>{user_bar}</header>
{nav_html}
<main>{flash}{body_html}</main>
</body></html>"""


class OLMSHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _current_user(self):
        cookie_hdr = self.headers.get("Cookie", "")
        c = cookies.SimpleCookie()
        c.load(cookie_hdr)
        if "olms_sid" in c:
            return SESSIONS.get(c["olms_sid"].value)
        return None

    def _send_html(self, content, status=200, extra_headers=None):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location, extra_headers=None):
        self.send_response(303)
        self.send_header("Location", location)
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()

    def _read_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        user = self._current_user()
        msg = qs.get("msg")
        err = qs.get("err")

        if path == "/logout":
            cookie_hdr = self.headers.get("Cookie", "")
            c = cookies.SimpleCookie()
            c.load(cookie_hdr)
            if "olms_sid" in c:
                SESSIONS.pop(c["olms_sid"].value, None)
            self._redirect("/login", [("Set-Cookie", "olms_sid=; Path=/; Max-Age=0")])
            return

        if path == "/login" or user is None:
            body = """
            <div class='card' style='max-width:420px;margin:40px auto;'>
              <h2>Sign In to OLMS</h2>
              <form method='POST' action='/login'>
                <p><label>Email<br><input type='email' name='email' required style='width:95%'></label></p>
                <p><label>Password<br><input type='password' name='password' required style='width:95%'></label></p>
                <button type='submit'>Login</button>
              </form>
              <p style='font-size:12px;color:#64748b;margin-top:16px;'>Demo: admin@olms.edu / Admin@123 | librarian@olms.edu / Lib@123 | student1@olms.edu / Stu@123</p>
            </div>"""
            self._send_html(page_shell("Login", None, body, msg, err))
            return

        conn = get_connection()
        try:
            if path == "/":
                q = qs.get("q", "")
                books = search_books(conn, q)
                rows_html = ""
                for b in books:
                    avail = b["available_copies"] or 0
                    act = f"<form method='POST' action='/reserve' style='display:inline'><input type='hidden' name='book_id' value='{b['book_id']}'><button type='submit' class='secondary'>Reserve</button></form>" if avail == 0 else "<span style='color:#166534'>In Stock</span>"
                    rows_html += f"<tr><td>{html.escape(b['isbn'])}</td><td><b>{html.escape(b['title'])}</b><br><small>{html.escape(b['author'])}</small></td><td>{html.escape(b['category'])}</td><td>{avail} / {b['total_copies']}</td><td>{act}</td></tr>"
                body = f"""
                <div class='card'>
                  <h2>Book Catalog Search</h2>
                  <form method='GET' action='/' class='row'>
                    <input type='text' name='q' value='{html.escape(q)}' placeholder='Search by title, author, ISBN, category...' style='flex:1;min-width:240px;'>
                    <button type='submit'>Search</button>
                  </form>
                </div>
                <div class='card'>
                  <table><thead><tr><th>ISBN</th><th>Title &amp; Author</th><th>Category</th><th>Available</th><th>Action</th></tr></thead>
                  <tbody>{rows_html or '<tr><td colspan=5>No matching books found.</td></tr>'}</tbody></table>
                </div>"""
                self._send_html(page_shell("Catalog", user, body, msg, err))
                return

            if path == "/my-loans":
                loans = get_member_loans(conn, user["user_id"])
                rows_html = "".join(
                    f"<tr><td>{l['loan_id']}</td><td>{html.escape(l['title'])}</td><td>{html.escape(l['accession_no'])}</td><td>{l['issue_date']}</td><td>{l['due_date']}</td><td>{l['return_date'] or 'Active'}</td><td>INR {l['fine_amount']:.0f} ({l['fine_status']})</td></tr>"
                    for l in loans
                )
                body = f"<div class='card'><h2>My Loans &amp; Fines</h2><table><thead><tr><th>Loan ID</th><th>Book</th><th>Accession</th><th>Issued</th><th>Due</th><th>Returned</th><th>Fine</th></tr></thead><tbody>{rows_html or '<tr><td colspan=7>No loan records.</td></tr>'}</tbody></table></div>"
                self._send_html(page_shell("My Loans", user, body, msg, err))
                return

            if path == "/circulation":
                if user["role"] not in ("Librarian", "Administrator"):
                    self._send_html(page_shell("Forbidden", user, "<div class='card'><h2>403 Forbidden</h2><p>Librarian or Administrator role required.</p></div>"), status=403)
                    return
                copies = [c for c in list_copies(conn) if c["status"] == "Available"]
                copy_opts = "".join(f"<option value='{c['copy_id']}'>{html.escape(c['accession_no'])} - {html.escape(c['title'])}</option>" for c in copies)
                members = conn.execute("SELECT user_id, name, email FROM app_user WHERE status='Active' ORDER BY user_id").fetchall()
                mem_opts = "".join(f"<option value='{m['user_id']}'>{m['user_id']} - {html.escape(m['name'])}</option>" for m in members)
                active = get_active_loans(conn)
                active_rows = "".join(
                    f"<tr><td>{a['loan_id']}</td><td>{html.escape(a['member_name'])}</td><td>{html.escape(a['title'])} ({html.escape(a['accession_no'])})</td><td>{a['issue_date']}</td><td>{a['due_date']}</td><td><form method='POST' action='/return'><input type='hidden' name='loan_id' value='{a['loan_id']}'><button type='submit'>Return</button></form></td></tr>"
                    for a in active
                )
                body = f"""
                <div class='card'><h2>Issue Book Copy</h2>
                  <form method='POST' action='/issue' class='row'>
                    <select name='member_id'>{mem_opts}</select>
                    <select name='copy_id'>{copy_opts}</select>
                    <button type='submit'>Issue Copy</button>
                  </form>
                </div>
                <div class='card'><h2>Active Loans</h2>
                  <table><thead><tr><th>ID</th><th>Member</th><th>Book Copy</th><th>Issued</th><th>Due</th><th>Action</th></tr></thead>
                  <tbody>{active_rows or '<tr><td colspan=6>No active loans.</td></tr>'}</tbody></table>
                </div>"""
                self._send_html(page_shell("Circulation", user, body, msg, err))
                return

            if path == "/manage-books":
                if user["role"] not in ("Librarian", "Administrator"):
                    self._send_html(page_shell("Forbidden", user, "<div class='card'><h2>403 Forbidden</h2></div>"), status=403)
                    return
                books = search_books(conn, "")
                book_opts = "".join(f"<option value='{b['book_id']}'>{html.escape(b['title'])} ({html.escape(b['isbn'])})</option>" for b in books)
                body = f"""
                <div class='card'><h2>Add New Book Title</h2>
                  <form method='POST' action='/books/add' class='row'>
                    <input name='isbn' placeholder='ISBN' required>
                    <input name='title' placeholder='Title' required>
                    <input name='author' placeholder='Author' required>
                    <input name='category' placeholder='Category' required>
                    <button type='submit'>Add Book</button>
                  </form>
                </div>
                <div class='card'><h2>Register Physical Copy</h2>
                  <form method='POST' action='/copies/add' class='row'>
                    <select name='book_id'>{book_opts}</select>
                    <input name='accession_no' placeholder='Accession No (e.g. ACC-6001)' required>
                    <input name='shelf_location' placeholder='Shelf Location'>
                    <button type='submit'>Add Copy</button>
                  </form>
                </div>"""
                self._send_html(page_shell("Manage Books", user, body, msg, err))
                return

            if path == "/admin/users":
                if user["role"] != "Administrator":
                    self._send_html(page_shell("Forbidden", user, "<div class='card'><h2>403 Forbidden</h2><p>Administrator role required.</p></div>"), status=403)
                    return
                users = conn.execute("SELECT user_id, name, email, role, status FROM app_user ORDER BY user_id").fetchall()
                u_rows = "".join(f"<tr><td>{u['user_id']}</td><td>{html.escape(u['name'])}</td><td>{html.escape(u['email'])}</td><td>{u['role']}</td><td>{u['status']}</td></tr>" for u in users)
                body = f"""
                <div class='card'><h2>Create User Account</h2>
                  <form method='POST' action='/admin/users/add' class='row'>
                    <input name='name' placeholder='Full Name' required>
                    <input name='email' type='email' placeholder='Email' required>
                    <input name='password' type='password' placeholder='Password' required>
                    <select name='role'><option>Member</option><option>Librarian</option><option>Administrator</option></select>
                    <button type='submit'>Create User</button>
                  </form>
                </div>
                <div class='card'><h2>Registered Users</h2>
                  <table><thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Status</th></tr></thead><tbody>{u_rows}</tbody></table>
                </div>"""
                self._send_html(page_shell("Users", user, body, msg, err))
                return

            self._send_html(page_shell("Not Found", user, "<div class='card'><h2>404 Not Found</h2></div>"), status=404)
        finally:
            conn.close()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        form = self._read_form()
        user = self._current_user()
        conn = get_connection()
        try:
            if path == "/login":
                try:
                    u = authenticate_user(conn, form.get("email", ""), form.get("password", ""))
                    sid = secrets.token_urlsafe(24)
                    SESSIONS[sid] = u
                    self._redirect("/", [("Set-Cookie", f"olms_sid={sid}; Path=/; HttpOnly")])
                except AuthError as e:
                    self._redirect(f"/login?err={e}")
                return

            if user is None:
                self._redirect("/login?err=Please+sign+in+first")
                return

            if path == "/reserve":
                try:
                    reserve_book(conn, user, int(form["book_id"]))
                    self._redirect("/?msg=Reservation+placed+successfully")
                except (BusinessRuleError, PermissionDeniedError) as e:
                    self._redirect(f"/?err={e}")
                return

            if path == "/issue":
                try:
                    res = issue_book_copy(conn, user, int(form["member_id"]), int(form["copy_id"]))
                    self._redirect(f"/circulation?msg=Issued+Loan+{res['loan_id']}+Due+{res['due_date']}")
                except (BusinessRuleError, PermissionDeniedError) as e:
                    self._redirect(f"/circulation?err={e}")
                return

            if path == "/return":
                try:
                    res = return_book_copy(conn, user, int(form["loan_id"]))
                    self._redirect(f"/circulation?msg=Returned+Loan+{res['loan_id']}+Fine+INR+{res['fine_amount']:.0f}")
                except (BusinessRuleError, PermissionDeniedError) as e:
                    self._redirect(f"/circulation?err={e}")
                return

            if path == "/books/add":
                try:
                    add_book(conn, user, form["isbn"], form["title"], form["author"], form["category"])
                    self._redirect("/manage-books?msg=Book+added+to+catalog")
                except (ValidationError, PermissionDeniedError) as e:
                    self._redirect(f"/manage-books?err={e}")
                return

            if path == "/copies/add":
                try:
                    add_copy(conn, user, int(form["book_id"]), form["accession_no"], form.get("shelf_location", ""))
                    self._redirect("/manage-books?msg=Copy+registered")
                except (ValidationError, PermissionDeniedError) as e:
                    self._redirect(f"/manage-books?err={e}")
                return

            if path == "/admin/users/add":
                try:
                    create_user(conn, user, form["name"], form["email"], form["password"], form["role"])
                    self._redirect("/admin/users?msg=User+created")
                except (PermissionDeniedError, ValueError) as e:
                    self._redirect(f"/admin/users?err={e}")
                return

            self._send_html(page_shell("Not Found", user, "<div class='card'><h2>404</h2></div>"), status=404)
        finally:
            conn.close()
