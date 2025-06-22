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
    return

class DirectionalOutput(BaseModel):
    next: str = Field(description="This field contains the name of the agent which the user must next be redirected to and nothing else.")
    followup: str = Field(
        description="This field contains a followup question for the user to answer, if necessary.",
        default="I'm sorry, I can't help with that. Can I do anything else for you? ",
    )

directional_manager = model.with_structured_output(DirectionalOutput)

project_maker_tools = [add_project]
project_maker = model.bind_tools(project_maker_tools)

def direct_workflow(state: InputState, config: RunnableConfig) -> Command[Literal["project_maker_check", "scheduler", "scoper", "analyst", "input_helper"]]:
    system_prompt = SystemMessage(
        """
        You are an AI that determines which agent a user must be redirected to based on their request.
        Your possible outputs are limited to the enumerated values as follows:
        If the user wants to make a new project, return 'project_maker_check'
        If the user wants to modify information pertaining to the project's timeline, tasks, or resources, return 'scheduler_check'
        If the user wants to modify information related to the project's description, requirements, or end goal, return 'scoper_check'
        If the user wants to access information or ask questions about the project, return 'analyst_check'
        If none of the above apply and you cannot understand the user's request, return 'input_helper'
        If and only if you return 'input_helper', also return a followup question that respectfully asks the user for a more clear request 
        """
    )
    response = directional_manager.invoke([system_prompt, HumanMessage(state["user_input"])], config=config)

    new_messages = [HumanMessage(state["user_input"])]
    if response.next == "input_helper":
        new_messages.append(AIMessage(response.followup))

    return Command(
        update={"messages": new_messages,
                "redirect": "liaison",
                "followup": response.followup
        }, goto=response.next,
    )

def clarify_input(state: OverallState) -> Command[Literal["liaison"]]:
    new_request = interrupt(state["followup"])

    return Command(
        update={"user_input": new_request} if state["redirect"] == "liaison" else {"messages": [AIMessage(state["followup"]), HumanMessage(new_request)]},
        goto=state["redirect"],
    )

def create_project_check(state: OverallState, config: RunnableConfig) -> Command[Literal["project_maker", "input_helper"]]:
    system_prompt = SystemMessage(
        """
        You are helping to create a new project. 
        Determine whether the provided message history has sufficient information about both the project's name and description.
        If you determine that there is not enough information about these factors, return a followup question that respectfully asks for specific further details
        If you determine that there is sufficient information, return only an empty string. Only do this once information about both name and description are present.
        """
    )
    response = directional_manager.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "redirect": "project_maker_check",
            "followup": response.next
        }, goto="input_helper" if response.next else "project_maker"
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
    return "end"