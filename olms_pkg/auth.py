import hashlib
import hmac
import secrets


class AuthError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _, salt, hex_digest = stored_hash.split("$", 2)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return hmac.compare_digest(dk.hex(), hex_digest)


def authenticate_user(conn, email: str, password: str) -> dict:
    row = conn.execute(
        "SELECT user_id, name, email, password_hash, role, status FROM app_user WHERE email = ?",
        (email.strip().lower(),),
    ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        raise AuthError("Invalid email or password.")
    if row["status"] != "Active":
        raise AuthError("Account is inactive. Contact the administrator.")
    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "status": row["status"],
    }


def require_role(user: dict, allowed_roles):
    if user is None:
        raise AuthError("Authentication required.")
    if user["role"] not in allowed_roles:
        raise PermissionDeniedError("Access denied for your role.")


def create_user(conn, actor: dict, name: str, email: str, password: str, role: str) -> int:
    require_role(actor, {"Administrator"})
    if role not in {"Administrator", "Librarian", "Member"}:
        raise ValueError("Invalid role.")
    cur = conn.execute(
        "INSERT INTO app_user (name, email, password_hash, role, status) VALUES (?, ?, ?, ?, 'Active')",
        (name.strip(), email.strip().lower(), hash_password(password), role),
    )
    return cur.lastrowid


def set_user_status(conn, actor: dict, target_user_id: int, status: str):
    require_role(actor, {"Administrator"})
    if status not in {"Active", "Inactive"}:
        raise ValueError("Invalid status.")
    conn.execute("UPDATE app_user SET status = ? WHERE user_id = ?", (status, target_user_id))
