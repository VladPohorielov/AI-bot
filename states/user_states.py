from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    """Settings menu states"""
    CHOOSING_LANGUAGE = State()
    CHOOSING_SUMMARY_STYLE = State()
    MAIN_SETTINGS_MENU = State()


class CaptureStates(StatesGroup):
    """Enhanced FSM for conversation capture sessions"""
    
    # Main capture flow
    IDLE = State()                          # Default state - ready for new session
    CAPTURING = State()                     # Actively capturing messages
    ANALYZING = State()                     # Processing captured content
    
    # Review & editing flow
    REVIEWING_RESULTS = State()             # User reviewing analysis results
    EDITING_EVENT = State()                 # User editing specific event
    EDITING_TITLE = State()                 # Editing event title
    EDITING_DATE = State()                  # Editing event date
    EDITING_TIME = State()                  # Editing event time
    EDITING_LOCATION = State()              # Editing event location
    EDITING_PARTICIPANTS = State()          # Editing participants
    EDITING_NOTES = State()                 # Editing notes
    
    # Confirmation & finalization
    CONFIRMING_SAVE = State()              # Final confirmation before saving
    SAVING_TO_CALENDAR = State()           # Saving to Google Calendar
    COMPLETED = State()                    # Session completed


class EventEditStates(StatesGroup):
    """Dedicated states for event editing workflow"""
    
    SELECTING_FIELD = State()              # User selecting which field to edit
    ENTERING_VALUE = State()               # User entering new value
    CONFIRMING_CHANGE = State()            # Confirming the change


class CalendarStates(StatesGroup):
    """States for calendar integration workflow"""
    
    CONNECTING = State()                   # OAuth connection process
    SELECTING_CALENDAR = State()           # Selecting target calendar
    CONFIRMING_EVENT = State()             # Final event confirmation
    PROCESSING_SAVE = State()              # Saving event to calendar


class SummaryStates(StatesGroup):
    """States for summary workflow"""
    WAITING_FOR_TEXT = State()


class ChatGPTStates(StatesGroup):
    """States for ChatGPT conversation"""
    CHATTING = State()
