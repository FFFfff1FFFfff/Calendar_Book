import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import close_pool, init_pool
from app.routes.auth import router as auth_router
from app.routes.availability import router as availability_router
from app.routes.booking import router as booking_router
from app.routes.owner import router as owner_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    await init_pool(settings.database_url)
    yield
    await close_pool()


app = FastAPI(title="Calendar Booking API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(availability_router)
app.include_router(booking_router)
app.include_router(owner_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


from fastapi.responses import HTMLResponse

_BOOKING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Book an Appointment</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <div class="container">
    <h1>Book an Appointment</h1>
    <p class="subtitle" id="ownerInfo">Choose a date and time that works for you.</p>
    <div id="errorMsg" class="status-msg error hidden"></div>
    <div id="stepDate" class="card">
      <h2>Select a Date</h2>
      <div class="form-group"><input type="date" id="datePicker" /></div>
    </div>
    <div id="stepSlots" class="card hidden">
      <h2>Available Times</h2>
      <div id="slotsLoading" class="loading-text">Loading available times&hellip;</div>
      <div id="slotsGrid" class="slots-grid"></div>
      <p id="noSlots" class="loading-text hidden">No available slots for this date.</p>
    </div>
    <div id="stepForm" class="card hidden">
      <h2>Your Details</h2>
      <div class="form-group"><label for="customerName">Name</label>
        <input type="text" id="customerName" placeholder="Jane Smith" required /></div>
      <div class="form-group"><label for="customerEmail">Email</label>
        <input type="email" id="customerEmail" placeholder="jane@example.com" required /></div>
      <button class="btn btn-primary" id="bookBtn" disabled>Confirm Booking</button>
    </div>
    <div id="stepConfirm" class="card hidden">
      <div class="confirmation">
        <div class="check-icon">&#10003;</div>
        <h2>Booking Confirmed</h2>
        <p>You'll receive a calendar invite shortly.</p>
      </div>
      <div id="confirmDetails"></div><br/>
      <button class="btn btn-primary" onclick="location.reload()">Book Another</button>
    </div>
  </div>
  <script src="/app.js"></script>
</body>
</html>"""


@app.get("/book/{slug:path}")
async def serve_booking_page(slug: str):
    return HTMLResponse(_BOOKING_HTML)


# Serve static files locally (Vercel uses @vercel/static instead)
_public_dir = _PROJECT_ROOT / "public"
if _public_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_public_dir), html=True), name="static")
