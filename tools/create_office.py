"""Create an API key.  Usage: python -m tools.create_office "Exams Office" """
import secrets, sys
from sqlalchemy import select
from app.db import SessionLocal, engine
from app.main import hash_key
from app.models import Base, Office

Base.metadata.create_all(engine)
name = sys.argv[1] if len(sys.argv) > 1 else "Default Office"
key = secrets.token_urlsafe(32)
with SessionLocal() as db:
    if db.scalar(select(Office).where(Office.name == name)):
        sys.exit(f"Office '{name}' already exists")
    db.add(Office(name=name, api_key_hash=hash_key(key))); db.commit()
print(f"API key for {name} (shown once, store it safely):\n{key}")
