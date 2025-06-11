"""
Google Calendar API service for managing calendar events
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import pytz
from dateutil import parser as date_parser

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import aiohttp

from services.google_oauth import google_oauth
from services.database import AsyncSessionLocal, Event, UserSettings
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET


class GoogleCalendarService:
    """Handle Google Calendar API operations"""
    
    def __init__(self):
        self.client_id = GOOGLE_CLIENT_ID
        self.client_secret = GOOGLE_CLIENT_SECRET
        
        # Cache for calendar services to avoid recreating
        self._service_cache = {}
        self._rate_limit_delay = 1  # Start with 1 second delay
        self._max_retry_attempts = 3
    
    async def _get_calendar_service(self, user_id: int):
        """Get authenticated Calendar API service for user"""
        if user_id in self._service_cache:
            return self._service_cache[user_id]
        
        # Get access token
        access_token = await google_oauth.get_access_token(user_id)
        if not access_token:
            raise ValueError("User not authenticated with Google Calendar")
        
        # Create credentials
        credentials = Credentials(
            token=access_token,
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        # Build service
        service = build('calendar', 'v3', credentials=credentials)
        
        # Cache the service (but not for too long due to token expiry)
        self._service_cache[user_id] = service
        
        # Clear cache after 30 minutes
        async def clear_cache():
            await asyncio.sleep(1800)  # 30 minutes
            self._service_cache.pop(user_id, None)
        
        asyncio.create_task(clear_cache())
        
        return service
    
    async def _handle_api_call(self, api_call, max_retries: int = None):
        """Handle API call with rate limiting and retry logic"""
        if max_retries is None:
            max_retries = self._max_retry_attempts
        
        for attempt in range(max_retries):
            try:
                # Add delay for rate limiting
                if attempt > 0:
                    await asyncio.sleep(self._rate_limit_delay * (2 ** attempt))
                
                # Execute API call
                result = api_call.execute()
                
                # Reset rate limit delay on success
                self._rate_limit_delay = max(1, self._rate_limit_delay * 0.9)
                
                return result
            
            except HttpError as e:
                if e.resp.status == 429:  # Rate limited
                    self._rate_limit_delay = min(60, self._rate_limit_delay * 2)
                    if attempt < max_retries - 1:
                        print(f"Rate limited, retrying in {self._rate_limit_delay} seconds...")
                        continue
                elif e.resp.status == 401:  # Unauthorized
                    # Clear cached service and raise auth error
                    user_id = getattr(api_call, '_user_id', None)
                    if user_id:
                        self._service_cache.pop(user_id, None)
                    raise ValueError("Authentication expired. Please reconnect your calendar.")
                elif e.resp.status >= 500:  # Server error
                    if attempt < max_retries - 1:
                        print(f"Server error {e.resp.status}, retrying...")
                        continue
                
                # Re-raise for other errors
                raise e
            
            except RefreshError:
                # Token refresh failed
                raise ValueError("Authentication expired. Please reconnect your calendar.")
        
        raise Exception(f"API call failed after {max_retries} attempts")
    
    async def get_user_calendars(self, user_id: int) -> List[Dict[str, Any]]:
        """Get list of user's calendars"""
        try:
            service = await self._get_calendar_service(user_id)
            
            calendar_list_call = service.calendarList().list()
            calendar_list_call._user_id = user_id  # For error handling
            
            result = await self._handle_api_call(calendar_list_call)
            
            calendars = []
            for calendar_item in result.get('items', []):
                calendars.append({
                    'id': calendar_item.get('id'),
                    'summary': calendar_item.get('summary'),
                    'primary': calendar_item.get('primary', False),
                    'access_role': calendar_item.get('accessRole'),
                    'timezone': calendar_item.get('timeZone')
                })
            
            return calendars
        
        except Exception as e:
            print(f"Error getting calendars for user {user_id}: {e}")
            return []
    
    async def get_primary_calendar_id(self, user_id: int) -> Optional[str]:
        """Get user's primary calendar ID"""
        try:
            calendars = await self.get_user_calendars(user_id)
            
            # Find primary calendar
            for calendar in calendars:
                if calendar.get('primary'):
                    return calendar['id']
            
            # If no primary found, return first calendar
            if calendars:
                return calendars[0]['id']
            
            return None
        
        except Exception as e:
            print(f"Error getting primary calendar for user {user_id}: {e}")
            return None
    
    def _format_datetime_for_api(self, dt: datetime, timezone: str = 'UTC') -> Dict[str, str]:
        """Format datetime for Google Calendar API"""
        if dt.tzinfo is None:
            # Assume UTC if no timezone info
            dt = pytz.UTC.localize(dt)
        
        return {
            'dateTime': dt.isoformat(),
            'timeZone': timezone
        }
    
    def _parse_event_datetime(self, event_datetime: str, default_timezone: str = 'UTC') -> datetime:
        """Parse datetime string from event with timezone handling"""
        try:
            # Try parsing with dateutil
            dt = date_parser.parse(event_datetime)
            
            # If no timezone info, assume the default timezone
            if dt.tzinfo is None:
                tz = pytz.timezone(default_timezone)
                dt = tz.localize(dt)
            
            return dt
        
        except Exception as e:
            print(f"Error parsing datetime '{event_datetime}': {e}")
            # Return current time as fallback
            return datetime.now(pytz.UTC)
    
    async def create_calendar_event(
        self, 
        user_id: int, 
        event_data: Dict[str, Any],
        calendar_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Create event in Google Calendar
        Returns: event_id if successful, None otherwise
        """
        try:
            service = await self._get_calendar_service(user_id)
            
            # Get calendar ID
            if not calendar_id:
                calendar_id = await self.get_primary_calendar_id(user_id)
            
            if not calendar_id:
                raise ValueError("No calendar available for user")
            
            # Get user timezone
            async with AsyncSessionLocal() as session:
                user_settings = await session.get(UserSettings, user_id)
                user_timezone = 'UTC'  # Default timezone
                
                if user_settings and user_settings.calendar_id:
                    # Try to get timezone from calendar settings
                    calendars = await self.get_user_calendars(user_id)
                    for cal in calendars:
                        if cal['id'] == user_settings.calendar_id:
                            user_timezone = cal.get('timezone', 'UTC')
                            break
            
            # Parse event times
            start_time = self._parse_event_datetime(
                event_data.get('start_datetime'), 
                user_timezone
            )
            
            end_time = None
            if event_data.get('end_datetime'):
                end_time = self._parse_event_datetime(
                    event_data.get('end_datetime'), 
                    user_timezone
                )
            else:
                # Default 1 hour duration
                end_time = start_time + timedelta(hours=1)
            
            # Build event body
            event_body = {
                'summary': event_data.get('title', 'Captured Event'),
                'description': self._build_event_description(event_data),
                'start': self._format_datetime_for_api(start_time, user_timezone),
                'end': self._format_datetime_for_api(end_time, user_timezone),
            }
            
            # Add location if available
            if event_data.get('location'):
                event_body['location'] = event_data['location']
            
            # Add attendees if available
            if event_data.get('participants'):
                attendees = []
                for participant in event_data['participants']:
                    # Simple email detection
                    if '@' in participant:
                        attendees.append({'email': participant})
                    else:
                        # Store as display name (Google will handle properly)
                        attendees.append({'displayName': participant})
                
                if attendees:
                    event_body['attendees'] = attendees
            
            # Create event
            create_call = service.events().insert(calendarId=calendar_id, body=event_body)
            create_call._user_id = user_id
            
            result = await self._handle_api_call(create_call)
            
            event_id = result.get('id')
            print(f"Created calendar event {event_id} for user {user_id}")
            
            return event_id
        
        except Exception as e:
            print(f"Error creating calendar event for user {user_id}: {e}")
            return None
    
    def _build_event_description(self, event_data: Dict[str, Any]) -> str:
        """Build event description from extracted event data"""
        description_parts = []
        
        # Add event type and priority
        event_type = event_data.get('event_type', 'event')
        priority = event_data.get('priority', 'medium')
        
        description_parts.append(f"📝 Тип: {event_type.title()}")
        description_parts.append(f"⭐ Приоритет: {priority}")
        
        # Add action items if available
        action_items = event_data.get('action_items', [])
        if action_items:
            description_parts.append("\n📋 Действия:")
            for i, item in enumerate(action_items, 1):
                description_parts.append(f"  {i}. {item}")
        
        # Add participants info
        participants = event_data.get('participants', [])
        if participants:
            description_parts.append(f"\n👥 Участники: {', '.join(participants)}")
        
        # Add session info
        session_id = event_data.get('session_id')
        if session_id:
            description_parts.append(f"\n🔗 Из сессии захвата: #{session_id}")
        
        description_parts.append("\n�� Создано Briefly")
        
        return '\n'.join(description_parts)
    
    async def check_calendar_conflicts(
        self, 
        user_id: int, 
        start_time: datetime, 
        end_time: datetime,
        calendar_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Check for calendar conflicts in the specified time range"""
        try:
            service = await self._get_calendar_service(user_id)
            
            if not calendar_id:
                calendar_id = await self.get_primary_calendar_id(user_id)
            
            if not calendar_id:
                return []
            
            # Query events in time range
            events_call = service.events().list(
                calendarId=calendar_id,
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            )
            events_call._user_id = user_id
            
            result = await self._handle_api_call(events_call)
            
            conflicts = []
            for event in result.get('items', []):
                event_start = event.get('start', {})
                event_end = event.get('end', {})
                
                conflicts.append({
                    'id': event.get('id'),
                    'summary': event.get('summary', 'Без названия'),
                    'start': event_start.get('dateTime', event_start.get('date')),
                    'end': event_end.get('dateTime', event_end.get('date'))
                })
            
            return conflicts
        
        except Exception as e:
            print(f"Error checking conflicts for user {user_id}: {e}")
            return []
    
    async def update_calendar_event(
        self, 
        user_id: int, 
        event_id: str,
        event_data: Dict[str, Any],
        calendar_id: Optional[str] = None
    ) -> bool:
        """Update existing calendar event"""
        try:
            service = await self._get_calendar_service(user_id)
            
            if not calendar_id:
                calendar_id = await self.get_primary_calendar_id(user_id)
            
            if not calendar_id:
                return False
            
            # Get existing event
            get_call = service.events().get(calendarId=calendar_id, eventId=event_id)
            get_call._user_id = user_id
            
            existing_event = await self._handle_api_call(get_call)
            
            # Update event fields
            if 'title' in event_data:
                existing_event['summary'] = event_data['title']
            
            if 'location' in event_data:
                existing_event['location'] = event_data['location']
            
            # Update description
            existing_event['description'] = self._build_event_description(event_data)
            
            # Update event
            update_call = service.events().update(
                calendarId=calendar_id, 
                eventId=event_id, 
                body=existing_event
            )
            update_call._user_id = user_id
            
            await self._handle_api_call(update_call)
            
            print(f"Updated calendar event {event_id} for user {user_id}")
            return True
        
        except Exception as e:
            print(f"Error updating calendar event {event_id} for user {user_id}: {e}")
            return False
    
    async def delete_calendar_event(
        self, 
        user_id: int, 
        event_id: str,
        calendar_id: Optional[str] = None
    ) -> bool:
        """Delete calendar event"""
        try:
            service = await self._get_calendar_service(user_id)
            
            if not calendar_id:
                calendar_id = await self.get_primary_calendar_id(user_id)
            
            if not calendar_id:
                return False
            
            # Delete event
            delete_call = service.events().delete(calendarId=calendar_id, eventId=event_id)
            delete_call._user_id = user_id
            
            await self._handle_api_call(delete_call)
            
            print(f"Deleted calendar event {event_id} for user {user_id}")
            return True
        
        except Exception as e:
            print(f"Error deleting calendar event {event_id} for user {user_id}: {e}")
            return False
    
    async def sync_session_events_to_calendar(self, user_id: int, session_id: int) -> Dict[str, Any]:
        """
        Sync all events from a capture session to Google Calendar
        Returns: sync results with created/failed events
        """
        try:
            # Check if user has calendar connected
            is_connected = await google_oauth.check_user_connected(user_id)
            if not is_connected:
                return {
                    'success': False,
                    'error': 'Google Calendar not connected',
                    'created_events': [],
                    'failed_events': []
                }
            
            # Get session events from database
            from services.database import get_session_events
            events = await get_session_events(session_id)
            
            if not events:
                return {
                    'success': True,
                    'message': 'No events to sync',
                    'created_events': [],
                    'failed_events': []
                }
            
            created_events = []
            failed_events = []
            
            for event in events:
                # Convert Event model to dict for API
                event_data = {
                    'title': event.title,
                    'event_type': event.event_type,
                    'priority': event.priority,
                    'start_datetime': event.start_datetime.isoformat() if event.start_datetime else None,
                    'end_datetime': event.end_datetime.isoformat() if event.end_datetime else None,
                    'location': event.location,
                    'participants': event.participants or [],
                    'action_items': event.action_items or [],
                    'session_id': session_id
                }
                
                # Create calendar event
                calendar_event_id = await self.create_calendar_event(user_id, event_data)
                
                if calendar_event_id:
                    # Update database with calendar event ID
                    async with AsyncSessionLocal() as db_session:
                        db_event = await db_session.get(Event, event.id)
                        if db_event:
                            db_event.calendar_event_id = calendar_event_id
                            await db_session.commit()
                    
                    created_events.append({
                        'event_id': event.id,
                        'title': event.title,
                        'calendar_event_id': calendar_event_id
                    })
                else:
                    failed_events.append({
                        'event_id': event.id,
                        'title': event.title,
                        'error': 'Failed to create calendar event'
                    })
            
            return {
                'success': True,
                'created_events': created_events,
                'failed_events': failed_events,
                'total_events': len(events),
                'created_count': len(created_events),
                'failed_count': len(failed_events)
            }
        
        except Exception as e:
            print(f"Error syncing session {session_id} events for user {user_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'created_events': [],
                'failed_events': []
            }


# Global instance
google_calendar = GoogleCalendarService() 