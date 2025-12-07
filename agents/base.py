import os
from dotenv import load_dotenv
from google.adk.agents import Agent

load_dotenv()
MODEL_ID = os.getenv("MODEL_ID")

def create_agent(name: str, system_instruction: str, input_schema, output_schema) -> Agent:
    return Agent(
        name=name,
        model=MODEL_ID,
        instruction=system_instruction,
        input_schema=input_schema,
        output_schema=output_schema,
    )
