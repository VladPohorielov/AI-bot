"""
Session Manager Service - handles capture session state management
"""
from typing import Optional
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from states.user_states import CaptureStates
from services.database import (
    get_active_session, 
    create_capture_session, 
    CaptureSession, 
    AsyncSessionLocal
)


class SessionManager:
    """Manages capture session states and transitions"""
    
    @staticmethod
    async def start_capture_session(user_id: int, state: FSMContext) -> Optional[CaptureSession]:
        """
        Start a new capture session for user
        Returns existing session if already active, creates new one otherwise
        """
        try:
            # Check if user already has active session
            active_session = await get_active_session(user_id)
            
            if active_session:
                # User already has active session
                return active_session
            
            # Create new session
            session = await create_capture_session(user_id)
            
            # Set FSM state to capturing
            await state.set_state(CaptureStates.CAPTURING)
            await state.update_data(session_id=session.id)
            
            return session
            
        except Exception as e:
            print(f"Error starting capture session: {e}")
            return None
    
    @staticmethod
    async def add_message_to_session(
        user_id: int, 
        message_text: str, 
        state: FSMContext
    ) -> bool:
        """
        Add message to active capture session
        Returns True if message was added successfully
        """
        try:
            # Get state data
            state_data = await state.get_data()
            session_id = state_data.get('session_id')
            
            if not session_id:
                return False
            
            # Get session from database
            async with AsyncSessionLocal() as db_session:
                capture_session = await db_session.get(CaptureSession, session_id)
                
                if not capture_session or capture_session.status != 'active':
                    return False
                
                # Add message to session
                capture_session.add_message(message_text)
                await db_session.commit()
                
                return True
                
        except Exception as e:
            print(f"Error adding message to session: {e}")
            return False
    
    @staticmethod
    async def end_capture_session(user_id: int, state: FSMContext) -> Optional[CaptureSession]:
        """
        End active capture session and prepare for processing
        Returns the session that was ended
        """
        try:
            # Get state data
            state_data = await state.get_data()
            session_id = state_data.get('session_id')
            
            if not session_id:
                return None
            
            # Update session status and set end time
            from datetime import datetime
            async with AsyncSessionLocal() as db_session:
                capture_session = await db_session.get(CaptureSession, session_id)
                
                if not capture_session:
                    return None
                
                capture_session.end_time = datetime.utcnow()
                capture_session.status = 'processing'
                await db_session.commit()
                await db_session.refresh(capture_session)
                
                # Set FSM state to processing
                await state.set_state(CaptureStates.PROCESSING)
                
                return capture_session
                
        except Exception as e:
            print(f"Error ending capture session: {e}")
            return None
    
    @staticmethod
    async def complete_session_processing(
        user_id: int, 
        state: FSMContext, 
        summary: str = None, 
        extracted_events: list = None
    ) -> bool:
        """
        Complete session processing and reset state
        """
        try:
            # Get state data
            state_data = await state.get_data()
            session_id = state_data.get('session_id')
            
            if not session_id:
                return False
            
            # Update session with results
            async with AsyncSessionLocal() as db_session:
                capture_session = await db_session.get(CaptureSession, session_id)
                
                if not capture_session:
                    return False
                
                capture_session.status = 'completed'
                if summary:
                    capture_session.summary = summary
                if extracted_events:
                    capture_session.extracted_events = extracted_events
                
                await db_session.commit()
                
                # Clear FSM state
                await state.clear()
                
                return True
                
        except Exception as e:
            print(f"Error completing session processing: {e}")
            return False
    
    @staticmethod
    async def cancel_session(user_id: int, state: FSMContext) -> bool:
        """
        Cancel active session and cleanup
        """
        try:
            # Get state data
            state_data = await state.get_data()
            session_id = state_data.get('session_id')
            
            if session_id:
                # Mark session as failed
                async with AsyncSessionLocal() as db_session:
                    capture_session = await db_session.get(CaptureSession, session_id)
                    if capture_session:
                        capture_session.status = 'failed'
                        await db_session.commit()
            
            # Clear FSM state
            await state.clear()
            return True
            
        except Exception as e:
            print(f"Error canceling session: {e}")
            return False
    
    @staticmethod
    async def get_session_info(state: FSMContext) -> dict:
        """
        Get current session information from FSM state
        """
        try:
            state_data = await state.get_data()
            current_state = await state.get_state()
            
            return {
                'session_id': state_data.get('session_id'),
                'current_state': current_state,
                'message_count': state_data.get('message_count', 0)
            }
        except Exception as e:
            print(f"Error getting session info: {e}")
            return {}
    
    @staticmethod 
    async def cleanup_expired_sessions():
        """
        Cleanup sessions that have been active too long (background task)
        """
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import select, update
            
            # Sessions active for more than 24 hours are considered expired
            expiry_time = datetime.utcnow() - timedelta(hours=24)
            
            async with AsyncSessionLocal() as db_session:
                # Update expired sessions
                stmt = update(CaptureSession).where(
                    CaptureSession.status == 'active',
                    CaptureSession.start_time < expiry_time
                ).values(status='failed')
                
                await db_session.execute(stmt)
                await db_session.commit()
                
        except Exception as e:
            print(f"Error cleaning up expired sessions: {e}")


# Create global instance
session_manager = SessionManager() 