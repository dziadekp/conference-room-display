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

    async def get_events_for_date(self, room_id: int, target_date: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Get all events for a specific date."""
        if target_date is None:
            target_date = datetime.now().date()

        room = await self.get_room(room_id)
        if not room:
            return []

        if room["calendar_provider"] == "google":
            return await self._get_google_events(room["calendar_id"], target_date)
        elif room["calendar_provider"] == "microsoft":
            return await self._get_microsoft_events(room["calendar_id"], target_date)
        else:
            return await self._get_local_events(room_id, target_date)

    async def get_events_for_week(self, room_id: int, start_date: Any = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get events for a full week starting from start_date."""
        if start_date is None:
            start_date = datetime.now().date()

        week_events = {}
        for i in range(7):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.isoformat()
            week_events[date_str] = await self.get_events_for_date(room_id, current_date)

        return week_events

    async def check_conflicts(self, room_id: int, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Check if a time range conflicts with existing events."""
        target_date = start_time.date()
        events = await self.get_events_for_date(room_id, target_date)

        conflicts = []
        for event in events:
            event_start = self._parse_datetime(event.get("start"))
            event_end = self._parse_datetime(event.get("end"))

            if event_start and event_end:
                # Check for overlap
                if start_time < event_end and end_time > event_start:
                    conflicts.append(event)

        return conflicts

    # ==================== Event Creation ====================

    async def create_event(
        self,
        room_id: int,
        title: str,
        start_time: datetime,
        end_time: datetime,
        booker_name: str = None,
    ) -> Dict[str, Any]:
        """Create a new event."""
        room = await self.get_room(room_id)
        if not room:
            raise ValueError("Room not found")

        if room["calendar_provider"] == "google":
            return await self._create_google_event(
                room["calendar_id"], title, start_time, end_time, booker_name
            )
        elif room["calendar_provider"] == "microsoft":
            return await self._create_microsoft_event(
                room["calendar_id"], title, start_time, end_time, booker_name
            )
        else:
            return await self._create_local_event(
                room_id, title, start_time, end_time, booker_name
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

    async def delete_event(self, room_id: int, event_id: str):
        """Delete/cancel an event."""
        room = await self.get_room(room_id)
        if not room:
            raise ValueError("Room not found")

        if room["calendar_provider"] == "google":
            await self._delete_google_event(room["calendar_id"], event_id)
        elif room["calendar_provider"] == "microsoft":
            await self._delete_microsoft_event(room["calendar_id"], event_id)
        else:
            await self._delete_local_event(event_id)

    # ==================== Google Calendar ====================

    async def _get_google_events(self, calendar_id: str, target_date: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Get events from Google Calendar."""
        from auth.google import get_google_credentials

        credentials = await get_google_credentials(self.db)
        if not credentials:
            return []

        try:
            service = build("calendar", "v3", credentials=credentials)

            # Get date range for target date
            if target_date is None:
                target_date = datetime.now().date()
            day_start = datetime.combine(target_date, datetime.min.time())
            day_end = day_start + timedelta(days=1)

            events_result = service.events().list(
                calendarId=calendar_id or "primary",
                timeMin=day_start.isoformat() + "Z",
                timeMax=day_end.isoformat() + "Z",
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
        booker_name: str = None,
    ) -> Dict[str, Any]:
        """Create event in Google Calendar."""
        from auth.google import get_google_credentials

        credentials = await get_google_credentials(self.db)
        if not credentials:
            raise ValueError("Google Calendar not connected")

        service = build("calendar", "v3", credentials=credentials)

        # Add booker name to title or description
        display_title = f"{title} - {booker_name}" if booker_name else title

        event = {
            "summary": display_title,
            "description": f"Booked by: {booker_name}" if booker_name else "",
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

    async def _delete_google_event(self, calendar_id: str, event_id: str):
        """Delete a Google Calendar event."""
        from auth.google import get_google_credentials

        credentials = await get_google_credentials(self.db)
        if not credentials:
            raise ValueError("Google Calendar not connected")

        service = build("calendar", "v3", credentials=credentials)

        service.events().delete(
            calendarId=calendar_id or "primary",
            eventId=event_id,
        ).execute()

    # ==================== Microsoft Calendar ====================

    async def _get_microsoft_events(self, calendar_id: str, target_date: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Get events from Microsoft Calendar."""
        from auth.microsoft import get_microsoft_token

        token = await get_microsoft_token(self.db)
        if not token:
            return []

        try:
            # Get date range for target date
            if target_date is None:
                target_date = datetime.now().date()
            day_start = datetime.combine(target_date, datetime.min.time())
            day_end = day_start + timedelta(days=1)

            # Use calendar_id if provided, otherwise use default calendar
            if calendar_id:
                url = f"https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events"
            else:
                url = "https://graph.microsoft.com/v1.0/me/calendar/events"

            params = {
                "$filter": f"start/dateTime ge '{day_start.isoformat()}' and start/dateTime lt '{day_end.isoformat()}'",
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
        booker_name: str = None,
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

        # Add booker name to title or body
        display_title = f"{title} - {booker_name}" if booker_name else title

        event = {
            "subject": display_title,
            "body": {"contentType": "text", "content": f"Booked by: {booker_name}" if booker_name else ""},
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

    async def _delete_microsoft_event(self, calendar_id: str, event_id: str):
        """Delete a Microsoft Calendar event."""
        from auth.microsoft import get_microsoft_token

        token = await get_microsoft_token(self.db)
        if not token:
            raise ValueError("Microsoft Calendar not connected")

        if calendar_id:
            url = f"https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events/{event_id}"
        else:
            url = f"https://graph.microsoft.com/v1.0/me/calendar/events/{event_id}"

        async with httpx.AsyncClient() as client:
            await client.delete(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )

    # ==================== Local Events ====================

    async def _get_local_events(self, room_id: int, target_date: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Get events from local database."""
        if target_date is None:
            target_date = datetime.now().date()
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        result = await self.db.execute(
            select(LocalEvent).where(
                and_(
                    LocalEvent.room_id == room_id,
                    LocalEvent.start_time >= day_start,
                    LocalEvent.start_time < day_end,
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
        booker_name: str = None,
    ) -> Dict[str, Any]:
        """Create a local event."""
        event = LocalEvent(
            room_id=room_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            organizer=booker_name,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)

        return {
            "id": str(event.id),
            "title": event.title,
            "start": event.start_time.isoformat(),
            "end": event.end_time.isoformat(),
            "organizer": event.organizer or "",
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

    async def _delete_local_event(self, event_id: str):
        """Delete a local event."""
        result = await self.db.execute(
            select(LocalEvent).where(LocalEvent.id == int(event_id))
        )
        event = result.scalar_one_or_none()

        if event:
            await self.db.delete(event)
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
