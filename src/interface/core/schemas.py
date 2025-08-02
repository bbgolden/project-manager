from typing import Annotated, Sequence, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class RouterSchema(BaseModel):
    add_project: int = Field(
        description="The number of times that the user wants to create a new project.",
        default=0,
    )
    add_requirement: int = Field(
        description="The number of times that the user wants to create a new requirement for an existing project.",
        default=0,
    )
    add_task: int = Field(
        description="The number of times that the user wants to create a new task.",
        default=0,
    )
    add_task_dependency: int = Field(
        description="The number of times that the user wants to add a task dependency.",
        default=0,
    )
    add_resource: int = Field(
        description="The number of times that the user wants to create a new resource.",
        default=0,
    )
    assign_resource: int = Field(
        description="The number of times that the user wants to assign a resource to an existing task.",
        default=0,
    )
    analyze_project: int = Field(
        description="Whether or not the user wants to ask questions about or analyze the project. 0 if not, 1 if so.",
        default=0,
    )
    followup: str = Field(
        description="A followup question asking the user to provide more clear information, if necessary.",
        default="",
    )

class DialogueSchema(BaseModel):
    followup: str = Field(description="A followup question for the user to answer and give further clarification, if necessary.")

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

class AnalystState(SubgraphState):
    existing_tasks: list[str]
    existing_resources: list[tuple[str]]
    project_id: int
    project_name: str
    project_desc: str