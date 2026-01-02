"""
Conference Room Calendar Display
A tablet-friendly calendar display for conference room scheduling.
"""
import os
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from database import get_db, init_db
from auth.google import router as google_router
from auth.microsoft import router as microsoft_router
from services.calendar import CalendarService

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield

app = FastAPI(
    title="Conference Room Display",
    description="Calendar display for conference rooms",
    lifespan=lifespan
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include auth routers
app.include_router(google_router, prefix="/auth/google", tags=["Google Auth"])
app.include_router(microsoft_router, prefix="/auth/microsoft", tags=["Microsoft Auth"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    """Main display page."""
    calendar_service = CalendarService(db)
    rooms = await calendar_service.get_rooms()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "rooms": rooms,
        "has_google": bool(os.getenv("GOOGLE_CLIENT_ID")),
        "has_microsoft": bool(os.getenv("MICROSOFT_CLIENT_ID")),
    })


@app.get("/display/{room_id}", response_class=HTMLResponse)
async def room_display(request: Request, room_id: int, db: AsyncSession = Depends(get_db)):
    """Display page for a specific room."""
    calendar_service = CalendarService(db)
    room = await calendar_service.get_room(room_id)

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    return templates.TemplateResponse("display.html", {
        "request": request,
        "room": room,
    })


@app.get("/api/rooms")
async def list_rooms(db: AsyncSession = Depends(get_db)):
    """List all configured rooms."""
    calendar_service = CalendarService(db)
    rooms = await calendar_service.get_rooms()
    return {"rooms": rooms}


@app.get("/api/rooms/{room_id}/events")
async def get_room_events(room_id: int, db: AsyncSession = Depends(get_db)):
    """Get today's events for a room."""
    calendar_service = CalendarService(db)

    room = await calendar_service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    events = await calendar_service.get_todays_events(room_id)
    current_event = await calendar_service.get_current_event(room_id)
    next_event = await calendar_service.get_next_event(room_id)

    return {
        "room": room,
        "events": events,
        "current_event": current_event,
        "next_event": next_event,
        "is_available": current_event is None,
        "server_time": datetime.now().isoformat(),
    }


@app.post("/api/rooms/{room_id}/book")
async def book_room(
    room_id: int,
    duration_minutes: int = 30,
    title: str = "Quick Booking",
    db: AsyncSession = Depends(get_db)
):
    """Quick book a room for the specified duration."""
    calendar_service = CalendarService(db)

    room = await calendar_service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Check if room is available
    current_event = await calendar_service.get_current_event(room_id)
    if current_event:
        raise HTTPException(status_code=400, detail="Room is currently occupied")

    # Check if booking conflicts with next event
    next_event = await calendar_service.get_next_event(room_id)
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration_minutes)

    if next_event and next_event.get("start"):
        next_start = datetime.fromisoformat(next_event["start"].replace("Z", "+00:00"))
        if end_time > next_start.replace(tzinfo=None):
            # Adjust end time to not conflict
            end_time = next_start.replace(tzinfo=None)
            if (end_time - start_time).total_seconds() < 300:  # Less than 5 minutes
                raise HTTPException(
                    status_code=400,
                    detail="Not enough time before next meeting"
                )

    # Create the booking
    event = await calendar_service.create_event(
        room_id=room_id,
        title=title,
        start_time=start_time,
        end_time=end_time,
    )

    return {"success": True, "event": event}


@app.post("/api/rooms/{room_id}/extend")
async def extend_meeting(
    room_id: int,
    minutes: int = 15,
    db: AsyncSession = Depends(get_db)
):
    """Extend the current meeting."""
    calendar_service = CalendarService(db)

    current_event = await calendar_service.get_current_event(room_id)
    if not current_event:
        raise HTTPException(status_code=400, detail="No active meeting to extend")

    result = await calendar_service.extend_event(
        room_id=room_id,
        event_id=current_event["id"],
        minutes=minutes,
    )

    return {"success": True, "event": result}


@app.post("/api/rooms/{room_id}/end")
async def end_meeting(room_id: int, db: AsyncSession = Depends(get_db)):
    """End the current meeting early."""
    calendar_service = CalendarService(db)

    current_event = await calendar_service.get_current_event(room_id)
    if not current_event:
        raise HTTPException(status_code=400, detail="No active meeting to end")

    await calendar_service.end_event(
        room_id=room_id,
        event_id=current_event["id"],
    )

    return {"success": True}


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Setup page for configuring rooms and calendars."""
    calendar_service = CalendarService(db)
    rooms = await calendar_service.get_rooms()

    return templates.TemplateResponse("setup.html", {
        "request": request,
        "rooms": rooms,
        "has_google": bool(os.getenv("GOOGLE_CLIENT_ID")),
        "has_microsoft": bool(os.getenv("MICROSOFT_CLIENT_ID")),
    })


@app.post("/api/rooms")
async def create_room(
    name: str,
    calendar_id: str = None,
    calendar_provider: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Create a new room configuration."""
    calendar_service = CalendarService(db)

    room = await calendar_service.create_room(
        name=name,
        calendar_id=calendar_id,
        calendar_provider=calendar_provider,
    )

    return {"success": True, "room": room}


@app.delete("/api/rooms/{room_id}")
async def delete_room(room_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a room configuration."""
    calendar_service = CalendarService(db)
    await calendar_service.delete_room(room_id)
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
