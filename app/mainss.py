import hashlib, io, json, os, uuid
from pathlib import Path
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .db import engine, get_db
from .models import AttendanceRecord, Base, Course, Office, Student

Base.metadata.create_all(engine)
# NOTE: Render's disk is ephemeral. Point PHOTO_DIR at a persistent disk, or swap save_photo() for S3/Cloudinary.
PHOTO_DIR = Path(os.getenv("PHOTO_DIR", "photos"))
PHOTO_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Attendance Hub")

# ---------- auth ----------
def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def require_key(x_api_key: str = Header(...), db: Session = Depends(get_db)) -> Office:
    office = db.scalar(select(Office).where(Office.api_key_hash == hash_key(x_api_key)))
    if not office:
        raise HTTPException(401, "Invalid API key")
    return office

# ---------- helpers ----------
def norm(matric: str) -> str:
    return matric.strip().upper()

def save_photo(file: UploadFile) -> str:
    try:
        img = Image.open(io.BytesIO(file.file.read())).convert("RGB")
    except Exception:
        raise HTTPException(400, "Photo is not a valid image")
    img.thumbnail((500, 500))
    name = f"{uuid.uuid4().hex}.jpg"
    img.save(PHOTO_DIR / name, "JPEG", quality=85)
    return name

def student_out(s: Student, with_records=False) -> dict:
    out = {"matric_number": s.matric_number, "full_name": s.full_name, "department": s.department,
           "level": s.level, "email": s.email, "phone": s.phone, "extra": s.extra,
           "photo_url": f"/photos/{s.photo_path}" if s.photo_path else None}
    if with_records:
        out["attendance"] = [
            {"course": r.course.code, "semester": r.course.semester,
             "attended": r.classes_attended, "total": r.total_classes,
             "percent": round(100 * r.classes_attended / r.total_classes, 1) if r.total_classes else None,
             "updated_at": r.updated_at.isoformat()} for r in s.records]
    return out

def parse_extra(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        assert isinstance(data, dict)
        return data
    except Exception:
        raise HTTPException(400, "'extra' must be a JSON object, e.g. {\"state\": \"Cross River\"}")

# ---------- students ----------
@app.get("/api/health")
def health():
    return {"ok": True}

@app.post("/api/students", status_code=201)
def register_student(matric_number: str = Form(...), full_name: str = Form(...),
                     department: str = Form(None), level: str = Form(None),
                     email: str = Form(None), phone: str = Form(None), extra: str = Form(None),
                     photo: UploadFile = File(None),
                     db: Session = Depends(get_db), _=Depends(require_key)):
    matric = norm(matric_number)
    if db.scalar(select(Student).where(Student.matric_number == matric)):
        raise HTTPException(409, f"{matric} is already registered")
    s = Student(matric_number=matric, full_name=full_name.strip(), department=department, level=level,
                email=email, phone=phone, extra=parse_extra(extra),
                photo_path=save_photo(photo) if photo and photo.filename else None)
    db.add(s); db.commit()
    return student_out(s)

@app.get("/api/students")
def list_students(q: str = "", db: Session = Depends(get_db), _=Depends(require_key)):
    stmt = select(Student).order_by(Student.full_name).limit(500)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Student.matric_number.ilike(like), Student.full_name.ilike(like)))
    return [student_out(s) for s in db.scalars(stmt)]

@app.get("/api/students/{matric:path}")
def get_student(matric: str, db: Session = Depends(get_db), _=Depends(require_key)):
    s = db.scalar(select(Student).where(Student.matric_number == norm(matric)))
    if not s:
        raise HTTPException(404, "Student not found")
    return student_out(s, with_records=True)

@app.put("/api/students/{matric:path}")
def update_student(matric: str, full_name: str = Form(None), department: str = Form(None),
                   level: str = Form(None), email: str = Form(None), phone: str = Form(None),
                   extra: str = Form(None), photo: UploadFile = File(None),
                   db: Session = Depends(get_db), _=Depends(require_key)):
    s = db.scalar(select(Student).where(Student.matric_number == norm(matric)))
    if not s:
        raise HTTPException(404, "Student not found")
    for field, val in dict(full_name=full_name, department=department, level=level, email=email, phone=phone).items():
        if val is not None:
            setattr(s, field, val)
    if extra:
        s.extra = {**(s.extra or {}), **parse_extra(extra)}
    if photo and photo.filename:
        s.photo_path = save_photo(photo)
    db.commit()
    return student_out(s, with_records=True)

# ---------- attendance upload (called by the desktop software) ----------
class Row(BaseModel):
    student_id: str
    classes_attended: int = Field(ge=0)

class Upload(BaseModel):
    course_code: str
    semester: str
    total_classes: int = Field(ge=0)
    records: list[Row]

@app.post("/api/attendance/upload")
def upload_attendance(p: Upload, db: Session = Depends(get_db), _=Depends(require_key)):
    code, sem = p.course_code.strip().upper(), p.semester.strip()
    course = db.scalar(select(Course).where(Course.code == code, Course.semester == sem))
    if not course:
        course = Course(code=code, semester=sem); db.add(course); db.flush()

    ids = {norm(r.student_id): r for r in p.records}
    students = {s.matric_number: s for s in db.scalars(select(Student).where(Student.matric_number.in_(ids)))}
    existing = {r.student_id: r for r in db.scalars(select(AttendanceRecord).where(AttendanceRecord.course_id == course.id))}

    matched, unmatched, flagged = 0, [], []
    for matric, row in ids.items():
        s = students.get(matric)
        if not s:
            unmatched.append(matric); continue
        if p.total_classes and row.classes_attended > p.total_classes:
            flagged.append(matric)  # still saved; shown so you can check the source data
        rec = existing.get(s.id)
        if rec:
            rec.classes_attended, rec.total_classes = row.classes_attended, p.total_classes
        else:
            db.add(AttendanceRecord(student_id=s.id, course_id=course.id,
                                    classes_attended=row.classes_attended, total_classes=p.total_classes))
        matched += 1
    db.commit()
    return {"course": code, "semester": sem, "matched": matched,
            "unmatched_ids": unmatched, "exceeds_total": flagged}

app.mount("/photos", StaticFiles(directory=PHOTO_DIR), name="photos")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
