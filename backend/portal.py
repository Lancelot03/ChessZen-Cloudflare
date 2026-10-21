"""
Student Management Portal - Backend Routes
Handles: Batches CRUD, Students CRUD, Dashboard stats
"""
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, Query
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid

# This module expects `db`, `get_current_user`, `put_object`, `APP_NAME` to be injected
db = None
get_current_user = None
put_object = None
APP_NAME = None


def init_portal(database, auth_fn, upload_fn, app_name):
    global db, get_current_user, put_object, APP_NAME
    db = database
    get_current_user = auth_fn
    put_object = upload_fn
    APP_NAME = app_name


router = APIRouter(prefix="/api/portal")

# ─── Pydantic Models ───

class BatchCreate(BaseModel):
    name: str
    schedule_days: List[str] = []
    schedule_time: str = ""
    max_capacity: int = 20

class BatchUpdate(BaseModel):
    name: Optional[str] = None
    schedule_days: Optional[List[str]] = None
    schedule_time: Optional[str] = None
    max_capacity: Optional[int] = None

class HolidayCreate(BaseModel):
    date: str
    reason: str = ""

class StudentCreate(BaseModel):
    full_name: str
    age_group: str
    email: str = ""
    phone: str = ""
    country_code: str = "+91"
    parent_name: str = ""
    batch_id: str = ""
    joining_date: str = ""
    chess_level: str = "Beginner"
    fee_per_block: float = 0
    status: str = "Active"
    date_of_birth: str = ""

class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    age_group: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    country_code: Optional[str] = None
    parent_name: Optional[str] = None
    batch_id: Optional[str] = None
    joining_date: Optional[str] = None
    chess_level: Optional[str] = None
    fee_per_block: Optional[float] = None
    status: Optional[str] = None
    date_of_birth: Optional[str] = None


# ─── BATCH ROUTES ───

@router.get("/batches")
async def list_batches(request: Request):
    await get_current_user(request)
    batches = await db.batches.find({}, {"_id": 0}).sort("created_at", 1).to_list(100)
    # Add student count per batch
    for b in batches:
        b["student_count"] = await db.students.count_documents({"batch_id": b["id"], "status": "Active"})
    return batches


@router.post("/batches")
async def create_batch(body: BatchCreate, request: Request):
    await get_current_user(request)
    doc = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "schedule_days": body.schedule_days,
        "schedule_time": body.schedule_time,
        "max_capacity": body.max_capacity,
        "holidays": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.batches.insert_one(doc)
    doc.pop("_id", None)
    doc["student_count"] = 0
    return doc


