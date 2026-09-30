# Attendance Hub (phase 1: FastAPI + plain HTML/JS)

    pip install -r requirements.txt
    python -m tools.create_office "Exams Office"     # prints an API key once
    uvicorn app.main:app --reload                    # open http://127.0.0.1:8000

Paste the key into the box at the top of the page. The desktop software uses the same key via
`client/push_attendance.py`. On Render set DATABASE_URL (PostgreSQL) and PHOTO_DIR (persistent disk).
