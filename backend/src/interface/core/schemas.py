from typing import Annotated, Sequence, Any
from operator import add
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

# Model output schemas

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

# Unique wrappers

class Action(BaseModel):
    name: str
    params: dict[str, Any]

class Task(BaseModel):
    projectName: str
    taskName: str
    taskDesc: str | None = None
    start: str
    end: str | None = None

# Graph states

class InputState(BaseModel):
    user_input: str

class OutputState(BaseModel):
    output: str | None = None
    actions_taken: Annotated[Sequence[Action], add] = []

class SubgraphOutputState(BaseModel):
    action: Action | None = None

class OverallState(InputState, OutputState):
    messages: Annotated[Sequence[AnyMessage], add_messages]
    tool_queue: list[str] = []
    prev: str | None = None
    followup: str | None = None

class SubgraphState(SubgraphOutputState):
    messages: Annotated[Sequence[AnyMessage], add_messages]
    redirect: str | None = None
    followup: str | None = None
    finish: bool = False

# Subgraph-specific graph states

class ProjectMakerState(SubgraphState):
    existing_projects: list[str] = []
    project_name: Annotated[str, "__action_param__"] = ""
    project_desc: Annotated[str, "__action_param__"] = ""

class ReqMakerState(SubgraphState):
    existing_projects: list[str] = []
    project_name: Annotated[str, "__action_param__"] = ""
    project_desc: str = ""
    req_desc: Annotated[str, "__action_param__"] = ""

class TaskMakerState(SubgraphState):
    existing_projects: list[str] = []
    existing_tasks: list[str] = []
    project_name: Annotated[str, "__action_param__"] = ""
    project_desc: str = ""
    task_name: Annotated[str, "__action_param__"] = ""
    task_desc: Annotated[str, "__action_param__"] = ""
    start_date: Annotated[str, "__action_param__"] = ""
    end_date: Annotated[str, "__action_param__"] = ""

class DependencyMakerState(SubgraphState):
    existing_tasks: list[str] = []
    task1_name: Annotated[str, "__action_param__"] = ""
    task1_desc: str = ""
    task2_name: Annotated[str, "__action_param__"] = ""
    task2_desc: str = ""
    dep_desc: Annotated[str, "__action_param__"] = ""

class ResourceMakerState(SubgraphState):
    existing_contacts: list[str] = []
    contact: Annotated[str, "__action_param__"] = ""
    first_name: Annotated[str, "__action_param__"] = ""
    last_name: Annotated[str, "__action_param__"] = ""

class ResourceAssignerState(SubgraphState):
    existing_tasks: list[str] = []
    matching_resources: list[tuple[str]] = []
    task_name: Annotated[str, "__action_param__"] = ""
    re_first_name: Annotated[str, "__action_param__"] = ""
    re_last_name: Annotated[str, "__action_param__"] = ""
    re_contact: Annotated[str, "__action_param__"] = ""

class AnalystState(SubgraphState):
    existing_tasks: list[str] = []
    existing_resources: list[tuple[str, str | None, str]] = []
    project_id: int = -1
    project_name: Annotated[str, "__action_param__"] = ""
    project_desc: str = ""