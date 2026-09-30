from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Office(Base):
    """One row per API key holder (an office, department, or the desktop software)."""
    __tablename__ = "offices"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True)

class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    matric_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(120))
    level: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    photo_path: Mapped[str | None] = mapped_column(String(300))
    extra: Mapped[dict] = mapped_column(JSON, default=dict)  # any extra details, no migration needed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="student", cascade="all, delete-orphan")

class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("code", "semester"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20))
    semester: Mapped[str] = mapped_column(String(40))

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("student_id", "course_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    classes_attended: Mapped[int] = mapped_column(Integer)
    total_classes: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    student: Mapped[Student] = relationship(back_populates="records")
    course: Mapped[Course] = relationship()
