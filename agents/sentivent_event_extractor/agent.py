from agents.base import create_agent
from .schemas import EventExtractionInput, EventExtractionOutput
from .prompt import PROMPT

sentivent_event_agent = create_agent(
    name="sentivent_event_extractor",
    system_instruction=PROMPT,
    input_schema=EventExtractionInput,
    output_schema=EventExtractionOutput,
)
