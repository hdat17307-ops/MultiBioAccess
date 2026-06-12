"""Tu dong dong bo employees.xlsx -> employees.json -> face_encodings.pkl truoc khi khoi dong he thong."""

import os

from config import EMPLOYEE_DB_PATH, EMPLOYEE_XLSX_PATH, FACES_DIR, FACE_ENCODINGS_PATH
from employees_excel import import_from_excel
from setup_db import build_encodings


def _mtime(path):
    return os.path.getmtime(path) if os.path.exists(path) else 0


def sync_employee_data():
    if os.path.exists(EMPLOYEE_XLSX_PATH) and _mtime(EMPLOYEE_XLSX_PATH) > _mtime(EMPLOYEE_DB_PATH):
        import_from_excel()

    newest_face = max(
        (_mtime(os.path.join(FACES_DIR, f)) for f in os.listdir(FACES_DIR)),
        default=0,
    )
    if (
        _mtime(EMPLOYEE_DB_PATH) > _mtime(FACE_ENCODINGS_PATH)
        or newest_face > _mtime(FACE_ENCODINGS_PATH)
    ):
        build_encodings()
