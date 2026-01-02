"""
Unified calendar service for Google and Microsoft calendars.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from googleapiclient.discovery import build
import httpx

from database import Room, LocalEvent


class CalendarService:
    """Unified calendar service supporting multiple providers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Room Management ====================

    async def get_rooms(self) -> List[Dict[str, Any]]:
        """Get all configured rooms."""
        result = await self.db.execute(
            select(Room).where(Room.is_active == True).order_by(Room.name)
        )
        rooms = result.scalars().all()

        return [
            {
                "id": room.id,
                "name": room.name,
                "calendar_id": room.calendar_id,
                "calendar_provider": room.calendar_provider,
            }
            for room in rooms
        ]

    async def get_room(self, room_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific room."""
        result = await self.db.execute(
            select(Room).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()

        if not room:
            return None

        return {
            "id": room.id,
            "name": room.name,
            "calendar_id": room.calendar_id,
            "calendar_provider": room.calendar_provider,
        }

    async def create_room(
        self,
        name: str,
        calendar_id: str = None,
        calendar_provider: str = None,
    ) -> Dict[str, Any]:
        """Create a new room."""
        room = Room(
            name=name,
            calendar_id=calendar_id,
            calendar_provider=calendar_provider,
        )
        self.db.add(room)
        await self.db.commit()
        await self.db.refresh(room)

        return {
            "id": room.id,
            "name": room.name,
            "calendar_id": room.calendar_id,
            "calendar_provider": room.calendar_provider,
        }

    async def delete_room(self, room_id: int):
        """Delete a room."""
        result = await self.db.execute(
            select(Room).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()
        if room:
            await self.db.delete(room)
            await self.db.commit()

    # ==================== Event Retrieval ====================

    async def get_todays_events(self, room_id: int) -> List[Dict[str, Any]]:
        """Get all events for today."""
        room = await self.get_room(room_id)
        if not room:
            return []

        if room["calendar_provider"] == "google":
            return await self._get_google_events(room["calendar_id"])
        elif room["calendar_provider"] == "microsoft":
            return await self._get_microsoft_events(room["calendar_id"])
        else:
            return await self._get_local_events(room_id)

    async def get_current_event(self, room_id: int) -> Optional[Dict[str, Any]]:
        """Get the currently active event, if any."""
        events = await self.get_todays_events(room_id)
        now = datetime.now()

        for event in events:
            start = self._parse_datetime(event.get("start"))
            end = self._parse_datetime(event.get("end"))

            if start and end and start <= now <= end:
                return event

        return None

    async def get_next_event(self, room_id: int) -> Optional[Dict[str, Any]]:
        """Get the next upcoming event."""
        events = await self.get_todays_events(room_id)
        now = datetime.now()

        for event in events:
            start = self._parse_datetime(event.get("start"))
            if start and start > now:
                return event

        return None

    # ==================== Event Creation ====================

    async def create_event(
        self,
        room_id: int,
        title: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Create a new event."""
        room = await self.get_room(room_id)
        if not room:
            raise ValueError("Room not found")

        if room["calendar_provider"] == "google":
            return await self._create_google_event(
                room["calendar_id"], title, start_time, end_time
            )
        elif room["calendar_provider"] == "microsoft":
            return await self._create_microsoft_event(
                room["calendar_id"], title, start_time, end_time
            )
        else:
            return await self._create_local_event(
                room_id, title, start_time, end_time
            )

    async def extend_event(
        self,
        room_id: int,
        event_id: str,
        minutes: int,
    ) -> Dict[str, Any]:
        """Extend an event by the specified minutes."""
        room = await self.get_room(room_id)
        if not room:
            raise ValueError("Room not found")

        if room["calendar_provider"] == "google":
            return await self._extend_google_event(
                room["calendar_id"], event_id, minutes
            )
        elif room["calendar_provider"] == "microsoft":
            return await self._extend_microsoft_event(
                room["calendar_id"], event_id, minutes
            )
        else:
            return await self._extend_local_event(event_id, minutes)

    async def end_event(self, room_id: int, event_id: str):
        """End an event early (set end time to now)."""
        room = await self.get_room(room_id)
        if not room:
            raise ValueError("Room not found")

        if room["calendar_provider"] == "google":
            await self._end_google_event(room["calendar_id"], event_id)
        elif room["calendar_provider"] == "microsoft":
            await self._end_microsoft_event(room["calendar_id"], event_id)
        else:
            await self._end_local_event(event_id)

    # ==================== Google Calendar ====================

    async def _get_google_events(self, calendar_id: str) -> List[Dict[str, Any]]:
        """Get events from Google Calendar."""
        from auth.google import get_google_credentials

        credentials = await get_google_credentials(self.db)
        if not credentials:
            return []

        try:
            service = build("calendar", "v3", credentials=credentials)

            # Get today's date range
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)

            events_result = service.events().list(
                calendarId=calendar_id or "primary",
                timeMin=today.isoformat() + "Z",
                timeMax=tomorrow.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = events_result.get("items", [])

            return [
                {
                    "id": event["id"],
                    "title": event.get("summary", "Busy"),
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                    "organizer": event.get("organizer", {}).get("email", ""),
                    "provider": "google",
                }
                for event in events
            ]
        except Exception as e:
            print(f"Error fetching Google events: {e}")
            return []

    async def _create_google_event(
        self,
        calendar_id: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Create event in Google Calendar."""
        from auth.google import get_google_credentials

        credentials = await get_google_credentials(self.db)
        if not credentials:
            raise ValueError("Google Calendar not connected")

        service = build("calendar", "v3", credentials=credentials)

        event = {
            "summary": title,
            "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
        }

        result = service.events().insert(
            calendarId=calendar_id or "primary",
            body=event,
        ).execute()

        return {
            "id": result["id"],
            "title": result.get("summary"),
            "start": result["start"].get("dateTime"),
            "end": result["end"].get("dateTime"),
        }

    async def _extend_google_event(
        self,
        calendar_id: str,
        event_id: str,
        minutes: int,
    ) -> Dict[str, Any]:
        """Extend a Google Calendar event."""
        from auth.google import get_google_credentials

        credentials = await get_google_credentials(self.db)
        if not credentials:
            raise ValueError("Google Calendar not connected")

        service = build("calendar", "v3", credentials=credentials)

        # Get current event
        event = service.events().get(
            calendarId=calendar_id or "primary",
            eventId=event_id,
        ).execute()

        # Extend end time
        current_end = datetime.fromisoformat(
            event["end"]["dateTime"].replace("Z", "+00:00")
        )
        new_end = current_end + timedelta(minutes=minutes)

        event["end"]["dateTime"] = new_end.isoformat()

        result = service.events().update(
            calendarId=calendar_id or "primary",
            eventId=event_id,
            body=event,
        ).execute()

        return {
            "id": result["id"],
            "title": result.get("summary"),
            "start": result["start"].get("dateTime"),
            "end": result["end"].get("dateTime"),
        }

    async def _end_google_event(self, calendar_id: str, event_id: str):
        """End a Google Calendar event early."""
        from auth.google import get_google_credentials

        credentials = await get_google_credentials(self.db)
        if not credentials:
            raise ValueError("Google Calendar not connected")

        service = build("calendar", "v3", credentials=credentials)

        event = service.events().get(
            calendarId=calendar_id or "primary",
            eventId=event_id,
        ).execute()

        event["end"]["dateTime"] = datetime.utcnow().isoformat() + "Z"

        service.events().update(
            calendarId=calendar_id or "primary",
            eventId=event_id,
            body=event,
        ).execute()

    # ==================== Microsoft Calendar ====================

    async def _get_microsoft_events(self, calendar_id: str) -> List[Dict[str, Any]]:
        """Get events from Microsoft Calendar."""
        from auth.microsoft import get_microsoft_token

        token = await get_microsoft_token(self.db)
        if not token:
            return []

        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)

            # Use calendar_id if provided, otherwise use default calendar
            if calendar_id:
                url = f"https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events"
            else:
                url = "https://graph.microsoft.com/v1.0/me/calendar/events"

            params = {
                "$filter": f"start/dateTime ge '{today.isoformat()}' and start/dateTime lt '{tomorrow.isoformat()}'",
                "$orderby": "start/dateTime",
                "$top": 50,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )

                if response.status_code != 200:
                    print(f"Microsoft API error: {response.text}")
                    return []

                data = response.json()
                events = data.get("value", [])

                return [
                    {
                        "id": event["id"],
                        "title": event.get("subject", "Busy"),
                        "start": event["start"]["dateTime"],
                        "end": event["end"]["dateTime"],
                        "organizer": event.get("organizer", {}).get("emailAddress", {}).get("address", ""),
                        "provider": "microsoft",
                    }
                    for event in events
                ]

        except Exception as e:
            print(f"Error fetching Microsoft events: {e}")
            return []

    async def _create_microsoft_event(
        self,
        calendar_id: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Create event in Microsoft Calendar."""
        from auth.microsoft import get_microsoft_token

        token = await get_microsoft_token(self.db)
        if not token:
            raise ValueError("Microsoft Calendar not connected")

        if calendar_id:
            url = f"https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events"
        else:
            url = "https://graph.microsoft.com/v1.0/me/calendar/events"

        event = {
            "subject": title,
            "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=event,
            )

            if response.status_code not in (200, 201):
                raise ValueError(f"Failed to create event: {response.text}")

            result = response.json()

            return {
                "id": result["id"],
                "title": result.get("subject"),
                "start": result["start"]["dateTime"],
                "end": result["end"]["dateTime"],
            }

    async def _extend_microsoft_event(
        self,
        calendar_id: str,
        event_id: str,
        minutes: int,
    ) -> Dict[str, Any]:
        """Extend a Microsoft Calendar event."""
        from auth.microsoft import get_microsoft_token

        token = await get_microsoft_token(self.db)
        if not token:
            raise ValueError("Microsoft Calendar not connected")

        # Get current event
        if calendar_id:
            url = f"https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events/{event_id}"
        else:
            url = f"https://graph.microsoft.com/v1.0/me/calendar/events/{event_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code != 200:
                raise ValueError("Event not found")

            event = response.json()

            # Extend end time
            current_end = datetime.fromisoformat(event["end"]["dateTime"])
            new_end = current_end + timedelta(minutes=minutes)

            update_data = {
                "end": {"dateTime": new_end.isoformat(), "timeZone": "UTC"}
            }

            response = await client.patch(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=update_data,
            )

            if response.status_code != 200:
                raise ValueError(f"Failed to extend event: {response.text}")

            result = response.json()

            return {
                "id": result["id"],
                "title": result.get("subject"),
                "start": result["start"]["dateTime"],
                "end": result["end"]["dateTime"],
            }

    async def _end_microsoft_event(self, calendar_id: str, event_id: str):
        """End a Microsoft Calendar event early."""
        from auth.microsoft import get_microsoft_token

        token = await get_microsoft_token(self.db)
        if not token:
            raise ValueError("Microsoft Calendar not connected")

        if calendar_id:
            url = f"https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events/{event_id}"
        else:
            url = f"https://graph.microsoft.com/v1.0/me/calendar/events/{event_id}"

        update_data = {
            "end": {"dateTime": datetime.utcnow().isoformat(), "timeZone": "UTC"}
        }

        async with httpx.AsyncClient() as client:
            await client.patch(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=update_data,
            )

    # ==================== Local Events ====================

    async def _get_local_events(self, room_id: int) -> List[Dict[str, Any]]:
        """Get events from local database."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        result = await self.db.execute(
            select(LocalEvent).where(
                and_(
                    LocalEvent.room_id == room_id,
                    LocalEvent.start_time >= today,
                    LocalEvent.start_time < tomorrow,
                )
            ).order_by(LocalEvent.start_time)
        )

        events = result.scalars().all()

        return [
            {
                "id": str(event.id),
                "title": event.title,
                "start": event.start_time.isoformat(),
                "end": event.end_time.isoformat(),
                "organizer": event.organizer or "",
                "provider": "local",
            }
            for event in events
        ]

    async def _create_local_event(
        self,
        room_id: int,
        title: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Create a local event."""
        event = LocalEvent(
            room_id=room_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)

        return {
            "id": str(event.id),
            "title": event.title,
            "start": event.start_time.isoformat(),
            "end": event.end_time.isoformat(),
        }

    async def _extend_local_event(self, event_id: str, minutes: int) -> Dict[str, Any]:
        """Extend a local event."""
        result = await self.db.execute(
            select(LocalEvent).where(LocalEvent.id == int(event_id))
        )
        event = result.scalar_one_or_none()

        if not event:
            raise ValueError("Event not found")

        event.end_time = event.end_time + timedelta(minutes=minutes)
        await self.db.commit()

        return {
            "id": str(event.id),
            "title": event.title,
            "start": event.start_time.isoformat(),
            "end": event.end_time.isoformat(),
        }

    async def _end_local_event(self, event_id: str):
        """End a local event early."""
        result = await self.db.execute(
            select(LocalEvent).where(LocalEvent.id == int(event_id))
        )
        event = result.scalar_one_or_none()

        if event:
            event.end_time = datetime.now()
            await self.db.commit()

    # ==================== Helpers ====================

    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parse datetime string to datetime object."""
        if not dt_str:
            return None

        try:
            # Handle ISO format with timezone
            if "Z" in dt_str:
                dt_str = dt_str.replace("Z", "+00:00")
            if "+" in dt_str or dt_str.count("-") > 2:
                return datetime.fromisoformat(dt_str).replace(tzinfo=None)
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None
