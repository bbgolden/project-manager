from typing import Literal, Annotated
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from langgraph.graph import StateGraph
from interface.config import model
from interface.core.schemas import AnalystState, OutputState
from interface.utils._db_utils import select
from interface.utils._agent_utils import clarify_subgraph_input, get_invalid_values

VARCHAR_ARR_EMPTY_ARG = ["__none__"]
DATE_ARR_EMPTY_ARG = ["0001-01-01"]

@tool
def get_analysis_context(tool_call_id: Annotated[str, InjectedToolCallId], project_name: str):
    """Retrieves information about the project which the user wants to analyze."""
    existing_projects = [project for project, in select("SELECT name FROM public.projects")]

    if project_name not in existing_projects:
        raise ValueError(f"Project with name {project_name} does not exist. Please enter a valid project.")
    
    project_id, project_desc = select("SELECT project_id, description FROM public.projects WHERE name = !p1", project_name)[0]
    existing_tasks = [task for task, in select("SELECT name FROM public.tasks WHERE project_id = !p1", project_id)]
    existing_resources = [re for re in select(
        """
        SELECT
            resources.first_name,
            resources.last_name,
            resources.contact
        FROM resource_assignments
        LEFT JOIN resources
            ON resources.resource_id = resource_assignments.resource_id
        LEFT JOIN tasks
            ON tasks.task_id = resource_assignments.task_id
        LEFT JOIN projects
            ON tasks.project_id = projects.project_id
        WHERE projects.name = !p1
        """, project_name,
    )]

    return Command(update={
        "messages": [ToolMessage(
            f"""
            The user will be asking for information about the following project.
            Project Name: {project_name}
            Project Description: {project_desc}
            """, tool_call_id=tool_call_id)],
        "existing_tasks": existing_tasks,
        "existing_resources": existing_resources,
        "project_id": project_id,
        "project_name": project_name,
        "project_desc": project_desc,
    })

@tool
def get_project_requirements(
    project_id: Annotated[int, InjectedState("project_id")],
) -> str:
    """Retrieves all requirements for the current project."""
    reqs = [req for req, in select("SELECT description FROM public.requirements WHERE project_id = !p1", project_id)]

    return "These are all requirements belonging to the current project:\n" + "\n".join(reqs)

@tool
def get_tasks(
    existing_tasks: Annotated[list[str], InjectedState("existing_tasks")],
    project_id: Annotated[int, InjectedState("project_id")],
    task_names: list[str] = [], 
    start_dates: list[str] = [], 
    end_dates: list[str] = [],
) -> str:
    "Retrieves all tasks that match the specified conditions."
    vtask_names = [task for task in task_names if task]
    vstart_dates = [start for start in start_dates if start]
    vend_dates = [end for end in end_dates if end]

    invalid_tasks = get_invalid_values(vtask_names, existing_tasks)
    if invalid_tasks:
        raise ValueError(f"The following tasks do not exist in the current project: {", ".join(invalid_tasks)}. Please enter valid tasks.")
    
    matching_task_info = [{
        "Task Name": name,
        "Task Description": desc,
        "Start Date": start,
        "End Date": end,
    } for name, desc, start, end in select(
        f"""
        SELECT name, description, start, \"end\" 
        FROM public.tasks 
        WHERE
            project_id = !p1
            AND name {"=" if vtask_names else "!="} ANY(ARRAY[!p2]::varchar[])
            AND start {"=" if vstart_dates else "!="} ANY(ARRAY[!p3]::date[])
            AND (\"end\" {"=" if vend_dates else "!="} ANY(ARRAY[!p4]::date[]) OR \"end\" IS NULL)
        """, project_id, vtask_names + VARCHAR_ARR_EMPTY_ARG, vstart_dates + DATE_ARR_EMPTY_ARG, vend_dates + DATE_ARR_EMPTY_ARG,
    )]

    return "These are all tasks in the current project that match the user's request:\n" + "\n".join([str(task) for task in matching_task_info])

