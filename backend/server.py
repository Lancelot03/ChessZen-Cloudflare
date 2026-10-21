from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, Form, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import uuid
import bcrypt
import jwt
import resend
import requests
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from bson import ObjectId

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# JWT Configuration
JWT_ALGORITHM = "HS256"

def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]

# Resend Configuration
resend.api_key = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
NOTIFICATION_EMAIL = os.environ.get("NOTIFICATION_EMAIL", "viveksingh9612@gmail.com")

# Object Storage Configuration
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "chesszen-classes"
storage_key = None

def init_storage():
    """Initialize storage and get storage key."""
    global storage_key
    if storage_key:
        return storage_key
    try:
        resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
        resp.raise_for_status()
        storage_key = resp.json()["storage_key"]
        logger.info("Object storage initialized successfully")
        return storage_key
    except Exception as e:
        logger.error(f"Failed to initialize storage: {e}")
        return None

def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload file to object storage."""
    key = init_storage()
    if not key:
        raise Exception("Storage not initialized")
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path: str) -> tuple:
    """Download file from object storage."""
    key = init_storage()
    if not key:
        raise Exception("Storage not initialized")
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

# Password Hashing
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# JWT Token Management
def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Pydantic Models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class EnquiryCreate(BaseModel):
    parent_name: str
    student_age: int
    phone: str
    email: EmailStr
    preferred_batch: str
    skill_level: str
    demo_interest: bool
    message: Optional[str] = ""
    consent: bool

class EnquiryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    parent_name: str
    student_age: int
    phone: str
    email: str
    preferred_batch: str
    skill_level: str
    demo_interest: bool
    message: str
    consent: bool
    created_at: str
    status: str = "new"

class TestimonialCreate(BaseModel):
    name: str
    testimonial: str
    rating: Optional[int] = 5
    relation: Optional[str] = "Parent"

class TestimonialResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    testimonial: str
    rating: int
    relation: str
    photo_url: Optional[str] = None
    approved: bool
    created_at: str

class TestimonialUpdate(BaseModel):
    approved: bool

class BookingCreate(BaseModel):
    parent_name: str
    student_name: str
    student_age: int
    phone: str
    email: EmailStr
    preferred_date: str  # ISO date string
    preferred_time: str  # e.g., "10:00 AM", "2:00 PM"
    skill_level: str
    message: Optional[str] = ""

class BookingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    parent_name: str
    student_name: str
    student_age: int
    phone: str
    email: str
    preferred_date: str
    preferred_time: str
    skill_level: str
    message: str
    status: str = "pending"  # pending, confirmed, completed, cancelled
    created_at: str

# Admin Seeding
async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@chesszen.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hashed,
            "name": "Admin",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin user created: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}}
        )
        logger.info(f"Admin password updated: {admin_email}")
    
    # Write credentials to file
    Path("/app/memory").mkdir(exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write("# Test Credentials\n\n")
        f.write("## Admin Account\n")
        f.write(f"- Email: {admin_email}\n")
        f.write(f"- Password: {admin_password}\n")
        f.write("- Role: admin\n\n")
        f.write("## Auth Endpoints\n")
        f.write("- POST /api/auth/login\n")
        f.write("- POST /api/auth/logout\n")
        f.write("- GET /api/auth/me\n")

# Send email notification
async def send_enquiry_notification(enquiry: dict):
    if not resend.api_key:
        logger.warning("RESEND_API_KEY not set, skipping email notification")
        return
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #D4AF37; border-bottom: 2px solid #D4AF37; padding-bottom: 10px;">New Enquiry - ChessZen Classes</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Parent/Student Name:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{enquiry['parent_name']}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Student Age:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{enquiry['student_age']} years</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Phone:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{enquiry['phone']}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Email:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{enquiry['email']}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Preferred Batch:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{enquiry['preferred_batch']}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Skill Level:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{enquiry['skill_level']}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Demo Class Interest:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{'Yes' if enquiry['demo_interest'] else 'No'}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Message:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{enquiry.get('message', 'N/A')}</td></tr>
        </table>
        <p style="margin-top: 20px; color: #666;">This enquiry was submitted on {enquiry['created_at']}</p>
    </div>
    """
    
    params = {
        "from": SENDER_EMAIL,
        "to": [NOTIFICATION_EMAIL],
        "subject": f"New Enquiry from {enquiry['parent_name']} - ChessZen Classes",
        "html": html_content
    }
    
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email notification sent for enquiry from {enquiry['parent_name']}")
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")

