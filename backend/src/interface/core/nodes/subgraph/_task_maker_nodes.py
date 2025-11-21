from datetime import date
from typing import Literal, Annotated
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from langgraph.graph import StateGraph
from interface.config import model
from interface.core.schemas import TaskMakerState, SubgraphOutputState
from interface.core.templates import SUBAGENT_PROMPT_GENERIC
from interface.utils._db_utils import execute, select
from interface.utils._agent_utils import clarify_subgraph_input, compile_action_data

@tool
def get_task_context(tool_call_id: Annotated[str, InjectedToolCallId], project_name: str):
    """
    DESCRIPTION: 
    Retrieve information about existing projects, existing tasks, and the project
    that this new task is to belong to. These will be useful when validating the information for 
    the new task.

    PARAMETERS: 
    - project_name: The name of the project that this new task is to belong to.
    """
    existing_projects = [project for project, in select("SELECT name FROM public.projects")]
    if project_name not in existing_projects:
        raise ValueError(f"Project with name {project_name} does not exist. Please enter a valid project."
                         + f" Existing projects are: {", ".join(existing_projects)}.")
    
    project_id, project_desc = select("SELECT project_id, description FROM public.projects WHERE name = !p1", project_name)[0]
    existing_tasks = [task for task, in select("SELECT name FROM public.tasks WHERE project_id = !p1", project_id)]

    return Command(update={
        "messages": [ToolMessage(f"New task belongs to project with (name: {project_name}) and"
                                 + f" (description: {project_desc})", tool_call_id=tool_call_id)],
        "existing_projects": existing_projects,
        "existing_tasks": existing_tasks,
        "project_id": project_id,
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
    start_date: str,
    end_date: str | None = "",
    task_description: str | None = "",
):
    """
    DESCRIPTION: 
    Store the information that you currently have about the new task. This tool 
    can and should be called multiple times as the user provides more of the appropriate data.

    PARAMETERS: 
    - task_name - The name of the new task.
    - task_description (OPTIONAL): The description of the new task.
    - start_date: The date on which the new task is to start.
    - end_date (OPTIONAL): The date on which the new task is to end.
    """
    vtask_name = task_name or current_name
    vtask_desc = task_description or current_desc
    vstart = start_date or current_start
    vend = end_date or current_end

    if vtask_name in existing_tasks:
        raise ValueError(f"Task with name {vtask_name} already exists. Please enter a valid task name.")

    return Command(update={
        "messages": [ToolMessage(
            f"""
            Updated name to: {vtask_name}
            Updated description to: {vtask_desc}
            Updated start date to: {vstart}
            Updated end date to: {vend}
            """, tool_call_id=tool_call_id)],
        "task_name": vtask_name,
        "task_desc": vtask_desc,
        "start_date": vstart,
        "end_date": vend,
    })

@tool
def finish_execution(tool_call_id: Annotated[str, InjectedToolCallId]):
    """
    DESCRIPTION:
    Indicate that all necessary information has been received and stored and that
    this task creation function has been successfully completed.

    PARAMETERS:
    This tool has no parameters.
    """
    return Command(update={
        "messages": [ToolMessage(f"Execution of current node complete. Moving to next node.", tool_call_id=tool_call_id)],
        "finish": True,
    })

@tool
def cancel(tool_call_id: Annotated[str, InjectedToolCallId]):
    """
    DESCRIPTION: 
    Indicate that the user has expressed the desire to cancel the current task
    creation function. This will return the user to the project management function selection
    portion of the dialogue.

    PARAMETERS:
    This tool has no parameters.
    """
    return Command(update={
        "messages": [ToolMessage("Cancelling current task creation dialogue.", tool_call_id=tool_call_id)],
        "cancel": True,
    })

task_maker_tools = [get_task_context, add_task, finish_execution, cancel]
task_maker = model.bind_tools(task_maker_tools)

def create_task_dialogue(state: TaskMakerState, config: RunnableConfig) -> Command[Literal["clarification", "dialogue_tools", "commit"]]:
    if state.cancel:
        HUMAN_CANCEL_MESSAGE_INDEX = -3

        return Command(graph=Command.PARENT, goto="liaison", 
                       update={"messages": [state.messages[HUMAN_CANCEL_MESSAGE_INDEX]]})
    elif state.finish:
        return Command(goto="commit")

    existing_projects = state.existing_projects or [project for project, in select("SELECT name from public.projects")]

    system_prompt = SystemMessage(SUBAGENT_PROMPT_GENERIC.format(
        subagent="Task Maker",
        subagent_tasks="Create tasks that belong to existing projects.",
        subagent_context=TASK_CONTEXT.format(project_name=state.project_name or "Not yet available",
                                             project_desc=state.project_desc or "Not yet available"),
        params=TASK_PARAMS,
        instructions=TASK_INSTR.format(existing_projects=existing_projects,
                                       existing_tasks=state.existing_tasks,
                                       today=date.today().strftime("%Y-%m-%d")),
    ))
    response = task_maker.invoke([system_prompt] + state.messages, config=config)

    return Command(
        update={
            "messages": [response],
            "redirect": "dialogue",
            "followup": response.content,
        }, goto="dialogue_tools" if response.tool_calls else "clarification",
    )

def create_task_commit(state: TaskMakerState) -> SubgraphOutputState:
    execute("INSERT INTO public.tasks(project_id, name, description, start, \"end\") VALUES(!p1, !p2, !p3, !p4, !p5)", 
            state.project_id, state.task_name, state.task_desc, state.start_date, state.end_date)

    return {"action": compile_action_data("task_maker", state)}

task_maker_workflow = StateGraph(TaskMakerState, output=SubgraphOutputState)

task_maker_workflow.add_node("clarification", clarify_subgraph_input)
task_maker_workflow.add_node("dialogue", create_task_dialogue)
task_maker_workflow.add_node("dialogue_tools", ToolNode(task_maker_tools))
task_maker_workflow.add_node("commit", create_task_commit)

task_maker_workflow.set_entry_point("dialogue")
task_maker_workflow.add_edge("dialogue_tools", "dialogue")
task_maker_workflow.set_finish_point("commit")

task_maker_agent = task_maker_workflow.compile()

# prompting
TASK_CONTEXT = (
"""
The task you are making belongs to an existing project. To help you further understand this project's 
specific context, here are some key details. Use these to inform your interactions with the user.
- Project Name: {project_name}
- Project Description: {project_desc}
""")

TASK_PARAMS = (
"""
1. project_name: The name of the project that this task belongs to. Must be an existing project.
2. task_name: The name of the task to be created. Cannot be the same as an existing task name in 
    the same project.
3. task_description (OPTIONAL): The description of the task. May involve details like operational
    duties, specific goals for task completion, etc.
4. start_date: The date on which the task is to start in YYYY-MM-DD format.
5. end_date (OPTIONAL): The date on which the task is to be ended in YYYY-MM-DD format.
""")

TASK_INSTR = ("""
1. Determine the name of the project that the user wants to add a new task to. If the project name
    the user provides does not exist, it is considered invalid and you must ask for a new one. 
    After determining the project name, you must fetch the context for this project.
    a. This is a list of all existing projects: {existing_projects}
2. Determine the name of the task to be created. If the task name the user provides already
    exists, it is considered invalid and you must ask for a new one.
    a. This is a list of all existing tasks: {existing_tasks}
3. Prompt the user for a task description. It is permissible that they do not provide one.
4. Determine the start date of the task to be created. If the user does not explicitly provide
    one, assume that today's date ({today}) is the start date.
5. Prompt the user for an end date for the task. It is permissible that they do not provide one.
    They may also provide one in terms relative to today. In this case, do your best to estimate
    their intended end date and confirm with them that you have the correct date.
6. Present the information you have to the user to confirm that it is correct. Once any necessary
    adjustments have been made, you shall end this task creation function.
7. Throughout the conversation, the user may either implicitly or explicitly make clear that they want
    to stop this task creation function and instead choose another project management function. If so,
    you shall cancel this task creation function.
""")