@tool
def get_dependent_tasks(
    existing_tasks: Annotated[int, InjectedState("existing_tasks")],
    project_id: Annotated[int, InjectedState("project_id")],
    independent_task_names: list[str] = [], 
    dependent_task_names: list[str] = [],
) -> str:
    """Retrieves tasks dependent on the provided one or tasks that the provided one depends on."""
    vindependent_task_names = [task for task in independent_task_names if task]
    vdependent_task_names = [task for task in dependent_task_names if task]

    invalid_tasks = get_invalid_values(vindependent_task_names + vdependent_task_names, existing_tasks)
    if invalid_tasks:
        raise ValueError(f"The following tasks do not exist in the current project: {", ".join(invalid_tasks)}. Please enter valid tasks.")
    
    matching_dependency_info = [{
        "Independent Task Name": itask_name,
        "Independent Task Description": itask_desc,
        "Independent Task Start Date": itask_start,
        "Independent Task End Date": itask_end,
        "Dependent Task Name": dtask_name,
        "Dependent Task Description": dtask_desc,
        "Dependent Task Start Date": dtask_start,
        "Dependent Task End Date": dtask_end,
        "Dependency Description": dep_desc,
    } for itask_name, itask_desc, itask_start, itask_end, dtask_name, dtask_desc, dtask_start, dtask_end, dep_desc in select(
        f"""
        SELECT
            itasks.name AS itask_name,
            itasks.description AS itask_desc,
            itasks.start AS itask_start,
            itasks.end AS itask_end,
            dtasks.name AS dtask_name,
            dtasks.description AS dtask_desc,
            dtasks.start AS dtask_start,
            dtasks.end AS dtask_end,
            task_dependencies.description AS dep_desc
        FROM task_dependencies
        LEFT JOIN tasks AS itasks
            ON itasks.task_id = task_dependencies.task_id
        LEFT JOIN tasks AS dtasks
            ON dtasks.task_id = task_dependencies.dependent_id
        WHERE
            itasks.project_id = !p1,
            AND dtasks.project_id = !p1,
            AND itask_name {"=" if vindependent_task_names else "!="} ANY(ARRAY[!p2]::varchar[])
            AND dtask_name {"=" if vdependent_task_names else "!="} ANY(ARRAY[!p3]::varchar[])
        """, project_id, vindependent_task_names + VARCHAR_ARR_EMPTY_ARG, vdependent_task_names + VARCHAR_ARR_EMPTY_ARG,
    )]

    return "These are all task dependencies in the current project that match the user's request:\n"+ "\n".join([str(dep) for dep in matching_dependency_info])

@tool
def get_all_resources() -> str:
    """Retrieves all existing resources, including those that have not been assigned to tasks."""
    res = [{
        "First Name": first,
        "Last Name": last,
        "Contact": contact,
    } for first, last, contact in select("SELECT first_name, last_name, contact FROM public.resources")]

    return "These are all resources that have been created thus far:\n" + "\n".join([str(re) for re in res])

@tool
def get_resources_by_assignment(
    existing_tasks: Annotated[list[str], InjectedState("existing_tasks")],
    existing_resources: Annotated[list[tuple[str, str | None, str]], InjectedState("existing_resources")],
    task_names: list[str] = [],
    resource_first_names: list[str] = [],
    resource_last_names: list[str] = [],
    resource_contacts: list[str] = [],
) -> str:
    """Retrieves all resource assignments that belong to the provided tasks and fit the provided arguments"""
    vtask_names = [task for task in task_names if task]

    invalid_tasks = get_invalid_values(vtask_names, existing_tasks)
    if invalid_tasks:
        raise ValueError(f"The following tasks do not exist in the current project: {", ".join(invalid_tasks)}. Please enter valid tasks.")

    matching_re_info = [{
        "First Name": first,
        "Last Name": last,
        "Contact": contact,
        "Task": task,
        "Task Description": desc,
        "Start Date": start,
        "End Date": end,
    } for first, last, contact, task , desc, start, end in select(
        f"""
        SELECT
            resources.first_name,
            resources.last_name,
            resources.contact,
            tasks.name AS task_name,
            tasks.description AS task_desc,
            tasks.start,
            tasks.end
        FROM public.resource_assignments
        LEFT JOIN resources
            ON resources.resource_id = resource_assignments.resource_id
        LEFT JOIN tasks
            ON tasks.task_id = resource_assignments.task_id
        WHERE
            tasks.name {"=" if task_names else "!="} ANY(ARRAY[!p1]::varchar[])
            AND first_name {"=" if resource_first_names else "!="} ANY(ARRAY[!p2]::varchar[])
            AND (last_name {"=" if resource_last_names else "!="} ANY(ARRAY[!p3]::varchar[]) OR last_name IS NULL)
            AND contact {"=" if resource_contacts else "!="} ANY(ARRAY[!p4]::varchar[])
        """, vtask_names + VARCHAR_ARR_EMPTY_ARG, resource_first_names + VARCHAR_ARR_EMPTY_ARG, resource_last_names + VARCHAR_ARR_EMPTY_ARG, resource_contacts + VARCHAR_ARR_EMPTY_ARG,
    )]

    return "These are all resource assignments that match the user's request:\n" + "\n".join([str(re) for re in matching_re_info])

