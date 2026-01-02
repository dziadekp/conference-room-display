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
async def get_room_events(
    room_id: int,
    date: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Get events for a room on a specific date (default: today)."""
    calendar_service = CalendarService(db)

    room = await calendar_service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Parse date or use today
    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    events = await calendar_service.get_events_for_date(room_id, target_date)
    current_event = await calendar_service.get_current_event(room_id) if not target_date or target_date == datetime.now().date() else None
    next_event = await calendar_service.get_next_event(room_id) if not target_date or target_date == datetime.now().date() else None

    return {
        "room": room,
        "events": events,
        "current_event": current_event,
        "next_event": next_event,
        "is_available": current_event is None,
        "server_time": datetime.now().isoformat(),
        "date": (target_date or datetime.now().date()).isoformat(),
    }


@app.get("/api/rooms/{room_id}/week")
async def get_room_week_events(
    room_id: int,
    start_date: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Get events for a room for the week."""
    calendar_service = CalendarService(db)

    room = await calendar_service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Parse start date or use today
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        start = datetime.now().date()

    # Get events for 7 days
    week_events = await calendar_service.get_events_for_week(room_id, start)

    return {
        "room": room,
        "week_events": week_events,
        "start_date": start.isoformat(),
        "server_time": datetime.now().isoformat(),
    }


@app.post("/api/rooms/{room_id}/book")
async def book_room(
    room_id: int,
    duration_minutes: int = 30,
    title: str = "Quick Booking",
    date: str = None,
    start_hour: int = None,
    start_minute: int = 0,
    booker_name: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Book a room for the specified duration on a specific date/time."""
    calendar_service = CalendarService(db)

    room = await calendar_service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Determine start time
    if date and start_hour is not None:
        # Booking for a specific date and time
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            start_time = datetime.combine(target_date, datetime.min.time().replace(hour=start_hour, minute=start_minute))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        # Booking for now
        start_time = datetime.now()

        # Check if room is currently available
        current_event = await calendar_service.get_current_event(room_id)
        if current_event:
            raise HTTPException(status_code=400, detail="Room is currently occupied")

    end_time = start_time + timedelta(minutes=duration_minutes)

    # Check for conflicts with existing events
    conflicts = await calendar_service.check_conflicts(room_id, start_time, end_time)
    if conflicts:
        raise HTTPException(
            status_code=400,
            detail=f"Conflicts with existing booking: {conflicts[0].get('title', 'Busy')}"
        )

    # Create the booking
    event = await calendar_service.create_event(
        room_id=room_id,
        title=title,
        start_time=start_time,
        end_time=end_time,
        booker_name=booker_name,
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


@app.delete("/api/rooms/{room_id}/events/{event_id}")
async def cancel_booking(room_id: int, event_id: str, db: AsyncSession = Depends(get_db)):
    """Cancel/delete a booking."""
    calendar_service = CalendarService(db)

    room = await calendar_service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    await calendar_service.delete_event(room_id=room_id, event_id=event_id)

    return {"success": True}


@app.post("/api/rooms/{room_id}/book-recurring")
async def book_recurring(
    room_id: int,
    title: str = "Recurring Booking",
    start_hour: int = 9,
    start_minute: int = 0,
    duration_minutes: int = 540,
    booker_name: str = None,
    recurring_days: str = "",
    recurring_start: str = None,
    recurring_end: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Create recurring bookings for specified days in a date range."""
    calendar_service = CalendarService(db)

    room = await calendar_service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Parse recurring days (comma-separated: "1,2,3" for Mon, Tue, Wed)
    try:
        days = [int(d.strip()) for d in recurring_days.split(",") if d.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recurring_days format")

    if not days:
        raise HTTPException(status_code=400, detail="At least one day must be selected")

    # Parse date range
    try:
        start_date = datetime.strptime(recurring_start, "%Y-%m-%d").date() if recurring_start else datetime.now().date()
        end_date = datetime.strptime(recurring_end, "%Y-%m-%d").date() if recurring_end else start_date + timedelta(days=90)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    # Create recurring events
    created_count, skipped_count = await calendar_service.create_recurring_events(
        room_id=room_id,
        title=title,
        start_hour=start_hour,
        start_minute=start_minute,
        duration_minutes=duration_minutes,
        booker_name=booker_name,
        days_of_week=days,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "success": True,
        "count": created_count,
        "skipped": skipped_count,
        "message": f"Created {created_count} bookings, skipped {skipped_count} due to conflicts"
    }


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
