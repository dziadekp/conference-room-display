# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Conference Room Calendar Display - a tablet-friendly web application for displaying and managing conference room schedules. Supports standalone local events or integration with Google/Microsoft 365 calendars.

Also includes **Digital Signage** feature for displaying promotional content (images, videos) on smart TVs in a continuous loop.

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

  **Digital Signage Routes:**
  - `/signage/{display_id}` - Full-screen signage display (for TVs)
  - `/api/signage` - GET: List all displays, POST: Create new display
  - `/api/signage/{display_id}` - DELETE: Remove display
  - `/api/signage/{display_id}/playlist` - GET: Get media items for display
  - `/api/signage/{display_id}/media` - POST: Upload media file (images, videos, PowerPoint - 50MB max)
  - `/api/signage/{display_id}/media/{media_id}` - DELETE: Remove media item
  - `/api/signage/{display_id}/media/{media_id}/move` - POST: Move item up/down in playlist
  - `/api/signage/{display_id}/reorder` - PUT: Bulk reorder all media items

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
- `SignageDisplay` - Digital signage display configuration (name, is_active)
- `MediaItem` - Media items for signage (filename, media_type, duration, order)

## Key Behaviors

- **Conflict Detection**: `CalendarService.check_conflicts()` prevents overlapping bookings
- **Full-Day Bookings**: Events 8+ hours are displayed as "Full Day" with special styling
- **Provider Fallback**: Rooms without calendar_provider use local SQLite storage
- **Token Refresh**: OAuth tokens auto-refresh on API calls when expired

### Digital Signage
- **Full-Screen Display**: `/signage/{display_id}` renders full-screen slideshow optimized for TVs
- **Media Support**: Images (JPG, PNG, GIF), videos (MP4, WebM), and PowerPoint (PPT, PPTX), max 50MB per file
- **PowerPoint Conversion**: PPT/PPTX files are automatically converted to images (one per slide) using LibreOffice
- **Playlist Ordering**: Up/down controls to reorder media items in the playlist sequence
- **Auto-Advance**: Images show for configurable duration, videos play to completion
- **Smooth Transitions**: 1-second fade transitions between media items
- **Audio Handling**: Videos muted by default (browser autoplay policy), click "Unmute" button to enable sound
- **Auto-Refresh Playlist**: Player checks for new content every 60 seconds
- **File Storage**: Uploaded media stored in `static/uploads/` with UUID-prefixed filenames

### PowerPoint Requirements (Server)
For PowerPoint conversion, the server needs:
```bash
# Ubuntu/Debian
sudo apt-get install libreoffice poppler-utils

# The app uses LibreOffice headless mode to convert PPT → PDF → Images
```

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

For digital signage: Open `/signage/{display_id}` on a smart TV browser. Use full-screen mode (F11) for best experience. Click "Click for Sound" button to enable audio on videos.

### Server Deployment (Linux)
The app runs on a Linux server (ptnminiserver) with these permanent URLs:

**Local Network Access (same network as server):**
- Calendar Display: `http://10.1.10.66:8000/display/1`
- Digital Signage: `http://10.1.10.66:8000/signage/1`
- Setup Page: `http://10.1.10.66:8000/setup`

**Tailscale Access (from any Tailscale device):**
- Calendar Display: `http://100.66.246.62:8000/display/1`
- Digital Signage: `http://100.66.246.62:8000/signage/1`
- Setup Page: `http://100.66.246.62:8000/setup`

These URLs are permanent as long as the server is running.

```bash
# SSH to server
ssh 100.66.246.62

# Service management
sudo systemctl status conference-room-display
sudo systemctl restart conference-room-display
sudo systemctl stop conference-room-display

# View logs
sudo journalctl -u conference-room-display -f

# Deploy updates
cd /home/dziadek_ptn/conference-room-display
git pull origin main
sudo systemctl restart conference-room-display
```
