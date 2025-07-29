from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt
from langgraph.graph import StateGraph
from .states import (
    OverallState,
    SubgraphState, 
    ProjectMakerState, 
    ReqMakerState, 
    TaskMakerState, 
    DependencyMakerState, 
    ResourceMakerState,
    ResourceAssignerState, 
    OutputState,
)
from .subgraph._project_maker_nodes import (
    create_project_context, 
    create_project_dialogue, 
    create_project_dialogue_tools, 
    create_project_commit,
)
from .subgraph._req_maker_nodes import (
    create_req_context, 
    create_req_context_tools, 
    create_req_dialogue, 
    create_req_dialogue_tools, 
    create_req_commit,
)
from .subgraph._task_maker_nodes import (
    create_task_context, 
    create_task_context_tools, 
    create_task_dialogue, 
    create_task_dialogue_tools, 
    create_task_commit,
)
from .subgraph._dep_maker_nodes import (
    create_dep_context, 
    create_dep_context_tools, 
    create_dep_dialogue, 
    create_dep_dialogue_tools, 
    create_dep_commit,
)
from .subgraph._resource_maker_nodes import (
    create_resource_context, 
    create_resource_dialogue, 
    create_resource_dialogue_tools, 
    create_resource_commit
)
from .subgraph._resource_assigner_nodes import (
    create_resource_assignment_context, 
    create_resource_assignment_context_tools,
    create_resource_assignment_dialogue,
    create_resource_assignment_dialogue_tools,
    create_resource_assignment_commit,
)
from ..utils._connection import execute, select

model = ChatOllama(model="llama3.1:8b")

@tool
def assign_resource(task_name: str, resource_first_name: str, resource_last_name: str = ""):
    """Assigns an existing resource to an existing task."""

    task_id = select(f"SELECT task_id FROM public.tasks WHERE name = '{task_name}'")[0][0]

    if resource_last_name:
        query = f"SELECT resource_id FROM public.resources WHERE first_name = '{resource_first_name}' and last_name = '{resource_last_name}'"
    else:
        query = f"SELECT resource_id FROM public.resources WHERE first_name = '{resource_first_name}' and last_name IS NULL"
    resource_id = select(query)[0][0]

    execute(f"INSERT INTO public.resource_assignments(task_id, resource_id) VALUES({task_id}, {resource_id})")

class WorkflowOutput(BaseModel):
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
    followup: str = Field(
        description="A followup question asking the user to provide more clear information, if necessary.",
        default="",
    )

class DirectionalOutput(BaseModel):
    followup: str = Field(description="A followup question for the user to answer and give further clarification, if necessary.")

queue_builder = model.with_structured_output(WorkflowOutput)
directional_manager = model.with_structured_output(DirectionalOutput)

# Threshold for "unvaluable" response from agents (characters)
value_thresh = 30
tool_to_direction = {
        "add_project": "project_maker",
        "add_requirement": "req_maker",
        "add_task": "task_maker",
        "add_task_dependency": "dep_maker",
        "add_resource": "resource_maker",
        "assign_resource": "resource_assigner",
}

def assign_workflow(state: OverallState, config: RunnableConfig) -> Command[Literal["supervisor", "clarification"]]:
    new_messages = [HumanMessage(state["user_input"])]

    system_prompt = SystemMessage(
        """
        You are an AI that determines which project management functions the user wants to utilize and how many times they wish to utilize each function.
        This does not refer to external function, but rather internal ones like creating a project, adding tasks, etc.
        Do not explicitly ask the user for which functions they would like to use. It is your job to inference that information from their messages.
        The following are functions the user may want to use . They are each distinct and should be treated as such.

        Adding a new project
        Adding a new requirement to a project
        Adding a new task
        Adding a new task dependency
        Adding a new resource
        Assigning a resource

        Based on the user's request, return the appropriate number of function calls for each function at your disposal.
        If and only if you cannot understand the user's request, return a followup question (in the form of a comprehensible sentence) that respectfully asks the user to give a different request.
        """
    )
    response = queue_builder.invoke([system_prompt] + state["messages"] + new_messages, config=config).model_dump()

    if len(response["followup"]) > value_thresh:
        new_messages.append(AIMessage(response["followup"]))

    tool_queue = list[str]()
    for tool, direction in tool_to_direction.items():
        tool_queue.extend([direction] * response[tool])

    return Command(
        update={
            "messages": new_messages,
            "tool_queue": tool_queue,
            "prev": "liaison",
            "followup": response["followup"],
        }, goto="clarification" if len(response["followup"]) > value_thresh else "supervisor",
    )

