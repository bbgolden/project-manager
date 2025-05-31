from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class ProjectState(TypedDict):
    messages: Annotated[Sequence[AnyMessage], add_messages]
    budget_info: str
    timeline_info: str
    scope_info: str

class OutputState(TypedDict):
    project_plan: str