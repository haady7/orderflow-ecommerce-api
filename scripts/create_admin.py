"""Create an administrator account. Run: python -m scripts.create_admin"""
from getpass import getpass
from sqlalchemy import select
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User

email = input("Admin email: ").strip().lower()
name = input("Admin name: ").strip()
password = getpass("Admin password (8+ characters): ")
if len(password) < 8:
    raise SystemExit("Password must contain at least 8 characters.")
with SessionLocal() as db:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        user.role = "admin"
        user.name = name or user.name
        user.password_hash = hash_password(password)
        user.is_active = True
        print("Existing account promoted to administrator.")
    else:
        db.add(User(name=name, email=email, password_hash=hash_password(password), role="admin"))
        print("Administrator account created.")
    db.commit()