def direct_workflow(state: OverallState) -> Command[Literal["project_maker", "req_maker", "task_maker", "dep_maker", "resource_maker", "resource_assigner", "scoper", "analyst", "suggestion_commit"]]:
    return Command(
        update={"tool_queue": state["tool_queue"][1:]},
        goto=state["tool_queue"][0] if state["tool_queue"] else "suggestion_commit",
    )

def clarify_input(state: OverallState) -> Command[Literal["liaison", "suggestion_commit"]]:
    new_request = interrupt(state["followup"])

    return Command(
        update={"user_input": new_request} if state["prev"] == "liaison" else {"messages": [AIMessage(state["followup"]), HumanMessage(new_request)]},
        goto=state["prev"],
    )

def clarify_subgraph_input(state: SubgraphState) -> Command[Literal["context", "dialogue"]]:
    new_request = interrupt(state["followup"])

    return Command(
        update={"messages": [HumanMessage(new_request)]},
        goto=state["redirect"],
    )

project_maker_workflow = StateGraph(ProjectMakerState, output=OutputState)

project_maker_workflow.add_node("clarification", clarify_subgraph_input)
project_maker_workflow.add_node("context", create_project_context)
project_maker_workflow.add_node("dialogue", create_project_dialogue)
project_maker_workflow.add_node("dialogue_tools", create_project_dialogue_tools())
project_maker_workflow.add_node("commit", create_project_commit)

project_maker_workflow.set_entry_point("context")
project_maker_workflow.add_edge("context", "dialogue")
project_maker_workflow.add_edge("dialogue_tools", "dialogue")
project_maker_workflow.set_finish_point("commit")

project_maker = project_maker_workflow.compile()

def create_project(state: OverallState) -> OverallState:
    response = project_maker.invoke({
        "messages": state["messages"],
        "project_name": "",
        "project_desc": "",
        "finish": False,
    })

    return {
        "messages": [AIMessage(response["output"])],
        "prev": "adding a new project",
    }

req_maker_workflow = StateGraph(ReqMakerState, output=OutputState)

req_maker_workflow.add_node("clarification", clarify_subgraph_input)
req_maker_workflow.add_node("context", create_req_context)
req_maker_workflow.add_node("context_tools", create_req_context_tools())
req_maker_workflow.add_node("dialogue", create_req_dialogue)
req_maker_workflow.add_node("dialogue_tools", create_req_dialogue_tools())
req_maker_workflow.add_node("commit", create_req_commit)

req_maker_workflow.set_entry_point("context")
req_maker_workflow.add_edge("context_tools", "context")
req_maker_workflow.add_edge("dialogue_tools", "dialogue")
req_maker_workflow.set_finish_point("commit")

req_maker = req_maker_workflow.compile()

