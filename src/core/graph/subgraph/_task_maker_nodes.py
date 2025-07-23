from datetime import date
from typing import Literal, Annotated
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from ..states import TaskMakerState, OutputState
from ...utils._connection import execute, select

model = ChatOllama(model="llama3.1:8b")

@tool
def get_task_context(tool_call_id: Annotated[str, InjectedToolCallId], project_name: str):
    """Retrieves necessary context for the project which the new task belongs to."""
    existing_projects = [project for project, in select("SELECT name FROM public.projects")]
    if project_name not in existing_projects:
        raise ValueError(f"Project with name {project_name} does not exist. Please enter a valid project. Existing projects are: {", ".join(existing_projects)}.")
    
    existing_tasks = [task for task, in select("SELECT name FROM public.tasks")]
    project_desc = select("SELECT description FROM public.projects WHERE name = !p1", project_name)[0][0]

    return Command(update={
        "messages": [ToolMessage(f"New task belongs to project with (name: {project_name}) and (description: {project_desc})", tool_call_id=tool_call_id)],
        "existing_projects": existing_projects,
        "existing_tasks": existing_tasks,
        "project_name": project_name,
        "project_desc": project_desc,
    })

@tool
def add_task(
    existing_tasks: Annotated[list[str], InjectedState("existing_tasks")],
    current_name: Annotated[str, InjectedState("task_name")],
    current_desc: Annotated[str, InjectedState("task_desc")],
    current_start: Annotated[str, InjectedState("start_date")],
    current_end: Annotated[str, InjectedState("end_date")],
    tool_call_id: Annotated[str, InjectedToolCallId],
    task_name: str,
    start_date: str = date.today().strftime("%Y-%m-%d"),
    end_date: str = "",
    task_description: str = "",
):
    """Loads provided information into a new task to be created."""
    validated_task_name = task_name if task_name else current_name
    validated_task_desc = task_description if task_description else current_desc
    validated_start = start_date if start_date else current_start
    validated_end = end_date if end_date else current_end

    if validated_task_name in existing_tasks:
        raise ValueError(f"Task with name {validated_task_name} already exists. Please enter a valid task name.")

    return Command(update={
        "messages": [ToolMessage(
            f"""
            Updated name to: {validated_task_name}
            Updated description to: {validated_task_desc}
            Updated start date to: {validated_start}
            Updated end date to: {validated_end}
            """, tool_call_id=tool_call_id)],
        "task_name": validated_task_name,
        "task_desc": validated_task_desc,
        "start_date": validated_start,
        "end_date": validated_end,
    })

@tool
def finish_execution(tool_call_id: Annotated[str, InjectedToolCallId]):
    """Finishes execution of the current portion of the task creation dialogue."""
    return Command(update={
        "messages": [ToolMessage(f"Execution of current node complete. Moving to next node.", tool_call_id=tool_call_id)],
        "finish": True,
    })

context_builder_tools = [get_task_context]
context_builder = model.bind_tools(context_builder_tools)

task_maker_tools = [add_task, finish_execution]
task_maker = model.bind_tools(task_maker_tools)

def create_task_context(state: TaskMakerState, config: RunnableConfig) -> Command[Literal["clarification", "context_tools", "dialogue"]]:
    if state["project_name"] and state["project_name"] in state["existing_projects"]:
        return Command(goto="dialogue")
    
    system_prompt = SystemMessage(
        """
        You are in a direct dialogue with the user helping them to add a task to an existing project.
        Speak in the second person, as if in conversation with the user.
        Your only job is to identify the name of the project that the task belongs to.
        This job is internal to the application and should not be mentioned to the user.

        The project name that the user enters must be an existing project.
        Ask the user for a new project name if they enter one that does not exist. The new name is the one you should refer to at all times.

        If the user only mentions that they would like to add a new task, you must assume that you do not yet have the project name.

        Once you have gathered the correct project name, finish execution. 
        Do not send any message to the user at this point.
        """
    )
    response = context_builder.invoke([system_prompt] + state["messages"], config=config)
    
    return Command(
        update={
            "messages": [response],
            "redirect": "context",
            "followup": response.content,
        }, goto="context_tools" if response.tool_calls else "clarification",
    )

def create_task_context_tools():
    return ToolNode(context_builder_tools)

def create_task_dialogue(state: TaskMakerState, config: RunnableConfig) -> Command[Literal["clarification", "dialogue_tools", "commit"]]:
    if state["finish"]:
        return Command(goto="commit")
    
    system_prompt = SystemMessage(
        f"""
        You are in a direct dialogue with the user, helping them to add a new task to a project as part of a project management application.
        Speak in the second person, as if in conversation with the user.
        A task is an objective to be completed in a project.
        A task has a name (required), description (optional), start date (required), and end date(optional).
        The task you are currently creating belongs to a parent project called {state["project_name"]}.
        This project has the following description (note that this is not the task description): {state["project_desc"]}

        Using your knowledge of the task's parent project, help the user to add the task.
        You must not add any details that the user does not explicitly mention, such as specific names.

        The task's name must be quoted directly from the user's messages and must be formatted in title case.
        The task description must be formatted as a properly capitalized and punctuated paragraph that could be read without additional context. It should be in the third-person.
        If the user provides any dates in terms relative to today, use your knowledge of today's date (which is {date.today().strftime("%Y-%m-%d")}) to approximate the true values of these dates.
        The task's start date must be formatted as YYYY-MM-DD. If the user does not specify a start date, assume that it is today's date. You must ask the user for the task's start date.
        The task's end date must also be formatted as YYYY-MM-DD. You must ask the user for the task's end date, but it is permissible that they do not provide it.

        Once you have confirmed that the task has been added, finish execution.
        Do not ask any followup questions at this point.
        You are not permitted to tell the user that the task has been added. You may only provide the information you have and ask for confirmation that it is correct.
        """
    )
    response = task_maker.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "messages": [response],
            "redirect": "dialogue",
            "followup": response.content,
        }, goto="dialogue_tools" if response.tool_calls else "clarification",
    )

def create_task_dialogue_tools():
    return ToolNode(task_maker_tools)

def create_task_commit(state: TaskMakerState) -> OutputState:
    project_id = select("SELECT project_id FROM public.projects WHERE name = !p1", state["project_name"])[0][0]

    execute("INSERT INTO public.tasks(project_id, name, description, start, \"end\") VALUES(!p1, !p2, !p3, !p4, !p5)", project_id, state["task_name"], state["task_desc"], state["start_date"], state["end_date"])

    return {
        "output": 
            f"""
            New task added with
            Parent Project: {state["project_name"]}
            Name: {state["task_name"]}
            Description: {state["task_desc"]}
            Start Date: {state["start_date"]}
            End Date: {state["end_date"]}
            """
    }