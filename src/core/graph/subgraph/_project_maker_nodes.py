from typing import Literal, Annotated
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from ..states import ProjectMakerState, OutputState
from ...utils._connection import execute, select

model = ChatOllama(model="llama3.1:8b")

@tool
def add_project(
    existing_projects: Annotated[list[str], InjectedState("existing_projects")],
    current_name: Annotated[str, InjectedState("project_name")], 
    current_description: Annotated[str, InjectedState("project_desc")], 
    tool_call_id: Annotated[str, InjectedToolCallId], 
    name: str, 
    description: str = "",
):
    """Loads provided name and description information into a new project to be created."""
    validated_name = name if name else current_name
    validated_desc = description if description else current_description

    if validated_name in existing_projects:
        raise ValueError(f"Project with name {validated_name} already exists. Please enter a valid project name.")

    return Command(update={
        "messages": [ToolMessage(f"Updated project name to: {validated_name}.\nUpdated project description to: {validated_desc}", tool_call_id=tool_call_id)],
        "project_name": validated_name,
        "project_desc": validated_desc,
    })

@tool
def finish_execution(tool_call_id: Annotated[str, InjectedToolCallId]):
    """Finishes execution of the current portion of the project creation dialogue."""
    return Command(update={
        "messages": [ToolMessage(f"Execution of current node complete. Moving to next node.", tool_call_id=tool_call_id)],
        "finish": True,
    })

project_maker_tools = [add_project, finish_execution]
project_maker = model.bind_tools(project_maker_tools)

def create_project_context(state: ProjectMakerState) -> ProjectMakerState:
    existing_projects = [project for project, in select("SELECT name FROM public.projects")]

    return {"existing_projects": existing_projects}

def create_project_dialogue(state: ProjectMakerState, config: RunnableConfig) -> Command[Literal["clarification", "dialogue_tools", "commit"]]:
    if state["finish"]:
        return Command(goto="commit")
    
    system_prompt = SystemMessage(
        """
        You are in a direct dialogue with the user, helping them to create a new project as part of a project management application.
        Speak in the second person, as if in conversation with the user.
        A project has a name (required) and a description (optional).

        The name of the new project cannot be the same as any existing projects' names. 
        Ask the user for a new name if they enter one that exists already. The new name is the one you should refer to at all times.

        If the user only mentions that they would like to make a new project, you must assume that you do not yet have the project name.
        You must ask the user for a description for the project, but it is permissible that they do not provide it.
        You must not add any details that the user does not explicitly mention, such as specific names.

        The project's name must be quoted directly from the user's messages and must be formatted in title case.
        The description must be formatted as a properly capitalized and punctuated paragraph that could be read without additional context. It should be in the third-person.

        Once you have confirmed that the project has been added, finish execution.
        Do not ask any followup questions at this point.
        You are not permitted to tell the user that the project has been added. You may only provide the information you have and ask for confirmation that it is correct.
        """
    )
    response = project_maker.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "messages": [response],
            "redirect": "dialogue",
            "followup": response.content,
        }, goto="dialogue_tools" if response.tool_calls else "clarification",
    )

def create_project_dialogue_tools():
    return ToolNode(project_maker_tools)

def create_project_commit(state: ProjectMakerState) -> OutputState:
    execute(f"INSERT INTO public.projects(name, description) VALUES(!p1, !p2)", state["project_name"], state["project_desc"])

    return {"output": f"New project added with\nName: {state["project_name"]}\nDescription: {state["project_desc"]}"}