"""Honeycomb ADK agent entry point."""
from google.adk.agents import Agent

from .system_prompt import SYSTEM_PROMPT
from .tools import (
    get_concept_details,
    grade_my_answer,
    ingest_learning_source,
    list_my_concepts,
    quiz_concept,
)

honeycomb_agent = Agent(
    name="honeycomb",
    model="gemini-2.5-flash",
    description="A learning agent that builds and maintains your personal knowledge graph from your sources.",
    instruction=SYSTEM_PROMPT,
    tools=[
        ingest_learning_source,
        quiz_concept,
        grade_my_answer,
        list_my_concepts,
        get_concept_details,
    ],
)

# ADK CLI tools (`adk run`, `adk web`) auto-discover a module-level `root_agent`.
root_agent = honeycomb_agent
