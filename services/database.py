"""
Database models and setup for Telegram bot capture sessions
"""
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, create_engine, select, desc, func, or_, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class CaptureSession(Base):
    """Model for storing conversation capture sessions"""
    __tablename__ = 'capture_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    messages = Column(JSON, nullable=False, default=list)  # List of message texts
    summary = Column(Text, nullable=True)
    extracted_events = Column(JSON, nullable=True, default=list)  # List of extracted events
    status = Column(String(20), nullable=False, default='active')  # active, completed, failed
    
    def add_message(self, message_text: str):
        """Add a message to the session"""
        if self.messages is None:
            self.messages = []
        self.messages.append({
            'text': message_text,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def get_full_text(self) -> str:
        """Get all messages as a single text"""
        if not self.messages:
            return ""
        return "\n".join([msg['text'] for msg in self.messages])


class Event(Base):
    """Model for extracted events from conversations"""
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    event_type = Column(String(50), nullable=False, default='event')  # meeting, deadline, task, appointment, reminder
    priority = Column(String(10), nullable=False, default='medium')  # high, medium, low
    start_datetime = Column(DateTime, nullable=True)
    end_datetime = Column(DateTime, nullable=True)
    location = Column(String(255), nullable=True)
    participants = Column(JSON, nullable=True, default=list)  # List of participant names
    action_items = Column(JSON, nullable=True, default=list)  # List of action items
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    calendar_event_id = Column(String(255), nullable=True)  # Google Calendar event ID


class UserSettings(Base):
    """Model for user preferences and settings"""
    __tablename__ = 'user_settings'
    
    user_id = Column(Integer, primary_key=True)
    auto_create_events = Column(Boolean, nullable=False, default=False)
    google_calendar_connected = Column(Boolean, nullable=False, default=False)
    calendar_id = Column(String(255), nullable=True)
    google_refresh_token = Column(Text, nullable=True)  # Encrypted refresh token
    language = Column(String(10), nullable=False, default='auto')
    summary_style = Column(String(20), nullable=False, default='default')
    
    # New settings for enhanced functionality
    notifications_enabled = Column(Boolean, nullable=False, default=True)
    event_notifications = Column(Boolean, nullable=False, default=True)
    session_notifications = Column(Boolean, nullable=False, default=True)
    error_notifications = Column(Boolean, nullable=False, default=True)
    data_retention_days = Column(Integer, nullable=False, default=30)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# Database setup
DATABASE_URL = "sqlite+aiosqlite:///./bot_data.db"

# Create async engine
async_engine = create_async_engine(DATABASE_URL, echo=False)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def init_database():
    """Initialize database and create tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncSession:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Database helper functions
async def get_user_settings(user_id: int) -> Optional[UserSettings]:
    """Get user settings or create default ones"""
    async with AsyncSessionLocal() as session:
        result = await session.get(UserSettings, user_id)
        if not result:
            # Create default settings
            result = UserSettings(user_id=user_id)
            session.add(result)
            await session.commit()
            await session.refresh(result)
        return result


async def get_active_session(user_id: int) -> Optional[CaptureSession]:
    """Get active capture session for user"""
    async with AsyncSessionLocal() as session:
        stmt = select(CaptureSession).where(
            CaptureSession.user_id == user_id,
            CaptureSession.status == 'active'
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def create_capture_session(user_id: int) -> CaptureSession:
    """Create new capture session"""
    async with AsyncSessionLocal() as session:
        capture_session = CaptureSession(user_id=user_id)
        session.add(capture_session)
        await session.commit()
        await session.refresh(capture_session)
        return capture_session


async def get_user_sessions(user_id: int, limit: int = 10, offset: int = 0) -> List[CaptureSession]:
    """Get user's capture sessions history"""
    async with AsyncSessionLocal() as session:
        stmt = select(CaptureSession).where(
            CaptureSession.user_id == user_id,
            CaptureSession.status == 'completed'
        ).order_by(desc(CaptureSession.end_time)).limit(limit).offset(offset)
        
        result = await session.execute(stmt)
        return result.scalars().all()


async def get_user_sessions_paginated(
    user_id: int, 
    page: int = 1, 
    per_page: int = 10, 
    status_filter: Optional[str] = None,
    search_query: Optional[str] = None
) -> tuple[List[CaptureSession], int]:
    """
    Get user's capture sessions with pagination and filtering
    Returns (sessions, total_count)
    """
    async with AsyncSessionLocal() as session:
        # Base query
        base_stmt = select(CaptureSession).where(CaptureSession.user_id == user_id)
        count_stmt = select(func.count(CaptureSession.id)).where(CaptureSession.user_id == user_id)
        
        # Apply status filter
        if status_filter:
            base_stmt = base_stmt.where(CaptureSession.status == status_filter)
            count_stmt = count_stmt.where(CaptureSession.status == status_filter)
        
        # Apply search filter (search in summary or message content)
        if search_query:
            search_filter = or_(
                CaptureSession.summary.contains(search_query),
                func.json_extract(CaptureSession.messages, '$').contains(search_query)
            )
            base_stmt = base_stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)
        
        # Get total count
        total_result = await session.execute(count_stmt)
        total_count = total_result.scalar()
        
        # Apply pagination and ordering
        offset = (page - 1) * per_page
        sessions_stmt = base_stmt.order_by(desc(CaptureSession.end_time)).limit(per_page).offset(offset)
        
        # Execute query
        sessions_result = await session.execute(sessions_stmt)
        sessions = sessions_result.scalars().all()
        
        return list(sessions), total_count


async def get_session_events(session_id: int) -> List['Event']:
    """Get all events for a specific session"""
    async with AsyncSessionLocal() as session:
        stmt = select(Event).where(Event.session_id == session_id).order_by(Event.start_datetime)
        result = await session.execute(stmt)
        return result.scalars().all()


async def get_user_stats(user_id: int) -> dict:
    """Get user statistics for sessions and events"""
    async with AsyncSessionLocal() as session:
        # Session stats
        session_count_stmt = select(func.count(CaptureSession.id)).where(
            CaptureSession.user_id == user_id,
            CaptureSession.status == 'completed'
        )
        session_count_result = await session.execute(session_count_stmt)
        total_sessions = session_count_result.scalar() or 0
        
        # Event stats
        event_count_stmt = select(func.count(Event.id)).where(Event.user_id == user_id)
        event_count_result = await session.execute(event_count_stmt)
        total_events = event_count_result.scalar() or 0
        
        # Recent session
        recent_session_stmt = select(CaptureSession).where(
            CaptureSession.user_id == user_id,
            CaptureSession.status == 'completed'
        ).order_by(desc(CaptureSession.end_time)).limit(1)
        recent_session_result = await session.execute(recent_session_stmt)
        recent_session = recent_session_result.scalar_one_or_none()
        
        return {
            'total_sessions': total_sessions,
            'total_events': total_events,
            'recent_session': recent_session
        }


async def cleanup_old_sessions(days_to_keep: int = 30) -> int:
    """
    Clean up old sessions based on data retention policy
    Returns number of deleted sessions
    """
    async with AsyncSessionLocal() as session:
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # First get count of sessions to delete
        count_stmt = select(func.count(CaptureSession.id)).where(
            CaptureSession.end_time < cutoff_date,
            CaptureSession.status == 'completed'
        )
        count_result = await session.execute(count_stmt)
        delete_count = count_result.scalar() or 0
        
        if delete_count > 0:
            # Delete old events first (foreign key constraint)
            old_sessions_stmt = select(CaptureSession.id).where(
                CaptureSession.end_time < cutoff_date,
                CaptureSession.status == 'completed'
            )
            old_sessions_result = await session.execute(old_sessions_stmt)
            old_session_ids = [row[0] for row in old_sessions_result.fetchall()]
            
            if old_session_ids:
                # Delete events
                events_delete_stmt = delete(Event).where(Event.session_id.in_(old_session_ids))
                await session.execute(events_delete_stmt)
                
                # Delete sessions
                sessions_delete_stmt = delete(CaptureSession).where(
                    CaptureSession.end_time < cutoff_date,
                    CaptureSession.status == 'completed'
                )
                await session.execute(sessions_delete_stmt)
                
                await session.commit()
        
        return delete_count


# Scheduled cleanup service
async def run_data_retention_cleanup():
    """
    Background task for data retention - clean up old sessions periodically
    This should be called by a scheduler (e.g., daily cron job)
    """
    try:
        deleted_count = await cleanup_old_sessions(days_to_keep=30)
        if deleted_count > 0:
            print(f"Data retention cleanup: Deleted {deleted_count} old sessions")
        return deleted_count
    except Exception as e:
        print(f"Error during data retention cleanup: {e}")
        return 0


# Session caching helper (simple in-memory cache)
_session_cache = {}
CACHE_TTL = 300  # 5 minutes

async def get_cached_user_stats(user_id: int) -> dict:
    """Get user stats with simple caching"""
    cache_key = f"stats_{user_id}"
    current_time = datetime.utcnow().timestamp()
    
    # Check cache
    if cache_key in _session_cache:
        cached_data, timestamp = _session_cache[cache_key]
        if current_time - timestamp < CACHE_TTL:
            return cached_data
    
    # Get fresh data
    stats = await get_user_stats(user_id)
    _session_cache[cache_key] = (stats, current_time)
    
    return stats


def clear_user_cache(user_id: Optional[int] = None):
    """Clear user cache - call after major session changes"""
    if user_id:
        cache_key = f"stats_{user_id}"
        _session_cache.pop(cache_key, None)
    else:
        _session_cache.clear()


async def update_user_setting(user_id: int, setting_name: str, value: any) -> bool:
    """Update a specific user setting"""
    try:
        async with AsyncSessionLocal() as session:
            settings = await session.get(UserSettings, user_id)
            if not settings:
                settings = UserSettings(user_id=user_id)
                session.add(settings)
            
            # Update the specific setting
            if hasattr(settings, setting_name):
                setattr(settings, setting_name, value)
                settings.updated_at = datetime.utcnow()
                await session.commit()
                return True
            else:
                print(f"Invalid setting name: {setting_name}")
                return False
    except Exception as e:
        print(f"Error updating user setting {setting_name} for user {user_id}: {e}")
        return False


async def get_user_setting(user_id: int, setting_name: str, default_value: any = None) -> any:
    """Get a specific user setting"""
    try:
        async with AsyncSessionLocal() as session:
            settings = await session.get(UserSettings, user_id)
            if settings and hasattr(settings, setting_name):
                return getattr(settings, setting_name)
            return default_value
    except Exception as e:
        print(f"Error getting user setting {setting_name} for user {user_id}: {e}")
        return default_value


async def disconnect_user_calendar(user_id: int) -> bool:
    """Disconnect user's Google Calendar and clear related data"""
    try:
        async with AsyncSessionLocal() as session:
            settings = await session.get(UserSettings, user_id)
            if settings:
                settings.google_calendar_connected = False
                settings.calendar_id = None
                settings.google_refresh_token = None
                settings.auto_create_events = False
                settings.updated_at = datetime.utcnow()
                await session.commit()
                return True
            return False
    except Exception as e:
        print(f"Error disconnecting calendar for user {user_id}: {e}")
        return False


async def get_user_calendar_status(user_id: int) -> dict:
    """Get user's calendar connection status and settings"""
    try:
        settings = await get_user_settings(user_id)
        if settings:
            return {
                'connected': settings.google_calendar_connected,
                'calendar_id': settings.calendar_id,
                'auto_create_events': settings.auto_create_events,
                'has_refresh_token': bool(settings.google_refresh_token)
            }
        else:
            return {
                'connected': False,
                'calendar_id': None,
                'auto_create_events': False,
                'has_refresh_token': False
            }
    except Exception as e:
        print(f"Error getting calendar status for user {user_id}: {e}")
        return {
            'connected': False,
            'calendar_id': None,
            'auto_create_events': False,
            'has_refresh_token': False
        }


async def cleanup_user_data(user_id: int, retention_days: int) -> dict:
    """
    Clean up user data based on retention policy
    Returns cleanup statistics
    """
    try:
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        deleted_sessions = 0
        deleted_events = 0
        
        async with AsyncSessionLocal() as session:
            # Get old sessions to delete
            old_sessions_stmt = select(CaptureSession.id).where(
                CaptureSession.user_id == user_id,
                CaptureSession.end_time < cutoff_date,
                CaptureSession.status == 'completed'
            )
            old_sessions_result = await session.execute(old_sessions_stmt)
            old_session_ids = [row[0] for row in old_sessions_result.fetchall()]
            
            if old_session_ids:
                # Delete events from old sessions
                delete_events_stmt = delete(Event).where(
                    Event.session_id.in_(old_session_ids)
                )
                events_result = await session.execute(delete_events_stmt)
                deleted_events = events_result.rowcount
                
                # Delete old sessions
                delete_sessions_stmt = delete(CaptureSession).where(
                    CaptureSession.id.in_(old_session_ids)
                )
                sessions_result = await session.execute(delete_sessions_stmt)
                deleted_sessions = sessions_result.rowcount
                
                await session.commit()
        
        return {
            'deleted_sessions': deleted_sessions,
            'deleted_events': deleted_events,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        print(f"Error cleaning up user data for user {user_id}: {e}")
        return {
            'deleted_sessions': 0,
            'deleted_events': 0,
            'error': str(e)
        } 