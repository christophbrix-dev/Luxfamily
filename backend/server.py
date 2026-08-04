"""FastAPI backend for Luxembourg Family Activities.

Provides:
 - JWT-based authentication with bcrypt password hashing
 - Seeded admin account on startup (from .env)
 - Admin-only CRUD for events
 - Public read endpoints used by the mobile app
 - Brute-force protection on /api/auth/login via slowapi
"""

import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import bcrypt
import httpx
import jwt
import stripe
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.cors import CORSMiddleware

from importers import run_all_active, run_source

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("lux-backend")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


MONGO_URL = _require_env("MONGO_URL")
DB_NAME = _require_env("DB_NAME")
JWT_SECRET = _require_env("JWT_SECRET")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))
ADMIN_EMAIL = _require_env("ADMIN_EMAIL").lower()
ADMIN_PASSWORD = _require_env("ADMIN_PASSWORD")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
stripe.api_key = STRIPE_SECRET_KEY

# Plan -> (cents, days)
SPONSOR_PLANS: Dict[str, Dict[str, int]] = {
    "1month": {"amount": 4900, "days": 30},
    "3months": {"amount": 12900, "days": 90},
    "6months": {"amount": 22900, "days": 180},
}

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ---------------------------------------------------------------------------
# Password & token helpers
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Pydantic models — strict response shapes so MongoDB internals never leak
# ---------------------------------------------------------------------------
LocalizedString = Dict[Literal["en", "de", "fr"], str]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    name: Optional[str] = None


class EventBase(BaseModel):
    title: LocalizedString
    short: LocalizedString
    description: LocalizedString
    type: Literal["Event", "Indoor", "Outdoor", "Educational"] = "Event"
    canton: str
    town: str
    category: List[str] = Field(default_factory=list)
    age_min: int = 0
    age_max: int = 99
    start_date: str  # ISO date (YYYY-MM-DD)
    end_date: Optional[str] = None
    time: str = ""
    price_adult: float = 0.0
    price_child: float = 0.0
    price_label: LocalizedString
    accessibility: LocalizedString
    weather_fit: LocalizedString
    image: str = ""  # URL or base64 data URI
    lat: float
    lng: float
    bookable: bool = False
    published: bool = True
    rating: float = 4.5
    featured: bool = False
    featured_until: Optional[str] = None
    view_count: int = 0
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    external_id: Optional[str] = None
    # Family-friendly detail fields (added per user feedback Jun 2026).
    website_url: str = ""
    accessibility_wheelchair: bool = False
    sensory_friendly: bool = False
    free_parking: bool = False
    sensory_notes: LocalizedString = Field(default_factory=lambda: {"en": "", "de": "", "fr": ""})
    parking: LocalizedString = Field(default_factory=lambda: {"en": "", "de": "", "fr": ""})
    food_allowed: bool = True
    food_onsite: LocalizedString = Field(default_factory=lambda: {"en": "", "de": "", "fr": ""})
    preparation_tips: LocalizedString = Field(default_factory=lambda: {"en": "", "de": "", "fr": ""})
    payment_methods: List[str] = Field(default_factory=list)
    opening_hours: LocalizedString = Field(default_factory=lambda: {"en": "", "de": "", "fr": ""})
    peak_hours: LocalizedString = Field(default_factory=lambda: {"en": "", "de": "", "fr": ""})
    changing_facilities: bool = False
    restrooms: bool = True


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[LocalizedString] = None
    short: Optional[LocalizedString] = None
    description: Optional[LocalizedString] = None
    type: Optional[str] = None
    canton: Optional[str] = None
    town: Optional[str] = None
    category: Optional[List[str]] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    time: Optional[str] = None
    price_adult: Optional[float] = None
    price_child: Optional[float] = None
    price_label: Optional[LocalizedString] = None
    accessibility: Optional[LocalizedString] = None
    weather_fit: Optional[LocalizedString] = None
    image: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    bookable: Optional[bool] = None
    published: Optional[bool] = None
    rating: Optional[float] = None
    featured: Optional[bool] = None
    featured_until: Optional[str] = None
    website_url: Optional[str] = None
    accessibility_wheelchair: Optional[bool] = None
    sensory_friendly: Optional[bool] = None
    free_parking: Optional[bool] = None
    sensory_notes: Optional[LocalizedString] = None
    parking: Optional[LocalizedString] = None
    food_allowed: Optional[bool] = None
    food_onsite: Optional[LocalizedString] = None
    preparation_tips: Optional[LocalizedString] = None
    payment_methods: Optional[List[str]] = None
    opening_hours: Optional[LocalizedString] = None
    peak_hours: Optional[LocalizedString] = None
    changing_facilities: Optional[bool] = None
    restrooms: Optional[bool] = None