@tool
def finish_execution(tool_call_id: Annotated[str, InjectedToolCallId]):
    """Finishes execution of the current portion of the analysis dialogue."""
    return Command(update={
        "messages": [ToolMessage(f"Execution of current node complete. Moving to next node.", tool_call_id=tool_call_id)],
        "finish": True,
    })

context_builder_tools = [get_analysis_context]
context_builder = model.bind_tools(context_builder_tools)

analyst_tools = [get_project_requirements, get_tasks, get_dependent_tasks, get_all_resources, get_resources_by_assignment, finish_execution]
analyst = model.bind_tools(analyst_tools)

def analysis_context(state: AnalystState, config: RunnableConfig) -> Command[Literal["clarification", "context_tools", "dialogue"]]:
    if state["project_name"]:
        return Command(goto="dialogue")
    
    system_prompt = SystemMessage(
        """
        You are in a direct dialogue with the user, preparing to answer their questions about one of their projects in a project management application.
        Speak in the second person, as if in conversation with the user.
        Your only job is to identify the name of the project that the user wants to analyze.
        This job is internal to the application and should not be mentioned to the user.

        The project name that the user enters must be an existing project.
        Ask the user for a new project name if they enter one that does not exist. The new name is the one you should refer to at all times.

        If the user only mentions that they would like to ask questions/analyze the project, you must assume that you do not yet have the project name.

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

def analysis_dialogue(state: AnalystState, config: RunnableConfig) -> Command[Literal["clarification", "dialogue_tools", "__end__"]]:
    if state["finish"]:
        return Command(
            update={"output": "Finished analysis"},
            goto="__end__",
        )
    
    system_prompt = SystemMessage(
        """
        You are in a direct dialogue with the user, preparing to answer their questions about one of their projects in a project management application.
        Speak in the second person, as if in conversation with the user.

        Use the tools at your disposal to retrieve information about the project and answer the user's questions.
        If the user asks for an analysis, use your best insight and offer an answer to their request.
        When retrieving information about the project, only use search arguments that the user has explicitly stated.
        Do not come up with your own arguments (e.g. task names, resource names, etc.)

        If the user does not specify values for a parameter (e.g. they do not mention any task names when searching for tasks), do not pass an argument to that parameter.

        Once the user has made it clear that they want to ask no more questions, finish execution.
        Do not ask any followup questions past this point.
        """
    )
    response = analyst.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "messages": [response],
            "redirect": "dialogue",
            "followup": response.content,
        }, goto="dialogue_tools" if response.tool_calls else "clarification",
    )

analyst_workflow = StateGraph(AnalystState, output=OutputState)

analyst_workflow.add_node("clarification", clarify_subgraph_input)
analyst_workflow.add_node("context", analysis_context)
analyst_workflow.add_node("context_tools", ToolNode(context_builder_tools))
analyst_workflow.add_node("dialogue", analysis_dialogue)
analyst_workflow.add_node("dialogue_tools", ToolNode(analyst_tools))

analyst_workflow.set_entry_point("context")
analyst_workflow.add_edge("context_tools", "context")
analyst_workflow.add_edge("dialogue_tools", "dialogue")

analyst_agent = analyst_workflow.compile()