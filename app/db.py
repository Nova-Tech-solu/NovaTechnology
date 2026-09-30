import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# SQLite locally; set DATABASE_URL to a PostgreSQL URL on Render.
url = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)

engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