class EventResponse(EventBase):
    id: str
    created_at: str
    updated_at: str
    created_by: Optional[str] = None


TokenResponse.model_rebuild()


def _event_to_response(doc: Dict[str, Any]) -> EventResponse:
    return EventResponse(
        id=doc["id"],
        title=doc["title"],
        short=doc["short"],
        description=doc["description"],
        type=doc.get("type", "Event"),
        canton=doc["canton"],
        town=doc["town"],
        category=doc.get("category", []),
        age_min=doc.get("age_min", 0),
        age_max=doc.get("age_max", 99),
        start_date=doc["start_date"],
        end_date=doc.get("end_date"),
        time=doc.get("time", ""),
        price_adult=doc.get("price_adult", 0.0),
        price_child=doc.get("price_child", 0.0),
        price_label=doc["price_label"],
        accessibility=doc["accessibility"],
        weather_fit=doc["weather_fit"],
        image=doc.get("image", ""),
        lat=doc["lat"],
        lng=doc["lng"],
        bookable=doc.get("bookable", False),
        published=doc.get("published", True),
        rating=doc.get("rating", 4.5),
        featured=doc.get("featured", False),
        featured_until=doc.get("featured_until"),
        view_count=doc.get("view_count", 0),
        source_id=doc.get("source_id"),
        source_name=doc.get("source_name"),
        external_id=doc.get("external_id"),
        website_url=doc.get("website_url", ""),
        accessibility_wheelchair=doc.get("accessibility_wheelchair", False),
        sensory_friendly=doc.get("sensory_friendly", False),
        free_parking=doc.get("free_parking", False),
        sensory_notes=doc.get("sensory_notes") or {"en": "", "de": "", "fr": ""},
        parking=doc.get("parking") or {"en": "", "de": "", "fr": ""},
        food_allowed=doc.get("food_allowed", True),
        food_onsite=doc.get("food_onsite") or {"en": "", "de": "", "fr": ""},
        preparation_tips=doc.get("preparation_tips") or {"en": "", "de": "", "fr": ""},
        payment_methods=doc.get("payment_methods", []),
        opening_hours=doc.get("opening_hours") or {"en": "", "de": "", "fr": ""},
        peak_hours=doc.get("peak_hours") or {"en": "", "de": "", "fr": ""},
        changing_facilities=doc.get("changing_facilities", False),
        restrooms=doc.get("restrooms", True),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        created_by=doc.get("created_by"),
    )


# ---- Source models ----
class SourceBase(BaseModel):
    name: str
    kind: Literal["ical", "data_public_lu", "html_scraper", "json_ld", "sitemap"]
    url: str
    active: bool = True
    canton_default: str = "Luxembourg"
    town_default: str = "Luxembourg"
    category_default: List[str] = Field(default_factory=lambda: ["Culture"])
    age_min_default: int = 0
    age_max_default: int = 99
    lat_default: float = 49.6116
    lng_default: float = 6.1319
    image_default: str = ""
    selectors: Optional[Dict[str, str]] = None


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    kind: Optional[Literal["ical", "data_public_lu", "html_scraper", "json_ld", "sitemap"]] = None
    url: Optional[str] = None
    active: Optional[bool] = None
    canton_default: Optional[str] = None
    town_default: Optional[str] = None
    category_default: Optional[List[str]] = None
    age_min_default: Optional[int] = None
    age_max_default: Optional[int] = None
    lat_default: Optional[float] = None
    lng_default: Optional[float] = None
    image_default: Optional[str] = None
    selectors: Optional[Dict[str, str]] = None


