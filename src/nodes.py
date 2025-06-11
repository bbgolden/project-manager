from typing import Annotated, Literal
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState, ToolNode
from langgraph.types import Command, interrupt
from states import InputState, OverallState, OutputState

model = ChatOllama(model="llama3:latest")

class DirectionalOutput(BaseModel):
    next: str = Field(description="This field contains the name of the agent which the user must next be redirected to.")

directional_manager = model.with_structured_output(DirectionalOutput)

def direct_workflow(state: InputState, config: RunnableConfig) -> Command[Literal["project_maker", "scheduler", "scoper", "analyst", "input_helper"]]:
    system_prompt = SystemMessage(
        """
        You are an AI that determines which agent a user must be redirected to based on their most recent request.
        Your possible outputs are limited to the enumerated values as follows:
        If the user wants to make a new project, return 'project_maker'
        If the user wants to modify information pertaining to the project's timeline, tasks, or resources, return 'scheduler'
        If the user wants to modify information related to the project's description, methodology, or end goal, return 'scoper'
        If the user wants to access information or ask quations about the project, return 'analyst'
        If none of the above apply and you cannot understand the user's request, return 'input_helper'
        """
    )
    response = directional_manager.invoke([system_prompt, HumanMessage(state["user_input"])], config=config)

    return Command(
        update={"messages": [HumanMessage(state["user_input"]), AIMessage("Go to " + response.next)]},
        goto=response.next
    )

def clarify_direction(state: OverallState) -> InputState:
    new_request = interrupt("I'm sorry, I can't help you with that. Can I do anything else for you?")

    return {"user_input": new_request}

def create_project(state: OverallState) -> OutputState:
    return {"output": "Ran create_project"}

def manage_schedule(state: OverallState) -> OutputState:
    return {"output": "Ran manage_schedule"}

def manage_scope(state: OverallState) -> OutputState:
    return {"output": "Ran manage_scope"}

def analyze_project(state: OverallState) -> OutputState:
    return {"output": "Ran analyze_project"}