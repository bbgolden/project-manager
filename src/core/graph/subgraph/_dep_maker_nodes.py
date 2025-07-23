from typing import Literal, Annotated
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from ..states import DependencyMakerState, OutputState
from ...utils._connection import execute, select

model = ChatOllama(model="llama3.1:8b")

@tool
def get_dependency_context(
    current_task1_name: Annotated[str, InjectedState("task1_name")],
    current_task2_name: Annotated[str, InjectedState("task2_name")],
    tool_call_id: Annotated[str, InjectedToolCallId], 
    task1_name: str, 
    task2_name: str,
):
    """Retrieves necessary context for the dependent and independent tasks."""
    existing_tasks = [task for task, in select("SELECT name FROM public.tasks")]
    validated_task1_name = task1_name if task1_name else current_task1_name
    validated_task2_name = task2_name if task2_name else current_task2_name

    tasks = [validated_task1_name, validated_task2_name]
    bool_mask = [task not in existing_tasks for task in tasks]
    invalid_tasks = [task for task, bool in zip(tasks, bool_mask) if bool]
    if invalid_tasks:
        raise ValueError(f"The following tasks do not exist: {", ".join(invalid_tasks)}. Please enter valid tasks. Existing tasks are {", ".join(existing_tasks)}.")
    
    task1_id, task1_desc = select("SELECT task_id, description FROM public.tasks WHERE name = !p1", validated_task1_name)[0]
    task2_id, task2_desc = select("SELECT task_id, description FROM public.tasks WHERE name = !p1", validated_task2_name)[0]

    if select("SELECT * FROM public.task_dependencies WHERE task_id = ANY(ARRAY[!p1, !p2]) AND dependent_id = ANY(ARRAY[!p1, !p2])", task1_id, task2_id):
        raise ValueError(f"A dependency already exists between tasks {validated_task1_name} and {validated_task2_name}. Please enter a valid dependency.")

    return Command(update={
        "messages": [ToolMessage(f"New dependency between task with (name: {validated_task1_name}, description: {task1_desc}) and task with (name: {validated_task2_name}, description: {task2_desc})", tool_call_id=tool_call_id)],
        "existing_tasks": existing_tasks,
        "task1_name": validated_task1_name,
        "task1_desc": task1_desc,
        "task2_name": validated_task2_name,
        "task2_desc": task2_desc,
    })

@tool
def add_task_dependency(
    current_task1_name: Annotated[str, InjectedState("task1_name")],
    current_task2_name: Annotated[str, InjectedState("task2_name")],
    current_dep_desc: Annotated[str, InjectedState("dep_desc")],
    tool_call_id: Annotated[str, InjectedToolCallId],
    task1_name: str,
    task2_name: str,
    description: str,
):
    """Loads provided information into a new task dependency to be created. Task 2 is dependent on Task 1 if Task 1 must be finished before Task 2 can be completed."""
    validated_task1_name = task1_name if task1_name else current_task1_name
    validated_task2_name = task2_name if task2_name else current_task2_name
    validated_description = description if description else current_dep_desc

    return Command(update={
        "messages": [ToolMessage(
            f"""
            Updated Task 1 to: {validated_task1_name}
            Updated Task 2 to: {validated_task2_name}
            Updated description to: {validated_description}
            """, tool_call_id=tool_call_id)],
        "task1_name": validated_task1_name,
        "task2_name": validated_task2_name,
        "dep_desc": validated_description,
    })

@tool
def finish_execution(tool_call_id: Annotated[str, InjectedToolCallId]):
    """Finishes execution of the current portion of the task dependency creation dialogue."""
    return Command(update={
        "messages": [ToolMessage(f"Execution of current node complete. Moving to next node.", tool_call_id=tool_call_id)],
        "finish": True,
    })


context_builder_tools = [get_dependency_context]
context_builder = model.bind_tools(context_builder_tools)

dep_maker_tools = [add_task_dependency, finish_execution]
dep_maker = model.bind_tools(dep_maker_tools)

def create_dep_context(state: DependencyMakerState, config: RunnableConfig) -> Command[Literal["clarification", "context_tools", "dialogue"]]:
    if state["task1_name"] and state["task2_name"] and all(task in state["existing_tasks"] for task in [state["task1_name"], state["task2_name"]]):
        return Command(goto="dialogue")
    
    system_prompt = SystemMessage(
        """
        You are in a direct dialogue with the user helping them to add a task dependency to an existing project.
        Speak in the second person, as if in conversation with the user.
        Your only job is to identify the names of the two tasks involved in the task dependency.
        This job is internal to the application and should not be mentioned to the user.

        The task names that the user enters must both be existing tasks and they must not be involved in a dependency with each other already.
        Ask the user for new tasks if they enter ones that do not exist or are already involved in a dependency. 
        The new names are the ones you should refer to at all times.
        It is possible that one or both of the tasks in the dependency are invalid. You must make sure to correct all invalid tasks.

        If the user only mentions that they would like to add a new dependency, you must assume that you do not yet have the task names.

        Once you have gathered the correct task names, finish execution. 
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

def create_dep_context_tools():
    return ToolNode(context_builder_tools)

def create_dep_dialogue(state: DependencyMakerState, config: RunnableConfig) -> Command[Literal["clarification", "dialogue_tools", "commit"]]:
    if state["finish"]:
        return Command(goto="commit")
    
    system_prompt = SystemMessage(
        f"""
        You are in a direct dialogue with the user, helping them to add a new task dependency to a project as part of a project management application.
        Speak in the second person, as if in conversation with the user.
        Task 2 is defined as dependent on Task 1 if Task 1 must be finished before Task 2 can be completed.
        A dependency has a description (optional).
        The task dependency you are currently creating involves two tasks.
        One has the name {state["task1_name"]}.
        This task has the following description (note that this is not the dependency description): {state["task1_desc"]}
        The other has the name {state["task2_name"]}.
        This task has the following description (note that this is not the dependency description): {state["task2_desc"]}

        Using your knowledge of the two tasks involved, help the user to add the task dependency.
        You must not add any details that the user does not explicitly mention, such as specific names.

        Ensure that you understand which task is dependent on the other. If the user has not made it clear, you must ask them to explicitly explain it.
        The task dependency description must be formatted as a properly capitalized and punctuated paragraph that could be read without additional context. It should be in the third-person.

        Once you have confirmed that the dependency has been added, finish execution.
        Do not ask any followup questions at this point.
        You are not permitted to tell the user that the dependency has been added. You may only provide the information you have and ask for confirmation that it is correct.
        """
    )
    response = dep_maker.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "messages": [response],
            "redirect": "dialogue",
            "followup": response.content,
        }, goto="dialogue_tools" if response.tool_calls else "clarification",
    )

def create_dep_dialogue_tools():
    return ToolNode(dep_maker_tools)

def create_dep_commit(state: DependencyMakerState) -> OutputState:
    task1_id = select("SELECT task_id FROM public.tasks WHERE name = !p1", state["task1_name"])[0][0]
    task2_id = select("SELECT task_id FROM public.tasks WHERE name = !p1", state["task2_name"])[0][0]

    execute("INSERT INTO public.task_dependencies(task_id, dependent_id, description) VALUES(!p1, !p2, !p3)", task1_id, task2_id, state["dep_desc"])

    return {"output": f"New task dependency added with\nTask {state["task2_name"]} dependent on task {state["task1_name"]}\nDescription: {state["dep_desc"]}"}