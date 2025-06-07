from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class InputState(TypedDict):
    user_input: str

class OutputState(TypedDict):
    output: str

class OverallState(OutputState):
    messages: Annotated[Sequence[AnyMessage], add_messages]