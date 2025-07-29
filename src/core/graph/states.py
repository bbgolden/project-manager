from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class InputState(TypedDict):
    user_input: str

class OutputState(TypedDict):
    output: str

class OverallState(InputState, OutputState):
    messages: Annotated[Sequence[AnyMessage], add_messages]
    tool_queue: list[str]
    prev: str
    followup: str

class SubgraphState(OutputState):
    messages: Annotated[Sequence[AnyMessage], add_messages]
    redirect: str
    followup: str
    finish: bool

class ProjectMakerState(SubgraphState):
    existing_projects: list[str]
    project_name: str
    project_desc: str

class ReqMakerState(SubgraphState):
    existing_projects: list[str]
    project_name: str
    project_desc: str
    req_desc: str

class TaskMakerState(SubgraphState):
    existing_projects: list[str]
    existing_tasks: list[str]
    project_name: str
    project_desc: str
    task_name: str
    task_desc: str
    start_date: str
    end_date: str

class DependencyMakerState(SubgraphState):
    existing_tasks: list[str]
    task1_name: str
    task1_desc: str
    task2_name: str
    task2_desc: str
    dep_desc: str

class ResourceMakerState(SubgraphState):
    existing_contacts: list[str]
    contact: str
    first_name: str
    last_name: str

class ResourceAssignerState(SubgraphState):
    existing_tasks: list[str]
    matching_resources: list[tuple[str]]
    task_name: str
    re_first_name: str
    re_last_name: str
    re_contact: str