@router.put("/batches/{batch_id}")
async def update_batch(batch_id: str, body: BatchUpdate, request: Request):
    await get_current_user(request)
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "No fields to update")
    result = await db.batches.update_one({"id": batch_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Batch not found")
    return {"status": "updated"}


@router.delete("/batches/{batch_id}")
async def delete_batch(batch_id: str, request: Request):
    await get_current_user(request)
    student_count = await db.students.count_documents({"batch_id": batch_id})
    if student_count > 0:
        raise HTTPException(400, f"Cannot delete batch with {student_count} assigned students. Reassign them first.")
    result = await db.batches.delete_one({"id": batch_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Batch not found")
    return {"status": "deleted"}


@router.post("/batches/{batch_id}/holidays")
async def add_holiday(batch_id: str, body: HolidayCreate, request: Request):
    await get_current_user(request)
    holiday = {"date": body.date, "reason": body.reason}
    result = await db.batches.update_one({"id": batch_id}, {"$push": {"holidays": holiday}})
    if result.matched_count == 0:
        raise HTTPException(404, "Batch not found")
    return {"status": "added"}


@router.delete("/batches/{batch_id}/holidays")
async def remove_holiday(batch_id: str, date: str = Query(...), request: Request = None):
    await get_current_user(request)
    await db.batches.update_one({"id": batch_id}, {"$pull": {"holidays": {"date": date}}})
    return {"status": "removed"}


# ─── STUDENT ROUTES ───

@router.get("/students")
async def list_students(
    request: Request,
    batch_id: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    chess_level: Optional[str] = None,
):
    await get_current_user(request)
    query = {}
    if batch_id:
        query["batch_id"] = batch_id
    if status:
        query["status"] = status
    if chess_level:
        query["chess_level"] = chess_level
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"parent_name": {"$regex": search, "$options": "i"}},
        ]
    students = await db.students.find(query, {"_id": 0}).sort("full_name", 1).to_list(500)
    return students


@router.post("/students")
async def create_student(body: StudentCreate, request: Request):
    await get_current_user(request)
    doc = {
        "id": str(uuid.uuid4()),
        **body.model_dump(),
        "photo_url": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.students.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/students/{student_id}")
async def update_student(student_id: str, body: StudentUpdate, request: Request):
    await get_current_user(request)
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "No fields to update")
    result = await db.students.update_one({"id": student_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Student not found")
    return {"status": "updated"}


@router.post("/students/{student_id}/photo")
async def upload_student_photo(student_id: str, photo: UploadFile = File(...), request: Request = None):
    await get_current_user(request)
    student = await db.students.find_one({"id": student_id})
    if not student:
        raise HTTPException(404, "Student not found")
    
    ext = photo.filename.split(".")[-1] if "." in photo.filename else "jpg"
    path = f"{APP_NAME}/students/{student_id}.{ext}"
    data = await photo.read()
    content_type = photo.content_type or "image/jpeg"
    put_object(path, data, content_type)
    photo_url = f"/api/files/{path}"
    
    await db.students.update_one({"id": student_id}, {"$set": {"photo_url": photo_url}})
    return {"photo_url": photo_url}


@router.get("/students/template/download")
async def download_student_template(request: Request):
    """Download an Excel template for bulk student upload"""
    await get_current_user(request)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from fastapi.responses import Response as FastResponse
    import io

    wb = Workbook()
    ws = wb.active
    ws.title = "Students"

    headers = [
        "Full Name *", "Age Group *", "Email", "Phone", "Country Code",
        "Parent/Guardian Name", "Batch Name", "Joining Date (YYYY-MM-DD)",
        "Chess Level", "Fee Per 8-Session Block", "Status", "Date of Birth (YYYY-MM-DD)"
    ]

    header_fill = PatternFill(start_color="F59E0B", end_color="F59E0B", fill_type="solid")
    header_font = Font(bold=True, color="000000", size=11)
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    # Column widths
    widths = [25, 12, 25, 15, 12, 25, 15, 22, 18, 20, 10, 22]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    # Sample row
    sample = ["Arjun Kumar", "10-15", "arjun@email.com", "9876543210", "+91",
              "Rajesh Kumar", "Online 1", "2026-01-15", "Beginner", "2000", "Active", "2014-06-15"]
    for col, val in enumerate(sample, 1):
        cell = ws.cell(row=2, column=col, value=val)
        cell.font = Font(color="888888", italic=True)
        cell.border = thin_border

    # Add data validations
    age_dv = DataValidation(type="list", formula1='"Below 5,5-10,10-15,15-20,20+"', allow_blank=True)
    age_dv.error = "Pick a valid age group"
    ws.add_data_validation(age_dv)
    age_dv.add("B2:B1000")

    level_dv = DataValidation(type="list", formula1='"Beginner,Intermediate,Advanced,Tournament Player"', allow_blank=True)
    ws.add_data_validation(level_dv)
    level_dv.add("I2:I1000")

    status_dv = DataValidation(type="list", formula1='"Active,Inactive"', allow_blank=True)
    ws.add_data_validation(status_dv)
    status_dv.add("K2:K1000")

    # Instructions sheet
    instr = wb.create_sheet("Instructions")
    instructions = [
        ("Column", "Description", "Required"),
        ("Full Name", "Student's full name", "Yes"),
        ("Age Group", "Below 5 / 5-10 / 10-15 / 15-20 / 20+", "Yes"),
        ("Email", "Student or parent email", "No"),
        ("Phone", "Phone number (digits only)", "No"),
        ("Country Code", "+91, +1, +44, etc.", "No (defaults to +91)"),
        ("Parent/Guardian Name", "Parent or guardian full name", "No"),
        ("Batch Name", "Must match an existing batch name exactly", "No"),
        ("Joining Date", "Format: YYYY-MM-DD", "No"),
        ("Chess Level", "Beginner / Intermediate / Advanced / Tournament Player", "No (defaults to Beginner)"),
        ("Fee Per Block", "Fee amount for 8 sessions", "No (defaults to 0)"),
        ("Status", "Active / Inactive", "No (defaults to Active)"),
        ("Date of Birth", "Format: YYYY-MM-DD", "No"),
    ]
    for row_idx, (c1, c2, c3) in enumerate(instructions, 1):
        instr.cell(row=row_idx, column=1, value=c1).font = Font(bold=row_idx == 1)
        instr.cell(row=row_idx, column=2, value=c2).font = Font(bold=row_idx == 1)
        instr.cell(row=row_idx, column=3, value=c3).font = Font(bold=row_idx == 1)
    instr.column_dimensions["A"].width = 22
    instr.column_dimensions["B"].width = 50
    instr.column_dimensions["C"].width = 20

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return FastResponse(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ChessZen_Student_Template.xlsx"}
    )


VALID_AGE_GROUPS = {"below 5", "5-10", "10-15", "15-20", "20+"}
VALID_CHESS_LEVELS = {"beginner", "intermediate", "advanced", "tournament player"}
VALID_STATUSES = {"active", "inactive"}


def parse_student_row(row, idx, batch_map):
    """Parse and validate a single row from the bulk upload spreadsheet.
    Returns (doc, None) on success or (None, error_string) on failure."""
    if not row or not row[0]:
        return None, None  # skip empty rows

    full_name = str(row[0]).strip()
    if not full_name:
        return None, f"Row {idx}: Name is empty"

    age_group = str(row[1] or "5-10").strip()
    if age_group.lower() not in VALID_AGE_GROUPS:
        return None, f"Row {idx}: Invalid age group '{age_group}'"

    email = str(row[2] or "").strip()
    phone = str(row[3] or "").strip().replace(" ", "").replace("-", "")
    country_code = str(row[4] or "+91").strip()
    if not country_code.startswith("+"):
        country_code = "+" + country_code

    parent_name = str(row[5] or "").strip()
    batch_name = str(row[6] or "").strip()
    batch_id = batch_map.get(batch_name.lower(), "") if batch_name else ""
    joining_date = str(row[7] or "").strip()

    chess_level = str(row[8] or "Beginner").strip()
    if chess_level.lower() not in VALID_CHESS_LEVELS:
        chess_level = "Beginner"

    try:
        fee = float(row[9] or 0)
    except (ValueError, TypeError):
        fee = 0

    status = str(row[10] or "Active").strip()
    if status.lower() not in VALID_STATUSES:
        status = "Active"

    dob = str(row[11] or "").strip()

    doc = {
        "id": str(uuid.uuid4()),
        "full_name": full_name,
        "age_group": age_group,
        "email": email,
        "phone": phone,
        "country_code": country_code,
        "parent_name": parent_name,
        "batch_id": batch_id,
        "joining_date": joining_date,
        "chess_level": chess_level,
        "fee_per_block": fee,
        "status": status,
        "date_of_birth": dob,
        "photo_url": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return doc, None


@router.post("/students/bulk-upload")
async def bulk_upload_students(file: UploadFile = File(...), request: Request = None):
    """Upload an Excel file to bulk-add students"""
    await get_current_user(request)
    from openpyxl import load_workbook
    import io

    data = await file.read()
    try:
        wb = load_workbook(io.BytesIO(data))
    except Exception:
        raise HTTPException(400, "Invalid Excel file. Please use the provided template.")

    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))

    batches = await db.batches.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)
    batch_map = {b["name"].lower().strip(): b["id"] for b in batches}

    created = []
    errors = []

    for idx, row in enumerate(rows, 2):
        doc, error = parse_student_row(row, idx, batch_map)
        if error:
            errors.append(error)
            continue
        if doc is None:
            continue
        await db.students.insert_one(doc)
        doc.pop("_id", None)
        created.append(doc["full_name"])

    return {
        "created_count": len(created),
        "created_names": created,
        "error_count": len(errors),
        "errors": errors,
    }


@router.delete("/students/{student_id}")
async def delete_student(student_id: str, request: Request):
    await get_current_user(request)
    result = await db.students.delete_one({"id": student_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Student not found")
    return {"status": "deleted"}


@router.get("/students/{student_id}")
async def get_student(student_id: str, request: Request):
    await get_current_user(request)
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")
    return student


# ─── DASHBOARD STATS ───

@router.get("/dashboard")
async def dashboard_stats(request: Request):
    await get_current_user(request)
    total_students = await db.students.count_documents({})
    active_students = await db.students.count_documents({"status": "Active"})
    inactive_students = total_students - active_students
    total_batches = await db.batches.count_documents({})

    # Batch stats
    batches = await db.batches.find({}, {"_id": 0, "id": 1, "name": 1, "max_capacity": 1}).to_list(50)
    batch_stats = []
    for b in batches:
        count = await db.students.count_documents({"batch_id": b["id"], "status": "Active"})
        batch_stats.append({
            "name": b["name"],
            "students": count,
            "capacity": b.get("max_capacity", 20),
        })

    # Level distribution
    levels = ["Beginner", "Intermediate", "Advanced", "Tournament Player"]
    level_dist = []
    for lvl in levels:
        c = await db.students.count_documents({"chess_level": lvl, "status": "Active"})
        if c > 0:
            level_dist.append({"level": lvl, "count": c})

    # Age distribution
    age_groups = ["Below 5", "5-10", "10-15", "15-20", "20+"]
    age_dist = []
    for ag in age_groups:
        c = await db.students.count_documents({"age_group": ag, "status": "Active"})
        if c > 0:
            age_dist.append({"age_group": ag, "count": c})

    return {
        "total_students": total_students,
        "active_students": active_students,
        "inactive_students": inactive_students,
        "total_batches": total_batches,
        "batch_stats": batch_stats,
        "level_distribution": level_dist,
        "age_distribution": age_dist,
    }


# ═══════════════════════════════════════════════════════
# MODULE 2 — ATTENDANCE MANAGEMENT
# ═══════════════════════════════════════════════════════

class AttendanceMark(BaseModel):
    student_id: str
    status: str  # Present / Absent / Late

class BulkAttendance(BaseModel):
    date: str
    batch_id: str
    records: List[AttendanceMark]


@router.post("/attendance")
async def save_attendance(body: BulkAttendance, request: Request):
    await get_current_user(request)
    now = datetime.now(timezone.utc).isoformat()
    for rec in body.records:
        await db.attendance.update_one(
            {"student_id": rec.student_id, "date": body.date},
            {"$set": {
                "student_id": rec.student_id,
                "date": body.date,
                "batch_id": body.batch_id,
                "status": rec.status,
                "updated_at": now,
            }},
            upsert=True,
        )
    return {"status": "saved", "count": len(body.records)}


@router.get("/attendance")
async def get_attendance(request: Request, date: str = Query(...), batch_id: Optional[str] = None):
    await get_current_user(request)
    query = {"date": date}
    if batch_id:
        query["batch_id"] = batch_id
    records = await db.attendance.find(query, {"_id": 0}).to_list(500)
    return records


async def count_batch_sessions(batch_id: str, since_date: str, until_date: str = None):
    """Count how many class sessions a batch had between since_date and until_date,
    based on schedule_days minus holidays."""
    from datetime import timedelta
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch or not batch.get("schedule_days"):
        return 0

    day_map = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    schedule_days = {day_map[d] for d in batch["schedule_days"] if d in day_map}
    holidays = {h["date"] for h in batch.get("holidays", [])}

    try:
        start = datetime.strptime(since_date, "%Y-%m-%d")
    except ValueError:
        return 0
    if until_date:
        try:
            end = datetime.strptime(until_date, "%Y-%m-%d")
        except ValueError:
            end = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        end = datetime.now(timezone.utc).replace(tzinfo=None)

    count = 0
    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        if current.weekday() in schedule_days and date_str not in holidays:
            count += 1
        current += timedelta(days=1)
    return count


async def get_batch_class_dates(batch_id: str):
    """Get all dates where attendance was recorded for this batch (i.e., class happened)."""
    pipeline = [
        {"$match": {"batch_id": batch_id}},
        {"$group": {"_id": "$date"}},
        {"$sort": {"_id": 1}},
    ]
    results = await db.attendance.aggregate(pipeline).to_list(1000)
    return [r["_id"] for r in results]


async def compute_student_attendance(student_id: str, student: dict = None):
    """Compute attendance where: if class happened for the batch (any student marked),
    and this student wasn't marked present/late, they count as absent."""
    if not student:
        student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        return {"present": 0, "late": 0, "absent": 0, "total": 0, "attended": 0, "percentage": 0, "records": [], "monthly": []}

    batch_id = student.get("batch_id", "")
    joining_date = student.get("joining_date", "")

    # Get all dates when this batch had class
    class_dates = await get_batch_class_dates(batch_id) if batch_id else []

    # Filter to dates on or after joining
    if joining_date:
        class_dates = [d for d in class_dates if d >= joining_date]

    # Get this student's explicit attendance records
    records = await db.attendance.find({"student_id": student_id}, {"_id": 0}).sort("date", -1).to_list(1000)
    marked_map = {r["date"]: r["status"] for r in records}

    present = 0
    late = 0
    absent = 0
    all_records = []
    monthly = {}

    for d in class_dates:
        status = marked_map.get(d, "Absent")  # Unmarked = Absent
        if status == "Present":
            present += 1
        elif status == "Late":
            late += 1
        else:
            absent += 1
        all_records.append({"date": d, "status": status, "batch_id": batch_id})

        month = d[:7]
        if month not in monthly:
            monthly[month] = {"month": month, "present": 0, "absent": 0, "late": 0}
        monthly[month][status.lower()] = monthly[month].get(status.lower(), 0) + 1

    total = len(class_dates)
    attended = present + late
    pct = round((attended / total) * 100, 1) if total > 0 else 0
    monthly_list = sorted(monthly.values(), key=lambda x: x["month"])

    return {
        "present": present,
        "late": late,
        "absent": absent,
        "total": total,
        "attended": attended,
        "percentage": pct,
        "records": sorted(all_records, key=lambda x: x["date"], reverse=True),
        "monthly": monthly_list,
    }


@router.get("/attendance/student/{student_id}")
async def get_student_attendance(student_id: str, request: Request):
    await get_current_user(request)
    data = await compute_student_attendance(student_id)
    return {
        "records": data["records"],
        "total_sessions": data["total"],
        "total_marked": data["present"] + data["late"] + data["absent"],
        "present": data["present"],
        "late": data["late"],
        "absent": data["absent"],
        "attended": data["attended"],
        "percentage": data["percentage"],
        "monthly": data["monthly"],
    }


@router.get("/attendance/batch-calendar/{batch_id}")
async def batch_calendar_view(batch_id: str, request: Request, month: Optional[str] = None):
    """Calendar view: for a batch+month, show each class date with all students' status."""
    await get_current_user(request)

    if not month:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    # Get all active students in this batch
    students = await db.students.find(
        {"batch_id": batch_id, "status": "Active"},
        {"_id": 0, "id": 1, "full_name": 1, "photo_url": 1}
    ).sort("full_name", 1).to_list(200)
    student_ids = {s["id"] for s in students}

    # Get all attendance records for this batch in this month
    date_prefix = month  # e.g. "2026-08"
    records = await db.attendance.find(
        {"batch_id": batch_id, "date": {"$regex": f"^{date_prefix}"}},
        {"_id": 0}
    ).to_list(5000)

    # Group by date
    date_map = {}
    for r in records:
        d = r["date"]
        if d not in date_map:
            date_map[d] = {}
        date_map[d][r["student_id"]] = r["status"]

    # Build calendar data
    calendar_days = []
    for d in sorted(date_map.keys()):
        day_data = {"date": d, "students": []}
        marked = date_map[d]
        for s in students:
            status = marked.get(s["id"], "Absent")
            day_data["students"].append({
                "id": s["id"],
                "name": s["full_name"],
                "photo_url": s.get("photo_url"),
                "status": status,
            })
        present_count = sum(1 for st in day_data["students"] if st["status"] in ("Present", "Late"))
        day_data["present_count"] = present_count
        day_data["total_count"] = len(students)
        calendar_days.append(day_data)

    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0, "name": 1})
    return {
        "batch_name": batch["name"] if batch else "",
        "month": month,
        "students": students,
        "days": calendar_days,
    }


# ═══════════════════════════════════════════════════════
# MODULE 3 — FEE TRACKING & PAYMENTS
# ═══════════════════════════════════════════════════════

class PaymentCreate(BaseModel):
    student_id: str
    amount: float
    date: str
    method: str
    sessions_covered: int = 8
    notes: str = ""

class PaymentUpdate(BaseModel):
    amount: Optional[float] = None
    date: Optional[str] = None
    method: Optional[str] = None
    sessions_covered: Optional[int] = None
    notes: Optional[str] = None
    student_id: Optional[str] = None


@router.post("/payments")
async def record_payment(body: PaymentCreate, request: Request):
    await get_current_user(request)
    doc = {
        "id": str(uuid.uuid4()),
        **body.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payments.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/payments/{payment_id}")
async def update_payment(payment_id: str, body: PaymentUpdate, request: Request):
    await get_current_user(request)
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "No fields to update")
    result = await db.payments.update_one({"id": payment_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Payment not found")
    return {"status": "updated"}


@router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str, request: Request):
    await get_current_user(request)
    result = await db.payments.delete_one({"id": payment_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Payment not found")
    return {"status": "deleted"}


@router.get("/payments/student/{student_id}")
async def get_student_payments(student_id: str, request: Request):
    await get_current_user(request)
    payments = await db.payments.find({"student_id": student_id}, {"_id": 0}).sort("date", -1).to_list(200)

    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    fee_per_block = student.get("fee_per_block", 0) if student else 0

    total_paid = sum(p["amount"] for p in payments)
    sessions_paid = sum(p.get("sessions_covered", 8) for p in payments)

    # Count attended sessions
    attended = await db.attendance.count_documents({"student_id": student_id, "status": {"$in": ["Present", "Late"]}})

    sessions_pending = max(0, attended - sessions_paid)
    pending_amount = 0
    if fee_per_block > 0 and sessions_pending > 0:
        pending_amount = round((sessions_pending / 8) * fee_per_block, 2)

    return {
        "payments": payments,
        "total_paid": total_paid,
        "sessions_paid": sessions_paid,
        "sessions_attended": attended,
        "sessions_pending": sessions_pending,
        "pending_amount": pending_amount,
        "fee_per_block": fee_per_block,
    }


async def compute_revenue(month_start: str):
    """Compute monthly and total revenue from payments."""
    rev = await db.payments.aggregate([
        {"$match": {"date": {"$gte": month_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]).to_list(1)
    monthly = rev[0]["total"] if rev else 0

    all_rev = await db.payments.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]).to_list(1)
    total = all_rev[0]["total"] if all_rev else 0
    return monthly, total


async def compute_student_pending(student_id: str, fee_per_block: float):
    """Compute pending sessions and amount for a student."""
    attended = await db.attendance.count_documents(
        {"student_id": student_id, "status": {"$in": ["Present", "Late"]}}
    )
    payments = await db.payments.find(
        {"student_id": student_id}, {"sessions_covered": 1}
    ).to_list(100)
    paid_sessions = sum(p.get("sessions_covered", 8) for p in payments)
    pending = max(0, attended - paid_sessions)
    amount = round((pending / 8) * fee_per_block, 2) if pending > 0 else 0
    return pending, amount


@router.get("/fees/summary")
async def fees_summary(request: Request):
    await get_current_user(request)
    now = datetime.now(timezone.utc)
    month_start = now.strftime("%Y-%m-01")

    monthly_revenue, total_revenue = await compute_revenue(month_start)

    students = await db.students.find(
        {"status": "Active"}, {"_id": 0, "id": 1, "fee_per_block": 1, "full_name": 1}
    ).to_list(500)

    total_pending = 0
    students_with_dues = []
    for s in students:
        fee = s.get("fee_per_block", 0)
        if fee <= 0:
            continue
        pending, amount = await compute_student_pending(s["id"], fee)
        if pending > 0:
            total_pending += amount
            students_with_dues.append({
                "id": s["id"],
                "name": s.get("full_name", ""),
                "pending_sessions": pending,
                "pending_amount": amount,
            })

    return {
        "monthly_revenue": monthly_revenue,
        "total_revenue": total_revenue,
        "total_pending": total_pending,
        "students_with_dues": students_with_dues[:20],
    }


@router.get("/fees/reminder/{student_id}")
async def generate_fee_reminder(student_id: str, request: Request):
    await get_current_user(request)
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    fee = student.get("fee_per_block", 0)
    attended_records = await db.attendance.find(
        {"student_id": student_id, "status": {"$in": ["Present", "Late"]}},
        {"_id": 0, "date": 1}
    ).sort("date", 1).to_list(500)
    attended_dates = [r["date"] for r in attended_records]

    payments = await db.payments.find({"student_id": student_id}, {"_id": 0}).to_list(100)
    paid_sessions = sum(p.get("sessions_covered", 8) for p in payments)
    pending = max(0, len(attended_dates) - paid_sessions)

    message = f"""Dear {student['full_name']},

This is a friendly reminder regarding your pending chess session fees.

Sessions attended: {', '.join(attended_dates[-10:])}{'...' if len(attended_dates) > 10 else ''}
Total sessions attended: {len(attended_dates)}
Sessions paid: {paid_sessions}
Pending sessions: {pending}

Fee applicable: ₹{fee} for 8 sessions

Please make the payment at your earliest convenience:
📱 PhonePe / Google Pay No: 8090424776
👤 Name: Ramya Singh
🔗 UPI ID: 8090424776@ybl

Thank you,
ChessZen Classes Team"""

    phone = student.get("phone", "")
    country_code = student.get("country_code", "+91").replace("+", "")
    whatsapp_url = f"https://wa.me/{country_code}{phone}?text={message.replace(chr(10), '%0A').replace(' ', '%20')}" if phone else ""

    return {
        "message": message,
        "whatsapp_url": whatsapp_url,
        "student_name": student["full_name"],
        "email": student.get("email", ""),
        "pending_sessions": pending,
        "pending_amount": round((pending / 8) * fee, 2) if fee > 0 else 0,
    }


# ═══════════════════════════════════════════════════════
# MODULE 4 — PERFORMANCE TRACKER
# ═══════════════════════════════════════════════════════

class TestEntryCreate(BaseModel):
    student_id: str
    test_name: str
    test_date: str
    score: float  # 0-100
    remarks: str = ""

class TestEntryUpdate(BaseModel):
    test_name: Optional[str] = None
    test_date: Optional[str] = None
    score: Optional[float] = None
    remarks: Optional[str] = None


@router.post("/tests")
async def add_test_entry(body: TestEntryCreate, request: Request):
    await get_current_user(request)
    doc = {
        "id": str(uuid.uuid4()),
        **body.model_dump(),
        "attachments": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tests.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/tests/student/{student_id}")
async def get_student_tests(student_id: str, request: Request):
    await get_current_user(request)
    tests = await db.tests.find({"student_id": student_id}, {"_id": 0}).sort("test_date", -1).to_list(200)

    scores = [t["score"] for t in tests]
    stats = {}
    if scores:
        stats = {
            "highest": max(scores),
            "lowest": min(scores),
            "average": round(sum(scores) / len(scores), 1),
            "latest": scores[0],
            "total_tests": len(scores),
        }

    return {"tests": tests, "stats": stats}


@router.put("/tests/{test_id}")
async def update_test_entry(test_id: str, body: TestEntryUpdate, request: Request):
    await get_current_user(request)
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "No fields to update")
    await db.tests.update_one({"id": test_id}, {"$set": update})
    return {"status": "updated"}


@router.delete("/tests/{test_id}")
async def delete_test_entry(test_id: str, request: Request):
    await get_current_user(request)
    await db.tests.delete_one({"id": test_id})
    return {"status": "deleted"}


@router.post("/tests/{test_id}/attachment")
async def upload_test_attachment(test_id: str, file: UploadFile = File(...), request: Request = None):
    await get_current_user(request)
    test = await db.tests.find_one({"id": test_id})
    if not test:
        raise HTTPException(404, "Test not found")
    if len(test.get("attachments", [])) >= 3:
        raise HTTPException(400, "Maximum 3 attachments per test")

    ext = file.filename.split(".")[-1] if "." in file.filename else "pdf"
    file_id = str(uuid.uuid4())[:8]
    path = f"{APP_NAME}/tests/{test_id}/{file_id}.{ext}"
    data = await file.read()
    content_type = file.content_type or "application/pdf"
    put_object(path, data, content_type)
    attachment = {"name": file.filename, "url": f"/api/files/{path}"}

    await db.tests.update_one({"id": test_id}, {"$push": {"attachments": attachment}})
    return attachment


@router.get("/tests/leaderboard")
async def test_leaderboard(request: Request, test_name: str = Query(...), batch_id: Optional[str] = None):
    await get_current_user(request)
    match = {"test_name": test_name}
    entries = await db.tests.find(match, {"_id": 0}).sort("score", -1).to_list(500)

    # Enrich with student info and filter by batch
    results = []
    for e in entries:
        student = await db.students.find_one({"id": e["student_id"]}, {"_id": 0, "full_name": 1, "batch_id": 1, "photo_url": 1})
        if not student:
            continue
        if batch_id and student.get("batch_id") != batch_id:
            continue
        results.append({
            "student_id": e["student_id"],
            "name": student["full_name"],
            "score": e["score"],
            "batch_id": student.get("batch_id", ""),
            "photo_url": student.get("photo_url"),
        })

    # Add rank
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results


# ═══════════════════════════════════════════════════════
# MODULE 7 — COMMUNICATIONS
# ═══════════════════════════════════════════════════════

class BroadcastMessage(BaseModel):
    batch_id: str
    message: str
    subject: str = ""


@router.post("/communications/broadcast")
async def broadcast_to_batch(body: BroadcastMessage, request: Request):
    await get_current_user(request)
    batch = await db.batches.find_one({"id": body.batch_id}, {"_id": 0, "name": 1})
    if not batch:
        raise HTTPException(404, "Batch not found")

    students = await db.students.find(
        {"batch_id": body.batch_id, "status": "Active"},
        {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "country_code": 1, "email": 1}
    ).to_list(100)

    links = []
    for s in students:
        phone = s.get("phone", "")
        cc = s.get("country_code", "+91").replace("+", "")
        wa_url = f"https://wa.me/{cc}{phone}?text={body.message.replace(chr(10), '%0A').replace(' ', '%20')}" if phone else ""
        links.append({
            "student_id": s["id"],
            "name": s["full_name"],
            "phone": f"{s.get('country_code', '+91')} {phone}",
            "email": s.get("email", ""),
            "whatsapp_url": wa_url,
        })

    # Log broadcast
    await db.communications.insert_one({
        "id": str(uuid.uuid4()),
        "type": "broadcast",
        "batch_id": body.batch_id,
        "batch_name": batch["name"],
        "message": body.message,
        "subject": body.subject,
        "recipients": len(links),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"batch_name": batch["name"], "recipients": links, "count": len(links)}


@router.get("/communications/history")
async def communication_history(request: Request):
    await get_current_user(request)
    records = await db.communications.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return records


@router.get("/communications/birthdays")
async def upcoming_birthdays(request: Request):
    await get_current_user(request)
    students = await db.students.find(
        {"status": "Active", "date_of_birth": {"$ne": ""}},
        {"_id": 0, "id": 1, "full_name": 1, "date_of_birth": 1, "phone": 1, "country_code": 1, "batch_id": 1}
    ).to_list(500)

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    upcoming = []
    for s in students:
        dob = s.get("date_of_birth", "")
        if not dob or len(dob) < 10:
            continue
        try:
            birth = datetime.strptime(dob, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            this_year = birth.replace(year=now.year)
            if this_year < now - timedelta(days=1):
                this_year = this_year.replace(year=now.year + 1)
            days_until = (this_year - now).days
            if 0 <= days_until <= 7:
                age = now.year - birth.year
                upcoming.append({
                    "student_id": s["id"],
                    "name": s["full_name"],
                    "date_of_birth": dob,
                    "days_until": days_until,
                    "turning_age": age,
                    "phone": s.get("phone", ""),
                    "country_code": s.get("country_code", "+91"),
                    "batch_id": s.get("batch_id", ""),
                })
        except ValueError:
            continue

    upcoming.sort(key=lambda x: x["days_until"])
    return upcoming


@router.get("/students/{student_id}/report")
async def generate_student_report(student_id: str, request: Request):
    """Generate a summary report for a student (attendance + tests)"""
    await get_current_user(request)
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    # Attendance
    att_records = await db.attendance.find({"student_id": student_id}, {"_id": 0}).to_list(500)
    total_att = len(att_records)
    present = sum(1 for r in att_records if r["status"] in ("Present", "Late"))
    att_pct = round((present / total_att) * 100, 1) if total_att > 0 else 0

    # Tests
    tests = await db.tests.find({"student_id": student_id}, {"_id": 0}).sort("test_date", 1).to_list(200)
    scores = [t["score"] for t in tests]
    test_stats = {}
    if scores:
        test_stats = {
            "highest": max(scores),
            "average": round(sum(scores) / len(scores), 1),
            "latest": scores[-1],
            "total_tests": len(scores),
        }

    batch_name = ""
    if student.get("batch_id"):
        batch = await db.batches.find_one({"id": student["batch_id"]}, {"_id": 0, "name": 1})
        batch_name = batch["name"] if batch else ""

    return {
        "student": student,
        "batch_name": batch_name,
        "attendance": {"total": total_att, "present": present, "percentage": att_pct},
        "tests": tests,
        "test_stats": test_stats,
    }


# ═══════════════════════════════════════════════════════
# MONTHLY ATTENDANCE GRAPH DATA
# ═══════════════════════════════════════════════════════

async def monthly_batch_sessions(batch_id: str, since_date: str):
    """Get month-by-month count of batch sessions since joining."""
    from datetime import timedelta
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch or not batch.get("schedule_days"):
        return {}
    day_map = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    schedule_days = {day_map[d] for d in batch["schedule_days"] if d in day_map}
    holidays = {h["date"] for h in batch.get("holidays", [])}
    try:
        start = datetime.strptime(since_date, "%Y-%m-%d")
    except ValueError:
        return {}
    end = datetime.now(timezone.utc).replace(tzinfo=None)
    months = {}
    current = start
    while current <= end:
        key = current.strftime("%Y-%m")
        if key not in months:
            months[key] = 0
        if current.weekday() in schedule_days and current.strftime("%Y-%m-%d") not in holidays:
            months[key] += 1
        current += timedelta(days=1)
    return months


@router.get("/attendance/student/{student_id}/monthly-graph")
async def student_monthly_attendance_graph(student_id: str, request: Request):
    """Month-wise: classes conducted vs attended + percentage (using actual class dates)."""
    await get_current_user(request)
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    att = await compute_student_attendance(student_id, student)
    batch_id = student.get("batch_id", "")

    # Build monthly: conducted = present+absent+late, attended = present+late
    graph = []
    total_conducted = 0
    total_attended = 0
    for m_data in att["monthly"]:
        c = m_data["present"] + m_data["absent"] + m_data["late"]
        a = m_data["present"] + m_data["late"]
        total_conducted += c
        total_attended += a
        pct = round((a / c) * 100, 1) if c > 0 else 0
        label = datetime.strptime(m_data["month"] + "-01", "%Y-%m-%d").strftime("%b %Y")
        graph.append({"month": m_data["month"], "label": label, "conducted": c, "attended": a, "percentage": pct})

    overall_pct = round((total_attended / total_conducted) * 100, 1) if total_conducted > 0 else 0

    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0, "name": 1}) if batch_id else None
    return {
        "student_name": student["full_name"],
        "batch_name": batch["name"] if batch else "",
        "joining_date": student.get("joining_date", ""),
        "monthly": graph,
        "total_conducted": total_conducted,
        "total_attended": total_attended,
        "overall_percentage": overall_pct,
    }


# ═══════════════════════════════════════════════════════
# FEE REMINDER CARD DATA
# ═══════════════════════════════════════════════════════

@router.get("/fees/reminder-card/{student_id}")
async def fee_reminder_card(student_id: str, request: Request):
    """Rich data for fee reminder card including attendance graph."""
    await get_current_user(request)
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    # Attendance summary — use unified logic
    joining = student.get("joining_date", "")
    batch_id = student.get("batch_id", "")
    att = await compute_student_attendance(student_id, student)
    attended = att["attended"]
    att_pct = att["percentage"]
    total_sessions = att["total"]
    attended_dates = [r["date"] for r in att["records"] if r["status"] in ("Present", "Late")]

    # Monthly graph (last 3 months) using actual class dates
    attended_set = set(attended_dates)
    class_dates = await get_batch_class_dates(batch_id) if batch_id else []
    now = datetime.now(timezone.utc)
    recent_months = []
    for i in range(3):
        d = now.replace(day=1) - timedelta(days=30 * i)
        m = d.strftime("%Y-%m")
        label = d.strftime("%b")
        month_classes = [cd for cd in class_dates if cd.startswith(m)]
        month_attended = len([cd for cd in month_classes if cd in attended_set])
        recent_months.append({"month": label, "conducted": len(month_classes), "attended": month_attended})
    recent_months.reverse()

    # Fee info
    fee = student.get("fee_per_block", 0)
    payments = await db.payments.find({"student_id": student_id}, {"_id": 0}).to_list(100)
    paid_sessions = sum(p.get("sessions_covered", 8) for p in payments)
    pending_sessions = max(0, attended - paid_sessions)
    pending_amount = round((pending_sessions / 8) * fee, 2) if fee > 0 and pending_sessions > 0 else 0

    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0, "name": 1}) if batch_id else None

    return {
        "student": {
            "name": student["full_name"],
            "phone": student.get("phone", ""),
            "country_code": student.get("country_code", "+91"),
            "email": student.get("email", ""),
            "batch": batch["name"] if batch else "",
            "chess_level": student.get("chess_level", ""),
        },
        "attendance": {
            "total_sessions": total_sessions,
            "attended": attended,
            "percentage": att_pct,
        },
        "recent_months": recent_months,
        "fees": {
            "fee_per_block": fee,
            "sessions_paid": paid_sessions,
            "pending_sessions": pending_sessions,
            "pending_amount": pending_amount,
        },
        "attended_dates": attended_dates[-15:],
    }


# ═══════════════════════════════════════════════════════
# ENHANCED REPORT CARD
# ═══════════════════════════════════════════════════════

@router.get("/students/{student_id}/report-card")
async def student_report_card(student_id: str, request: Request):
    """Full auto-generated performance report card for parents."""
    await get_current_user(request)
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    batch_id = student.get("batch_id", "")
    joining = student.get("joining_date", "")
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0, "name": 1, "schedule_days": 1, "schedule_time": 1}) if batch_id else None

    # Attendance — use unified logic (unmarked = absent)
    att = await compute_student_attendance(student_id, student)

    # Monthly breakdown from computed data
    monthly_att = []
    for m_data in att["monthly"]:
        month_key = m_data["month"]
        label = datetime.strptime(month_key + "-01", "%Y-%m-%d").strftime("%b %Y")
        c = m_data["present"] + m_data["absent"] + m_data["late"]
        a = m_data["present"] + m_data["late"]
        monthly_att.append({"label": label, "conducted": c, "attended": a, "pct": round((a / c) * 100) if c > 0 else 0})

    # Tests
    tests = await db.tests.find({"student_id": student_id}, {"_id": 0}).sort("test_date", 1).to_list(200)
    scores = [t["score"] for t in tests]
    test_stats = {}
    if scores:
        test_stats = {"highest": max(scores), "lowest": min(scores), "average": round(sum(scores) / len(scores), 1), "latest": scores[-1], "total": len(scores)}
    test_entries = [{"name": t["test_name"], "date": t["test_date"], "score": t["score"], "remarks": t.get("remarks", "")} for t in tests]

    # Fees
    fee = student.get("fee_per_block", 0)
    payments = await db.payments.find({"student_id": student_id}, {"_id": 0}).to_list(100)
    total_paid = sum(p["amount"] for p in payments)
    paid_sessions = sum(p.get("sessions_covered", 8) for p in payments)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "student": {
            "name": student["full_name"],
            "age_group": student.get("age_group", ""),
            "chess_level": student.get("chess_level", ""),
            "joining_date": joining,
            "parent_name": student.get("parent_name", ""),
        },
        "batch": {
            "name": batch["name"] if batch else "",
            "schedule": f"{', '.join(batch.get('schedule_days', []))} | {batch.get('schedule_time', '')}" if batch else "",
        },
        "attendance": {
            "total_sessions": att["total"],
            "present": att["present"],
            "absent": att["absent"],
            "percentage": att["percentage"],
            "monthly": monthly_att,
        },
        "tests": {"entries": test_entries, "stats": test_stats},
        "fees": {"total_paid": total_paid, "sessions_paid": paid_sessions, "fee_per_block": fee},
    }


# ═══════════════════════════════════════════════════════
# TOURNAMENT / TEST SCHEDULING
# ═══════════════════════════════════════════════════════

class TournamentCreate(BaseModel):
    name: str
    date: str
    batch_ids: List[str] = []
    description: str = ""
    location: str = ""

class TournamentUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[str] = None
    batch_ids: Optional[List[str]] = None
    description: Optional[str] = None
    location: Optional[str] = None


@router.get("/tournaments")
async def list_tournaments(request: Request):
    await get_current_user(request)
    tournaments = await db.tournaments.find({}, {"_id": 0}).sort("date", -1).to_list(100)
    return tournaments


@router.post("/tournaments")
async def create_tournament(body: TournamentCreate, request: Request):
    await get_current_user(request)
    doc = {
        "id": str(uuid.uuid4()),
        **body.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tournaments.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/tournaments/{tournament_id}")
async def update_tournament(tournament_id: str, body: TournamentUpdate, request: Request):
    await get_current_user(request)
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "No fields to update")
    await db.tournaments.update_one({"id": tournament_id}, {"$set": update})
    return {"status": "updated"}


@router.delete("/tournaments/{tournament_id}")
async def delete_tournament(tournament_id: str, request: Request):
    await get_current_user(request)
    await db.tournaments.delete_one({"id": tournament_id})
    # Also delete associated test entries
    await db.tests.delete_many({"tournament_id": tournament_id})
    return {"status": "deleted"}


@router.post("/tournaments/{tournament_id}/scores")
async def record_tournament_scores(tournament_id: str, request: Request):
    """Bulk record scores for a tournament. Body: {scores: [{student_id, score, remarks}]}"""
    await get_current_user(request)
    body = await request.json()
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not tournament:
        raise HTTPException(404, "Tournament not found")

    created = 0
    for entry in body.get("scores", []):
        sid = entry.get("student_id")
        score = entry.get("score", 0)
        remarks = entry.get("remarks", "")
        if not sid:
            continue
        # Upsert: update if exists, create if not
        existing = await db.tests.find_one({"tournament_id": tournament_id, "student_id": sid})
        if existing:
            await db.tests.update_one(
                {"tournament_id": tournament_id, "student_id": sid},
                {"$set": {"score": score, "remarks": remarks}}
            )
        else:
            await db.tests.insert_one({
                "id": str(uuid.uuid4()),
                "student_id": sid,
                "test_name": tournament["name"],
                "test_date": tournament["date"],
                "score": score,
                "remarks": remarks,
                "tournament_id": tournament_id,
                "attachments": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        created += 1
    return {"status": "saved", "count": created}


@router.get("/tournaments/{tournament_id}/scores")
async def get_tournament_scores(tournament_id: str, request: Request):
    await get_current_user(request)
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not tournament:
        raise HTTPException(404, "Tournament not found")

    entries = await db.tests.find({"tournament_id": tournament_id}, {"_id": 0}).sort("score", -1).to_list(500)
    results = []
    for e in entries:
        student = await db.students.find_one({"id": e["student_id"]}, {"_id": 0, "full_name": 1, "batch_id": 1})
        results.append({
            "student_id": e["student_id"],
            "name": student["full_name"] if student else "Unknown",
            "score": e["score"],
            "remarks": e.get("remarks", ""),
        })

    return {"tournament": tournament, "scores": results}
