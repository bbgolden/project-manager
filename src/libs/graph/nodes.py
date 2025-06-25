from typing import Annotated, Literal
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState, ToolNode
from langgraph.types import Command, interrupt
from .states import InputState, OverallState, OutputState
from libs.database import execute, select

model = ChatOllama(model="llama3.1:8b")

@tool
def add_project(name: str, description: str = ""):
    """Runs a SQL query to add a project to the database with the provided name and description information"""
    execute(f"INSERT INTO public.projects(name, description) VALUES('{name}', '{description}')")

@tool
def add_task(name: str, description: str, project_name: str, start, end):
    """placeholder"""
    return

class WorkflowOutput(BaseModel):
    add_project: int = Field(
        description="The number of times that the user wants to create a new project.",
        default=0,
    )
    add_task: int = Field(
        description="The number of times that the user wants to create a new task.",
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

project_maker_tools = [add_project]
project_maker = model.bind_tools(project_maker_tools)

def assign_workflow(state: InputState, config: RunnableConfig) -> Command[Literal["supervisor", "input_helper"]]:
    new_messages = [HumanMessage(state["user_input"])]

    system_prompt = SystemMessage(
        """
        You are an AI that determines which project management tools the user wants to utilize and how many times they wish to utilize each tool.
        This does not refer to external tools, but rather internal ones like creating a project, adding tasks, etc.
        Based on the user's request, return the appropriate number of tools calls for each tool at your disposal.
        If and only if you cannot understand the user's request, return a followup question that respectfully asks the user to give a different request.
        """
    )
    response = queue_builder.invoke([system_prompt] + new_messages, config=config)

    if response.followup:
        new_messages.append(AIMessage(response.followup))

    tool_queue = list[str]()
    for i in range(response.add_project):
        tool_queue.append("project_maker_check")
    for i in range(response.add_task):
        tool_queue.append("scheduler")

    return Command(
        update={
            "messages": new_messages,
            "tool_queue": tool_queue,
            "redirect": "liaison",
            "followup": response.followup
        }, goto="input_helper" if response.followup else "supervisor"
    )


def direct_workflow(state: OverallState) -> Command[Literal["project_maker_check", "scheduler", "scoper", "analyst"]]:
    return Command(
        update={"tool_queue": state["tool_queue"][1:]},
        goto=state["tool_queue"][0],
    )

def clarify_input(state: OverallState) -> Command[Literal["liaison", "project_maker_check"]]:
    new_request = interrupt(state["followup"])

    return Command(
        update={"user_input": new_request} if state["redirect"] == "liaison" else {"messages": [AIMessage(state["followup"]), HumanMessage(new_request)]},
        goto=state["redirect"],
    )

def create_project_check(state: OverallState, config: RunnableConfig) -> Command[Literal["project_maker", "input_helper"]]:
    system_prompt = SystemMessage(
        """
        You are helping to create a new project. If the user wants to create multiple, approach them one at a time.
        Determine whether the provided message history has sufficient information about both the project's name and description.
        If you determine that there is not enough information about these factors, return a followup question that respectfully asks for specific further details
        If you determine that there is sufficient information, return only an empty string. Only do this once information about both name and description are present.
        """
    )
    response = directional_manager.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "redirect": "project_maker_check",
            "followup": response.followup
        }, goto="input_helper" if response.followup else "project_maker"
    )

def create_project(state: OverallState, config: RunnableConfig) -> OverallState:
    system_prompt = SystemMessage(
        """
        You are helping to create a new project.
        From the given message history, extract information about the project's name and description and pass it to the appropriate tools.
        The project's name absolutely must be quoted directly from the user's messages. 
        The description should be formatted as a properly capitalized and punctuated paragraph that could be read without additional context.
        """
    )
    response = project_maker.invoke([system_prompt] + state["messages"], config=config)

    return {"messages": [response]} if response.tool_calls else {"messages": [response], "output": "Ran create_project"}

def create_project_tools():
    return ToolNode(project_maker_tools)

def manage_schedule(state: OverallState) -> OutputState:
    return {"output": "Ran manage_schedule"}

def manage_scope(state: OverallState) -> OutputState:
    return {"output": "Ran manage_scope"}

def analyze_project(state: OverallState) -> OutputState:
    return {"output": "Ran analyze_project"}

def should_finish(state: OverallState):
    if state["messages"][-1].tool_calls:
        return "tools"
    elif state["tool_queue"]:
        return "loop"
    return "end"