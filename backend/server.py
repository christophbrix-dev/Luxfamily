"""FastAPI backend for Luxembourg Family Activities.

Provides:
 - JWT-based authentication with bcrypt password hashing
 - Seeded admin account on startup (from .env)
 - Admin-only CRUD for events
 - Public read endpoints used by the mobile app
 - Brute-force protection on /api/auth/login via slowapi
"""

import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.cors import CORSMiddleware

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
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        created_by=doc.get("created_by"),
    )


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Dict[str, Any]:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
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

    yield
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
    cursor = db.events.find(query, {"_id": 0}).sort("start_date", 1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_event_to_response(d) for d in docs]


@app.get("/api/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: str):
    doc = await db.events.find_one({"id": event_id, "published": True}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_response(doc)


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


# Health probe used by tests / supervisor.
@app.get("/api/health")
async def health():
    try:
        await db.command("ping")
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "detail": str(exc)}