class SourceResponse(SourceBase):
    id: str
    created_at: str
    last_run_at: Optional[str] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    last_imported_count: Optional[int] = None
    last_skipped_count: Optional[int] = None


def _source_to_response(doc: Dict[str, Any]) -> SourceResponse:
    return SourceResponse(**{k: v for k, v in doc.items() if k != "_id"})


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Dict[str, Any]:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    # Path 1: Google-Auth session token — look up in user_sessions collection.
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if session:
        expires_at = session.get("expires_at")
        if isinstance(expires_at, datetime):
            # Normalize to timezone-aware for comparison.
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                raise HTTPException(status_code=401, detail="Session expired")
        user = await db.users.find_one({"id": session["user_id"]}, {"_id": 0})
        if user:
            return user
        raise HTTPException(status_code=401, detail="User not found")

    # Path 2: Legacy JWT (used by admin email/password login).
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(current: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current


# ---------------------------------------------------------------------------
# Lifespan: indexes + seed admin
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.events.create_index("id", unique=True)
    await db.events.create_index("start_date")
    await db.events.create_index([("source_id", 1), ("external_id", 1)], sparse=True)
    await db.sources.create_index("id", unique=True)
    await db.event_views.create_index("event_id")
    await db.event_views.create_index("viewed_at")
    await db.partners.create_index("id", unique=True)
    await db.partners.create_index("created_at")
    await db.sponsorships.create_index("session_id", unique=True)
    await db.sponsorships.create_index("event_id")
    # Google Auth session storage
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("user_id")
    # TTL index — MongoDB auto-removes rows after expires_at.
    try:
        await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
    except Exception:
        pass  # already exists with different options — non-fatal

    # Idempotent admin seeding.
    existing = await db.users.find_one({"email": ADMIN_EMAIL})
    if not existing:
        admin_doc = {
            "id": str(uuid.uuid4()),
            "email": ADMIN_EMAIL,
            "hashed_password": hash_password(ADMIN_PASSWORD),
            "role": "admin",
            "name": "Administrator",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(admin_doc)
        logger.info("Seeded admin user %s", ADMIN_EMAIL)
    else:
        logger.info("Admin user already exists: %s", ADMIN_EMAIL)

    # Background importer cron: 3x daily at 05:00, 12:00, 18:00 Europe/Luxembourg.
    # We skip the scheduler in pytest runs to keep the test suite hermetic
    # (toggle with DISABLE_SCHEDULER=1).
    scheduler: Optional[AsyncIOScheduler] = None
    if os.environ.get("DISABLE_SCHEDULER") != "1":
        from apscheduler.triggers.cron import CronTrigger

        scheduler = AsyncIOScheduler(timezone="Europe/Luxembourg")
        scheduler.add_job(
            run_all_active,
            CronTrigger(hour="5,12,18", minute=0, timezone="Europe/Luxembourg"),
            args=[db],
            id="importers",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Importer scheduler started (3x daily: 05:00, 12:00, 18:00 Europe/Luxembourg)")

    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        client.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(lifespan=lifespan, title="Family Luxembourg API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/")
async def root():
    return {"service": "Family Luxembourg API", "version": "1.0"}


# ---- Auth ----
@app.post("/api/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest = Body(...)):
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = create_access_token(user["id"], user["role"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"], email=user["email"], role=user["role"], name=user.get("name")
        ),
    )


@app.get("/api/auth/me", response_model=UserResponse)
async def me(current: Dict[str, Any] = Depends(get_current_user)):
    return UserResponse(
        id=current["id"],
        email=current["email"],
        role=current["role"],
        name=current.get("name"),
    )


# ---------------------------------------------------------------------------
# Google Auth (Emergent-managed) — exchange session_id → session_token.
# ---------------------------------------------------------------------------
class GoogleSessionRequest(BaseModel):
    session_id: str


class GoogleAuthUser(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    role: str = "user"


class GoogleSessionResponse(BaseModel):
    session_token: str
    user: GoogleAuthUser


EMERGENT_SESSION_URL = os.environ["EMERGENT_SESSION_URL"]


@app.post("/api/auth/session", response_model=GoogleSessionResponse)
async def exchange_google_session(payload: GoogleSessionRequest):
    """Redeem a one-time Emergent session_id (returned by the OAuth redirect)
    for a 7-day session_token this backend controls.

    - Never accepts a session_token — only a fresh session_id.
    - Upserts the user by email (reuse existing user_id if present).
    - Stores the session in `user_sessions` with a TTL index.
    """
    if not payload.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                EMERGENT_SESSION_URL,
                headers={"X-Session-ID": payload.session_id.strip()},
            )
        except httpx.HTTPError as exc:
            logger.warning("Emergent session-data fetch failed: %s", exc)
            raise HTTPException(status_code=401, detail="Session verification failed")

    if resp.status_code != 200:
        logger.info("Emergent session-data returned %s", resp.status_code)
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    data = resp.json()
    email = (data.get("email") or "").strip().lower()
    session_token = data.get("session_token")
    name = data.get("name") or ""
    picture = data.get("picture") or ""

    if not email or not session_token:
        raise HTTPException(status_code=401, detail="Malformed session data")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)

    # Upsert user by email — reuse existing user_id when known.
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["id"]
        role = existing.get("role", "user")
        # Update name/picture if changed
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"name": name or existing.get("name", ""),
                       "picture": picture or existing.get("picture", ""),
                       "provider": "google",
                       "last_login_at": now.isoformat()}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        role = "user"
        await db.users.insert_one({
            "id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "provider": "google",
            "role": role,
            "hashed_password": "",           # Google users have no password
            "created_at": now.isoformat(),
            "last_login_at": now.isoformat(),
        })

    # Insert the session row (idempotent on session_token uniqueness).
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {
            "$set": {
                "session_token": session_token,
                "user_id": user_id,
                "created_at": now,
                "expires_at": expires_at,
            }
        },
        upsert=True,
    )

    return GoogleSessionResponse(
        session_token=session_token,
        user=GoogleAuthUser(
            id=user_id,
            email=email,
            name=name or None,
            picture=picture or None,
            role=role,
        ),
    )


@app.post("/api/auth/logout", status_code=204)
async def logout(current: Dict[str, Any] = Depends(get_current_user),
                  token: Optional[str] = Depends(oauth2_scheme)):
    """Invalidate the current session token (if it's a Google session)."""
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    return None


@app.delete("/api/auth/me", status_code=204)
async def delete_my_account(current: Dict[str, Any] = Depends(get_current_user)):
    """GDPR / Apple App Store requirement: user-initiated permanent account deletion.

    Removes the user's row, all of their sessions, and any personal data
    they created. Public content (events they submitted, bookings that
    reference partner venues) is anonymised — the `created_by` field is
    replaced with 'deleted_user', not deleted, so downstream analytics
    stay consistent.
    """
    uid = current["id"]
    # Delete personal auth artefacts.
    await db.user_sessions.delete_many({"user_id": uid})
    # Anonymise anything they created but keep the content itself.
    await db.events.update_many(
        {"created_by": uid},
        {"$set": {"created_by": "deleted_user"}},
    )
    # Finally, remove the user row itself. Guard against deleting the
    # seed admin account through this endpoint.
    if current.get("email", "").lower() == (ADMIN_EMAIL or "").lower():
        raise HTTPException(status_code=400,
                             detail="Admin account cannot be deleted this way.")
    await db.users.delete_one({"id": uid})
    return None


# ---- Public events ----
@app.get("/api/events", response_model=List[EventResponse])
async def list_events(
    canton: Optional[str] = None,
    upcoming: bool = True,
    limit: int = 200,
):
    query: Dict[str, Any] = {"published": True}
    if canton:
        query["canton"] = canton
    if upcoming:
        today = datetime.now(timezone.utc).date().isoformat()
        query["start_date"] = {"$gte": today}
    # Featured events first, then by start date.
    cursor = (
        db.events.find(query, {"_id": 0})
        .sort([("featured", -1), ("start_date", 1)])
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_event_to_response(d) for d in docs]


@app.get("/api/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: str):
    doc = await db.events.find_one({"id": event_id, "published": True}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_response(doc)


@app.post("/api/events/{event_id}/view", status_code=204)
async def event_view(event_id: str, request: Request):
    # Fire-and-forget ping. We count anonymous views but rate-limit per IP+event
    # so a refresh loop can't inflate stats.
    ip = get_remote_address(request)
    minute_bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    bucket_id = f"{event_id}:{ip}:{minute_bucket}"
    seen = await db.event_views_dedup.find_one({"_id": bucket_id})
    if seen:
        return
    try:
        await db.event_views_dedup.insert_one(
            {"_id": bucket_id, "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)}
        )
    except Exception:
        return  # race — already counted

    await db.events.update_one({"id": event_id}, {"$inc": {"view_count": 1}})
    await db.event_views.insert_one(
        {
            "event_id": event_id,
            "viewed_at": datetime.now(timezone.utc).isoformat(),
            "ip_hash": str(hash(ip))[:12],
        }
    )


# ---- Admin events ----
@app.get("/api/admin/events", response_model=List[EventResponse])
async def admin_list_events(_: Dict[str, Any] = Depends(require_admin)):
    cursor = db.events.find({}, {"_id": 0}).sort("start_date", 1)
    docs = await cursor.to_list(length=1000)
    return [_event_to_response(d) for d in docs]


@app.post("/api/admin/events", response_model=EventResponse, status_code=201)
async def admin_create_event(
    body: EventCreate, admin: Dict[str, Any] = Depends(require_admin)
):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        **body.model_dump(),
        "id": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
        "created_by": admin["id"],
    }
    await db.events.insert_one(doc)
    doc.pop("_id", None)
    return _event_to_response(doc)


@app.patch("/api/admin/events/{event_id}", response_model=EventResponse)
async def admin_update_event(
    event_id: str,
    body: EventUpdate,
    _: Dict[str, Any] = Depends(require_admin),
):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.events.find_one_and_update(
        {"id": event_id},
        {"$set": updates},
        return_document=True,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_response(result)


@app.delete("/api/admin/events/{event_id}", status_code=204)
async def admin_delete_event(
    event_id: str, _: Dict[str, Any] = Depends(require_admin)
):
    result = await db.events.delete_one({"id": event_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Event not found")


# ---------------------------------------------------------------------------
# Partner submissions + Stripe sponsored slots
# ---------------------------------------------------------------------------
class PartnerCreate(BaseModel):
    name: str
    venue: str
    email: EmailStr
    website: Optional[str] = ""
    instagram: Optional[str] = ""
    facebook: Optional[str] = ""
    message: Optional[str] = ""


@app.post("/api/partners", status_code=201)
@limiter.limit("5/minute")
async def submit_partner(request: Request, body: PartnerCreate = Body(...)):
    doc = {
        **body.model_dump(),
        "id": str(uuid.uuid4()),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.partners.insert_one(doc)
    return {"id": doc["id"], "status": "pending"}


@app.get("/api/admin/partners")
async def admin_list_partners(_: Dict[str, Any] = Depends(require_admin)):
    cursor = db.partners.find({}, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=500)


@app.patch("/api/admin/partners/{partner_id}")
async def admin_update_partner(
    partner_id: str,
    body: Dict[str, Any] = Body(...),
    _: Dict[str, Any] = Depends(require_admin),
):
    allowed = {k: v for k, v in body.items() if k in {"status", "message"}}
    if not allowed:
        raise HTTPException(400, "No allowed fields")
    result = await db.partners.find_one_and_update(
        {"id": partner_id}, {"$set": allowed}, return_document=True, projection={"_id": 0}
    )
    if not result:
        raise HTTPException(404, "Partner not found")
    return result


class CheckoutRequest(BaseModel):
    event_id: str
    plan: str


@app.post("/api/sponsor/checkout")
async def create_sponsor_checkout(body: CheckoutRequest = Body(...)):
    if body.plan not in SPONSOR_PLANS:
        raise HTTPException(400, "Invalid plan")
    event = await db.events.find_one({"id": body.event_id}, {"_id": 0, "title": 1})
    if not event:
        raise HTTPException(404, "Event not found")
    plan = SPONSOR_PLANS[body.plan]
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": f"Featured slot ({body.plan}) — {event['title'].get('en', 'Event')}"
                        },
                        "unit_amount": plan["amount"],
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{FRONTEND_URL}/sponsor/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/sponsor/cancel",
            metadata={"event_id": body.event_id, "plan": body.plan},
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(502, f"Stripe error: {exc.user_message or str(exc)}")
    return {"url": session.url, "session_id": session.id}


@app.get("/api/sponsor/session/{session_id}")
async def get_sponsor_session(session_id: str):
    """Frontend polls this on the success page so the partner sees confirmation
    even if our webhook hasn't been wired in this environment."""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError as exc:
        raise HTTPException(404, str(exc))
    paid = session.payment_status == "paid"
    if paid:
        await _grant_featured(session)
    return {
        "paid": paid,
        "payment_status": session.payment_status,
        "amount_total": session.amount_total,
        "event_id": (session.metadata or {}).get("event_id"),
        "plan": (session.metadata or {}).get("plan"),
    }


async def _grant_featured(session) -> None:
    session_id = session.id if hasattr(session, "id") else session["id"]
    metadata = session.metadata if hasattr(session, "metadata") else session.get("metadata", {})
    event_id = metadata.get("event_id")
    plan = metadata.get("plan")
    amount_total = session.amount_total if hasattr(session, "amount_total") else session.get("amount_total", 0)
    if not (event_id and plan and plan in SPONSOR_PLANS):
        return
    result = await db.sponsorships.update_one(
        {"session_id": session_id},
        {
            "$setOnInsert": {
                "session_id": session_id,
                "event_id": event_id,
                "plan": plan,
                "amount_total": amount_total,
                "status": "paid",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    if not result.upserted_id:
        return  # duplicate, already processed
    days = SPONSOR_PLANS[plan]["days"]
    ev = await db.events.find_one({"id": event_id}, {"_id": 0, "featured_until": 1})
    now = datetime.now(timezone.utc)
    base = now
    if ev and ev.get("featured_until"):
        try:
            existing = datetime.fromisoformat(ev["featured_until"].replace("Z", "+00:00"))
            if existing > now:
                base = existing
        except (ValueError, TypeError):
            pass
    new_until = (base + timedelta(days=days)).date().isoformat()
    await db.events.update_one(
        {"id": event_id},
        {"$set": {"featured": True, "featured_until": new_until}},
    )


@app.post("/api/sponsor/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError):
            raise HTTPException(400, "Invalid webhook signature")
    else:
        # No webhook secret configured (e.g. preview environment). Trust payload.
        event = json.loads(payload)
    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        if session.get("payment_status") == "paid":
            await _grant_featured(stripe.util.convert_to_stripe_object(session))
    return {"received": True}


# Health probe used by tests / supervisor.
@app.get("/api/health")
async def health():
    try:
        await db.command("ping")
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "detail": str(exc)}


# ---------------------------------------------------------------------------
# Admin: Sources (auto-importer configuration)
# ---------------------------------------------------------------------------
@app.get("/api/admin/sources", response_model=List[SourceResponse])
async def admin_list_sources(_: Dict[str, Any] = Depends(require_admin)):
    cursor = db.sources.find({}, {"_id": 0}).sort("created_at", 1)
    docs = await cursor.to_list(length=200)
    return [_source_to_response(d) for d in docs]


@app.post("/api/admin/sources", response_model=SourceResponse, status_code=201)
async def admin_create_source(
    body: SourceCreate = Body(...), _: Dict[str, Any] = Depends(require_admin)
):
    doc = {
        **body.model_dump(),
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "last_imported_count": None,
        "last_skipped_count": None,
    }
    await db.sources.insert_one(doc)
    doc.pop("_id", None)
    return _source_to_response(doc)


@app.patch("/api/admin/sources/{source_id}", response_model=SourceResponse)
async def admin_update_source(
    source_id: str,
    body: SourceUpdate = Body(...),
    _: Dict[str, Any] = Depends(require_admin),
):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db.sources.find_one_and_update(
        {"id": source_id}, {"$set": updates}, return_document=True, projection={"_id": 0}
    )
    if not result:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_to_response(result)


@app.delete("/api/admin/sources/{source_id}", status_code=204)
async def admin_delete_source(
    source_id: str, _: Dict[str, Any] = Depends(require_admin)
):
    result = await db.sources.delete_one({"id": source_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Source not found")


@app.post("/api/admin/sources/{source_id}/run")
async def admin_run_source(
    source_id: str, _: Dict[str, Any] = Depends(require_admin)
):
    source = await db.sources.find_one({"id": source_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return await run_source(source, db)


@app.post("/api/admin/sources/run-all")
async def admin_run_all(_: Dict[str, Any] = Depends(require_admin)):
    return {"runs": await run_all_active(db)}


class RobotsCheckRequest(BaseModel):
    url: str


@app.post("/api/admin/sources/robots-check")
async def admin_robots_check(
    payload: RobotsCheckRequest,
    _: Dict[str, Any] = Depends(require_admin),
):
    """Diagnostic: probe a URL to see whether our crawler is allowed and what
    Crawl-delay the site publishes."""
    from crawler_utils import robots_check

    try:
        return await robots_check(payload.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"robots-check failed: {exc}")


# ---------------------------------------------------------------------------
# Admin analytics
# ---------------------------------------------------------------------------
@app.get("/api/admin/analytics/overview")
async def admin_analytics(_: Dict[str, Any] = Depends(require_admin)):
    total = await db.events.count_documents({})
    published = await db.events.count_documents({"published": True})
    featured = await db.events.count_documents({"featured": True, "published": True})
    drafts = total - published
    total_views_doc = await db.events.aggregate(
        [{"$group": {"_id": None, "v": {"$sum": "$view_count"}}}]
    ).to_list(1)
    total_views = total_views_doc[0]["v"] if total_views_doc else 0
    top_cursor = (
        db.events.find({"published": True}, {"_id": 0, "id": 1, "title": 1, "view_count": 1})
        .sort("view_count", -1)
        .limit(5)
    )
    top = await top_cursor.to_list(5)
    return {
        "total_events": total,
        "published": published,
        "drafts": drafts,
        "featured": featured,
        "total_views": total_views,
        "top_events": [
            {"id": t["id"], "title": t["title"].get("en", ""), "view_count": t.get("view_count", 0)}
            for t in top
        ],
    }
