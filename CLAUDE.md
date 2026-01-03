# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Conference Room Calendar Display - a tablet-friendly web application for displaying and managing conference room schedules. Supports standalone local events or integration with Google/Microsoft 365 calendars.

## Development Commands

```bash
# Start development server (uses venv Python)
./venv/bin/python main.py

# Or with uvicorn directly
./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Install dependencies
pip install -r requirements.txt

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
```

## Architecture

### Backend (FastAPI + SQLAlchemy Async)
- **main.py** - FastAPI application with all API routes
  - `/` - Room list homepage
  - `/display/{room_id}` - Tablet display view for a room
  - `/setup` - Admin setup page
  - `/api/rooms/{room_id}/events` - Day events with current/next event detection
  - `/api/rooms/{room_id}/week` - Week view events
  - `/api/rooms/{room_id}/month` - Month calendar grid events
  - `/api/rooms/{room_id}/book` - Create booking with conflict detection
  - `/api/rooms/{room_id}/book-recurring` - Create recurring bookings

### Calendar Provider Pattern
The `CalendarService` class (`services/calendar.py`) uses a provider abstraction:
- Checks `room.calendar_provider` to route to Google, Microsoft, or local storage
- Each operation has three implementations: `_*_google_*`, `_*_microsoft_*`, `_*_local_*`
- Local events stored in SQLite, external calendars use OAuth tokens

### OAuth Flow
- `auth/google.py` - Google Calendar OAuth using `google-auth-oauthlib`
- `auth/microsoft.py` - Microsoft 365 OAuth using `msal`
- Tokens stored in `CalendarToken` table, auto-refresh on expiry

### Frontend (Vanilla JS)
- **static/js/app.js** - `ConferenceRoomDisplay` class handles all UI
  - Day/Week/Month view rendering
  - Quick book buttons (15min, 30min, 1hr, Full Day)
  - Meeting actions (Extend, End Now)
  - Booking modal with conflict prevention
  - Auto-refresh every 30 seconds

### Database Models
- `Room` - Conference room configuration (name, calendar_id, provider)
- `CalendarToken` - OAuth tokens for Google/Microsoft
- `LocalEvent` - Events for rooms without external calendar

## Key Behaviors

- **Conflict Detection**: `CalendarService.check_conflicts()` prevents overlapping bookings
- **Full-Day Bookings**: Events 8+ hours are displayed as "Full Day" with special styling
- **Provider Fallback**: Rooms without calendar_provider use local SQLite storage
- **Token Refresh**: OAuth tokens auto-refresh on API calls when expired

## Environment Variables

```bash
PORT=8000                      # Server port
DEBUG=false                    # Enable uvicorn reload
DATABASE_URL=                  # Optional: PostgreSQL URL (defaults to SQLite)
GOOGLE_CLIENT_ID=              # Google OAuth
GOOGLE_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=           # Microsoft OAuth
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT_ID=common     # 'common' for multi-tenant
```

## Deployment

The app is designed for self-hosting. Uses SQLite by default (zero-config), or PostgreSQL for production. See `render.yaml` for Render deployment blueprint.

For tablet display: Open `/display/{room_id}` in Safari/Chrome and enable kiosk mode or Guided Access.