def create_req(state: OverallState) -> OverallState:
    response = req_maker.invoke({
        "messages": state["messages"],
        "project_name": "",
        "req_desc": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "adding a new requirement",
    }

task_maker_workflow = StateGraph(TaskMakerState, output=OutputState)

task_maker_workflow.add_node("clarification", clarify_subgraph_input)
task_maker_workflow.add_node("context", create_task_context)
task_maker_workflow.add_node("context_tools", create_task_context_tools())
task_maker_workflow.add_node("dialogue", create_task_dialogue)
task_maker_workflow.add_node("dialogue_tools", create_task_dialogue_tools())
task_maker_workflow.add_node("commit", create_task_commit)

task_maker_workflow.set_entry_point("context")
task_maker_workflow.add_edge("context_tools", "context")
task_maker_workflow.add_edge("dialogue_tools", "dialogue")
task_maker_workflow.set_finish_point("commit")

task_maker = task_maker_workflow.compile()

def create_task(state: OverallState) -> OverallState:
    response = task_maker.invoke({
        "messages": state["messages"],
        "project_name": "",
        "task_name": "",
        "task_desc": "",
        "start_date": "",
        "end_date": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "adding a new task",
    }

dep_maker_workflow = StateGraph(DependencyMakerState, output=OutputState)

dep_maker_workflow.add_node("clarification", clarify_subgraph_input)
dep_maker_workflow.add_node("context", create_dep_context)
dep_maker_workflow.add_node("context_tools", create_dep_context_tools())
dep_maker_workflow.add_node("dialogue", create_dep_dialogue)
dep_maker_workflow.add_node("dialogue_tools", create_dep_dialogue_tools())
dep_maker_workflow.add_node("commit", create_dep_commit)

dep_maker_workflow.set_entry_point("context")
dep_maker_workflow.add_edge("context_tools", "context")
dep_maker_workflow.add_edge("dialogue_tools", "dialogue")
dep_maker_workflow.set_finish_point("commit")

dep_maker = dep_maker_workflow.compile()

def create_dep(state: OverallState) -> OverallState:
    response = dep_maker.invoke({
        "messages": state["messages"],
        "task1_name": "",
        "task2_name": "",
        "dep_desc": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "adding a new task dependency",
    }

resource_maker_workflow = StateGraph(ResourceMakerState, output=OutputState)

resource_maker_workflow.add_node("clarification", clarify_subgraph_input)
resource_maker_workflow.add_node("context", create_resource_context)
resource_maker_workflow.add_node("dialogue", create_resource_dialogue)
resource_maker_workflow.add_node("dialogue_tools", create_resource_dialogue_tools())
resource_maker_workflow.add_node("commit", create_resource_commit)

resource_maker_workflow.set_entry_point("context")
resource_maker_workflow.add_edge("context", "dialogue")
resource_maker_workflow.add_edge("dialogue_tools", "dialogue")
resource_maker_workflow.set_finish_point("commit")

resource_maker = resource_maker_workflow.compile()

def create_resource(state: OverallState) -> OverallState:
    response = resource_maker.invoke({
        "messages": state["messages"],
        "first_name": "",
        "last_name": "",
        "contact": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "adding a new resource",
    }

resource_assigner_workflow = StateGraph(ResourceAssignerState, output=OutputState)

resource_assigner_workflow.add_node("clarification", clarify_subgraph_input)
resource_assigner_workflow.add_node("context", create_resource_assignment_context)
resource_assigner_workflow.add_node("context_tools", create_resource_assignment_context_tools())
resource_assigner_workflow.add_node("dialogue", create_resource_assignment_dialogue)
resource_assigner_workflow.add_node("dialogue_tools", create_resource_assignment_dialogue_tools())
resource_assigner_workflow.add_node("commit", create_resource_assignment_commit)

resource_assigner_workflow.set_entry_point("context")
resource_assigner_workflow.add_edge("context_tools", "context")
resource_assigner_workflow.add_edge("dialogue_tools", "dialogue")
resource_assigner_workflow.set_finish_point("commit")

resource_assigner = resource_assigner_workflow.compile()

def assign_resource(state: OverallState) -> OverallState:
    response = resource_assigner.invoke({
        "messages": state["messages"],
        "matching_resources": [],
        "task_name": "",
        "re_first_name": "",
        "re_last_name": "",
        "re_contact": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "assigning a resource",
    }

def manage_scope(state: OverallState) -> OutputState:
    return {"output": "Ran manage_scope"}

def analyze_project(state: OverallState) -> OutputState:
    return {"output": "Ran analyze_project"}

def suggest_next(state: OverallState, config: RunnableConfig) -> Command[Literal["clarification", "supervisor"]]:
    system_prompt = SystemMessage(
        f"""
        You are helping the user to create and manage their projects as part of a project management software.
        Your task is to recommend the use of a secondary project management function based on the most recent one that the user has utilized.
        The following are existing project management functions and which recommendations to offer in each case.

        Adding a new project: recommended secondary functions are adding a new requirement
        Adding a new requirement: recommended secondary functions are adding another requirement
        Adding a new task: recommended secondary functions are adding a new task dependency, adding a new resource, and assigning a resource to that task
        Adding a new task dependency: recommended secondary functions are adding another task dependency
        Adding a new resource: recommended secondary functions are assigning that resource to a task
        Assigning a resource: recommended secondary functions are adding a new resource

        The user's most recently used function is {state["prev"]}
        Take into consideration this information, recent message context, and the above list.
        Also consider any questions asked in the AI message after the latest tool call.
        Return a followup question using these factors that respectfully asks the user whether they would like to utilize an appropriate secondary function.
        Ensure that the question is formatted as a proper sentence.
        """
    )
    response = directional_manager.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "prev": "suggestion_commit", 
            "followup": response.followup,
        }, goto="clarification" if len(response.followup) > value_thresh else "supervisor",
    )

def suggest_commit(state: OverallState, config: RunnableConfig) -> OverallState:
    system_prompt = SystemMessage(
        """
        You are helping the user to create and manage their projects as part of a project management software.
        Your task is to recommend the use of a secondary project management function based on the most recent one that the user has utilized.

        Examine the provided messages and context to determine which project functions the user would like to use and how many of each.
        Based on the user's response to the AI-prompted question, return the appropriate number of calls for each function at your disposal.
        Remember that it is possible that the user may not wish to use any tools at all.

        If the user's response is negative, assume that they do not wish to add any tools.
        """
    )
    response = queue_builder.invoke([system_prompt] + state["messages"][-2:], config=config).model_dump()

    new_tools = list[str]()
    for tool, direction in tool_to_direction.items():
        new_tools.extend([direction] * response[tool])

    return {
        "tool_queue": new_tools + state["tool_queue"], 
        "output": "New tools added: " + (", ".join(new_tools) if new_tools else "None"),
    }

def should_finish(state: OverallState):
    if state["tool_queue"]:
        return "loop"
    return "end"