# Send booking notification email
async def send_booking_notification(booking: dict):
    if not resend.api_key:
        logger.warning("RESEND_API_KEY not set, skipping email notification")
        return
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #D4AF37; border-bottom: 2px solid #D4AF37; padding-bottom: 10px;">New Demo Class Booking - ChessZen Classes</h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Parent Name:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{booking['parent_name']}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Student Name:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{booking['student_name']}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Student Age:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{booking['student_age']} years</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Phone:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{booking['phone']}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Email:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{booking['email']}</td></tr>
            <tr style="background: #FFF8E1;"><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Preferred Date:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold;">{booking['preferred_date']}</td></tr>
            <tr style="background: #FFF8E1;"><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Preferred Time:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold;">{booking['preferred_time']}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Skill Level:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{booking['skill_level']}</td></tr>
            <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Message:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">{booking.get('message', 'N/A')}</td></tr>
        </table>
        <p style="margin-top: 20px; color: #666;">This booking was submitted on {booking['created_at']}</p>
        <p style="margin-top: 10px; padding: 15px; background: #E8F5E9; border-radius: 4px;">
            <strong>Action Required:</strong> Please confirm this demo class booking by contacting the parent.
        </p>
    </div>
    """
    
    params = {
        "from": SENDER_EMAIL,
        "to": [NOTIFICATION_EMAIL],
        "subject": f"Demo Class Booking: {booking['student_name']} on {booking['preferred_date']} at {booking['preferred_time']}",
        "html": html_content
    }
    
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Booking notification sent for {booking['student_name']}")
    except Exception as e:
        logger.error(f"Failed to send booking notification: {e}")

# Routes
@api_router.get("/")
async def root():
    return {"message": "ChessZen Classes API"}

# Auth Routes
@api_router.post("/auth/login")
async def login(request: LoginRequest, response: Response):
    email = request.email.lower()
    user = await db.users.find_one({"email": email})
    
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user_id = str(user["_id"])
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=86400,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=604800,
        path="/"
    )
    
    return {
        "id": user_id,
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "access_token": access_token
    }

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out successfully"}

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return user

# Admin Stats
@api_router.get("/admin/stats")
async def get_admin_stats(request: Request):
    await get_current_user(request)
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()

    total_bookings = await db.bookings.count_documents({})
    pending_bookings = await db.bookings.count_documents({"status": "pending"})
    confirmed_bookings = await db.bookings.count_documents({"status": "confirmed"})

    total_testimonials = await db.testimonials.count_documents({})
    pending_testimonials = await db.testimonials.count_documents({"approved": False})

    total_enquiries = await db.enquiries.count_documents({})
    recent_enquiries = await db.enquiries.count_documents({"created_at": {"$gte": week_ago}})

    return {
        "total_bookings": total_bookings,
        "pending_bookings": pending_bookings,
        "confirmed_bookings": confirmed_bookings,
        "total_testimonials": total_testimonials,
        "pending_testimonials": pending_testimonials,
        "total_enquiries": total_enquiries,
        "recent_enquiries": recent_enquiries,
    }


# Enquiry Routes
@api_router.post("/enquiries", response_model=EnquiryResponse)
async def create_enquiry(enquiry: EnquiryCreate):
    if not enquiry.consent:
        raise HTTPException(status_code=400, detail="Consent is required")
    
    enquiry_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    doc = {
        "id": enquiry_id,
        "parent_name": enquiry.parent_name,
        "student_age": enquiry.student_age,
        "phone": enquiry.phone,
        "email": enquiry.email,
        "preferred_batch": enquiry.preferred_batch,
        "skill_level": enquiry.skill_level,
        "demo_interest": enquiry.demo_interest,
        "message": enquiry.message or "",
        "consent": enquiry.consent,
        "created_at": created_at,
        "status": "new"
    }
    
    await db.enquiries.insert_one(doc)
    
    # Send email notification in background
    asyncio.create_task(send_enquiry_notification(doc))
    
    return EnquiryResponse(**doc)

@api_router.get("/enquiries", response_model=List[EnquiryResponse])
async def get_enquiries(request: Request):
    await get_current_user(request)  # Auth check
    enquiries = await db.enquiries.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [EnquiryResponse(**e) for e in enquiries]

@api_router.patch("/enquiries/{enquiry_id}/status")
async def update_enquiry_status(enquiry_id: str, status: str = Query(...), request: Request = None):
    await get_current_user(request)  # Auth check
    result = await db.enquiries.update_one(
        {"id": enquiry_id},
        {"$set": {"status": status}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    return {"message": "Status updated"}

# Booking Routes
@api_router.post("/bookings", response_model=BookingResponse)
async def create_booking(booking: BookingCreate):
    booking_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    doc = {
        "id": booking_id,
        "parent_name": booking.parent_name,
        "student_name": booking.student_name,
        "student_age": booking.student_age,
        "phone": booking.phone,
        "email": booking.email,
        "preferred_date": booking.preferred_date,
        "preferred_time": booking.preferred_time,
        "skill_level": booking.skill_level,
        "message": booking.message or "",
        "status": "pending",
        "created_at": created_at
    }
    
    await db.bookings.insert_one(doc)
    
    # Send booking notification email
    asyncio.create_task(send_booking_notification(doc))
    
    return BookingResponse(**doc)

@api_router.get("/bookings", response_model=List[BookingResponse])
async def get_bookings(request: Request):
    await get_current_user(request)  # Auth check
    bookings = await db.bookings.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [BookingResponse(**b) for b in bookings]

@api_router.patch("/bookings/{booking_id}/status")
async def update_booking_status(booking_id: str, status: str = Query(...), request: Request = None):
    await get_current_user(request)  # Auth check
    if status not in ["pending", "confirmed", "completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    result = await db.bookings.update_one(
        {"id": booking_id},
        {"$set": {"status": status}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {"message": "Status updated"}

@api_router.get("/available-slots")
async def get_available_slots(date: str = Query(...)):
    """Get available time slots for a given date."""
    # Define available time slots
    all_slots = [
        "9:00 AM", "10:00 AM", "11:00 AM",
        "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM", "6:00 PM"
    ]
    
    # Get existing bookings for this date
    existing_bookings = await db.bookings.find(
        {"preferred_date": date, "status": {"$ne": "cancelled"}},
        {"_id": 0, "preferred_time": 1}
    ).to_list(100)
    
    booked_times = [b["preferred_time"] for b in existing_bookings]
    available_slots = [slot for slot in all_slots if slot not in booked_times]
    
    return {"date": date, "available_slots": available_slots}

# Testimonial Routes
@api_router.post("/testimonials")
async def create_testimonial(
    name: str = Form(...),
    testimonial: str = Form(...),
    rating: int = Form(5),
    relation: str = Form("Parent"),
    photo: Optional[UploadFile] = File(None)
):
    testimonial_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    photo_url = None
    storage_path = None
    
    if photo and photo.filename:
        try:
            ext = photo.filename.split(".")[-1] if "." in photo.filename else "jpg"
            path = f"{APP_NAME}/testimonials/{testimonial_id}.{ext}"
            data = await photo.read()
            content_type = photo.content_type or "image/jpeg"
            result = put_object(path, data, content_type)
            storage_path = result.get("path", path)
            photo_url = f"/api/files/{storage_path}"
        except Exception as e:
            logger.error(f"Failed to upload photo: {e}")
    
    doc = {
        "id": testimonial_id,
        "name": name,
        "testimonial": testimonial,
        "rating": min(max(rating, 1), 5),
        "relation": relation,
        "photo_url": photo_url,
        "storage_path": storage_path,
        "approved": False,
        "created_at": created_at
    }
    
    await db.testimonials.insert_one(doc)
    
    return TestimonialResponse(
        id=doc["id"],
        name=doc["name"],
        testimonial=doc["testimonial"],
        rating=doc["rating"],
        relation=doc["relation"],
        photo_url=doc["photo_url"],
        approved=doc["approved"],
        created_at=doc["created_at"]
    )

@api_router.get("/testimonials", response_model=List[TestimonialResponse])
async def get_testimonials(approved_only: bool = True):
    query = {"approved": True} if approved_only else {}
    testimonials = await db.testimonials.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [TestimonialResponse(**t) for t in testimonials]

@api_router.get("/admin/testimonials", response_model=List[TestimonialResponse])
async def get_all_testimonials(request: Request):
    await get_current_user(request)  # Auth check
    testimonials = await db.testimonials.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [TestimonialResponse(**t) for t in testimonials]

@api_router.patch("/admin/testimonials/{testimonial_id}")
async def update_testimonial(testimonial_id: str, update: TestimonialUpdate, request: Request):
    await get_current_user(request)  # Auth check
    result = await db.testimonials.update_one(
        {"id": testimonial_id},
        {"$set": {"approved": update.approved}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return {"message": "Testimonial updated"}

@api_router.delete("/admin/testimonials/{testimonial_id}")
async def delete_testimonial(testimonial_id: str, request: Request):
    await get_current_user(request)  # Auth check
    result = await db.testimonials.delete_one({"id": testimonial_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return {"message": "Testimonial deleted"}

# File serving route
@api_router.get("/files/{path:path}")
async def get_file(path: str):
    try:
        data, content_type = get_object(path)
        return Response(content=data, media_type=content_type)
    except Exception as e:
        logger.error(f"Failed to get file: {e}")
        raise HTTPException(status_code=404, detail="File not found")

# ──────────── ANALYTICS: Visitor Tracking ────────────

class VisitorTrack(BaseModel):
    page: str = "/"
    referrer: Optional[str] = None

@api_router.post("/track")
async def track_visitor(body: VisitorTrack, request: Request, response: Response):
    ua = request.headers.get("user-agent", "")
    device = "Mobile" if any(k in ua.lower() for k in ["mobile", "android", "iphone", "ipad"]) else "Desktop"
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    # Get or set visitor cookie
    visitor_id = request.cookies.get("_cz_vid")
    if not visitor_id:
        visitor_id = str(uuid.uuid4())
        response.set_cookie("_cz_vid", visitor_id, max_age=365*86400, httponly=True, samesite="none", secure=True)

    # Check if this visitor already logged today (unique per day)
    existing = await db.visitors.find_one({"visitor_id": visitor_id, "date": date_str})

    if existing:
        # Update page views for returning visitor today
        await db.visitors.update_one(
            {"visitor_id": visitor_id, "date": date_str},
            {"$push": {"pages": body.page}, "$set": {"last_seen": now.isoformat()}}
        )
        return {"status": "updated"}

    # New unique visit for today
    doc = {
        "visitor_id": visitor_id,
        "date": date_str,
        "timestamp": now.isoformat(),
        "last_seen": now.isoformat(),
        "hour": now.hour,
        "device": device,
        "pages": [body.page],
        "referrer": body.referrer,
        "user_agent": ua[:300],
    }
    await db.visitors.insert_one(doc)
    return {"status": "tracked"}


def pct_change(current: int, previous: int) -> float:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


async def compute_period_counts(now: datetime):
    today = now.strftime("%Y-%m-%d")
    weekday = now.weekday()
    week_start = (now - timedelta(days=weekday)).strftime("%Y-%m-%d")
    prev_week_start = (now - timedelta(days=weekday + 7)).strftime("%Y-%m-%d")
    prev_week_end = (now - timedelta(days=weekday + 1)).strftime("%Y-%m-%d")
    month_start = now.strftime("%Y-%m-01")
    prev_month = now.replace(day=1) - timedelta(days=1)
    prev_month_start = prev_month.strftime("%Y-%m-01")
    prev_month_end = prev_month.strftime("%Y-%m-%d")

    today_count = await db.visitors.count_documents({"date": today})
    week_count = await db.visitors.count_documents({"date": {"$gte": week_start}})
    prev_week_count = await db.visitors.count_documents({"date": {"$gte": prev_week_start, "$lte": prev_week_end}})
    month_count = await db.visitors.count_documents({"date": {"$gte": month_start}})
    prev_month_count = await db.visitors.count_documents({"date": {"$gte": prev_month_start, "$lte": prev_month_end}})
    total_count = await db.visitors.count_documents({})

    return {
        "today": today_count,
        "this_week": week_count,
        "prev_week": prev_week_count,
        "week_change": pct_change(week_count, prev_week_count),
        "this_month": month_count,
        "prev_month": prev_month_count,
        "month_change": pct_change(month_count, prev_month_count),
        "total": total_count,
    }


@api_router.get("/admin/analytics/overview")
async def analytics_overview(request: Request):
    await get_current_user(request)
    now = datetime.now(timezone.utc)
    return await compute_period_counts(now)


@api_router.get("/admin/analytics/daily")
async def analytics_daily(request: Request, days: int = Query(default=30, le=90)):
    await get_current_user(request)
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    pipeline = [
        {"$match": {"date": {"$gte": start_date}}},
        {"$group": {"_id": "$date", "visitors": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    results = await db.visitors.aggregate(pipeline).to_list(100)
    data_map = {r["_id"]: r["visitors"] for r in results}

    daily = []
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        daily.append({"date": d, "visitors": data_map.get(d, 0)})

    return daily


@api_router.get("/admin/analytics/weekly")
async def analytics_weekly(request: Request, weeks: int = Query(default=8, le=12)):
    await get_current_user(request)
    now = datetime.now(timezone.utc)
    results = []

    for w in range(weeks):
        week_end = now - timedelta(weeks=w)
        week_start = week_end - timedelta(days=6)
        start_str = week_start.strftime("%Y-%m-%d")
        end_str = week_end.strftime("%Y-%m-%d")
        count = await db.visitors.count_documents({"date": {"$gte": start_str, "$lte": end_str}})
        label = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}"
        results.append({"week": label, "start": start_str, "visitors": count})

    results.reverse()
    return results


@api_router.get("/admin/analytics/top-pages")
async def analytics_top_pages(request: Request, days: int = Query(default=30, le=90)):
    await get_current_user(request)
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    pipeline = [
        {"$match": {"date": {"$gte": start_date}}},
        {"$unwind": "$pages"},
        {"$group": {"_id": "$pages", "views": {"$sum": 1}}},
        {"$sort": {"views": -1}},
        {"$limit": 10},
    ]
    results = await db.visitors.aggregate(pipeline).to_list(10)
    return [{"page": r["_id"], "views": r["views"]} for r in results]


@api_router.get("/admin/analytics/peak-hours")
async def analytics_peak_hours(request: Request, days: int = Query(default=30, le=90)):
    await get_current_user(request)
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    pipeline = [
        {"$match": {"date": {"$gte": start_date}}},
        {"$group": {"_id": "$hour", "visitors": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    results = await db.visitors.aggregate(pipeline).to_list(24)
    hour_map = {r["_id"]: r["visitors"] for r in results}

    hours = []
    for h in range(24):
        label = f"{h:02d}:00"
        hours.append({"hour": label, "h": h, "visitors": hour_map.get(h, 0)})

    return hours


@api_router.get("/admin/analytics/devices")
async def analytics_devices(request: Request, days: int = Query(default=30, le=90)):
    await get_current_user(request)
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    pipeline = [
        {"$match": {"date": {"$gte": start_date}}},
        {"$group": {"_id": "$device", "count": {"$sum": 1}}},
    ]
    results = await db.visitors.aggregate(pipeline).to_list(10)
    return [{"device": r["_id"], "count": r["count"]} for r in results]


@api_router.get("/admin/analytics/export")
async def analytics_export(request: Request, days: int = Query(default=30, le=365)):
    await get_current_user(request)
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    visitors = await db.visitors.find(
        {"date": {"$gte": start_date}},
        {"_id": 0, "visitor_id": 1, "date": 1, "hour": 1, "device": 1, "pages": 1, "referrer": 1, "timestamp": 1}
    ).sort("date", -1).to_list(10000)

    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Time", "Visitor ID", "Device", "Pages Visited", "Referrer"])
    for v in visitors:
        pages = ", ".join(v.get("pages", []))
        writer.writerow([v["date"], f"{v.get('hour', 0):02d}:00", v["visitor_id"][:8], v.get("device", ""), pages, v.get("referrer", "")])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=chesszen_analytics_{start_date}.csv"}
    )

# Include the router in the main app (must be after all route definitions)
app.include_router(api_router)

# Student Management Portal
from portal import router as portal_router, init_portal
init_portal(db, get_current_user, put_object, APP_NAME)
app.include_router(portal_router)

# CORS Configuration
cors_origins = [
    os.environ.get("FRONTEND_URL", "http://localhost:3000"),
    "https://chess-zen.in",
    "https://www.chess-zen.in",
    "https://chesszen-academy.preview.emergentagent.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await seed_admin()
    try:
        init_storage()
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.enquiries.create_index("created_at")
    await db.testimonials.create_index("created_at")
    await db.testimonials.create_index("approved")
    await db.visitors.create_index([("visitor_id", 1), ("date", 1)])
    await db.visitors.create_index("date")
    await db.visitors.create_index("hour")
    await db.students.create_index("batch_id")
    await db.students.create_index("status")
    await db.students.create_index("full_name")
    await db.attendance.create_index([("student_id", 1), ("date", 1)], unique=True)
    await db.attendance.create_index("date")
    await db.payments.create_index("student_id")
    await db.tests.create_index("student_id")
    await db.tests.create_index("test_name")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
