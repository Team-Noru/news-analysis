from pydantic import BaseModel
from typing import Optional, List

class EventExtractionInput(BaseModel):
    article: str

class EventItem(BaseModel):
    event_type: str
    company: str
    target: Optional[str]
    value: Optional[str]
    date: Optional[str]
    trigger_word: Optional[str]
    summary: str

class EventExtractionOutput(BaseModel):
    events: List[EventItem]
