from collections import namedtuple
from typing import Literal, Annotated
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from langgraph.graph import StateGraph
from interface.config import model
from interface.core.schemas import ResourceAssignerState, OutputState
from interface.utils._db_utils import execute, select
from interface.utils._agent_utils import clarify_subgraph_input

@tool
def get_resource_assignment_context(
    current_first_name: Annotated[str, InjectedState("re_first_name")],
    current_last_name: Annotated[str, InjectedState("re_last_name")],
    tool_call_id: Annotated[str, InjectedToolCallId], 
    first_name: str, 
    last_name: str,
):
    """Retrieves necessary context for the assignment of an existing resource."""
    existing_tasks = [task for task, in select("SELECT name FROM public.tasks")]
    vfirst_name = first_name if first_name else current_first_name
    vlast_name = last_name if last_name else current_last_name

    if vlast_name:
        query_results = select("SELECT first_name, last_name, contact FROM public.resources WHERE first_name = !p1 and last_name = !p2", vfirst_name, vlast_name)
    else:
        query_results = select("SELECT first_name, last_name, contact FROM public.resources WHERE first_name = !p1 and last_name IS NULL", vfirst_name)

    matching_resources = [re_info for re_info in query_results]
    if not matching_resources:
        raise ValueError(f"No resources with first name {vfirst_name} and last name {vlast_name} exist. Please enter valid resource information.")

    return Command(update={
        "messages": [ToolMessage(f"Resource has first name {vfirst_name} and last name {vlast_name}", tool_call_id=tool_call_id)],
        "existing_tasks": existing_tasks,
        "matching_resources": matching_resources,
        "re_first_name": vfirst_name,
        "re_last_name": vlast_name,
    })
    
@tool
def assign_resource(
    existing_tasks: Annotated[list[str], InjectedState("existing_tasks")],
    current_task_name: Annotated[str, InjectedState("task_name")],
    current_resource_contact: Annotated[str, InjectedState("re_contact")],
    tool_call_id: Annotated[str, InjectedToolCallId],
    task_name: str,
    resource_contact: str,
):
    """Loads provided information into the assignment of a new resource."""
    vtask_name = task_name if task_name else current_task_name
    vresource_contact = resource_contact if resource_contact else current_resource_contact

    if vtask_name not in existing_tasks:
        raise ValueError(f"Task with name {vtask_name} does not exist. Please enter a valid task. Existing tasks are {", ".join(existing_tasks)}")
    
    task_id = select("SELECT task_id FROM public.tasks WHERE name = !p1", vtask_name)[0][0]
    resource_id = select("SELECT resource_id FROM public.resources WHERE contact = !p1", vresource_contact)[0][0]
    if select("SELECT * FROM public.resource_assignments WHERE task_id = !p1 and resource_id = !p2", task_id, resource_id):
        raise ValueError(f"Resource with contact {vresource_contact} has already been assigned to task {vtask_name}. Please enter a valid assignment.")
    
    return Command(update={
        "messages": [ToolMessage(f"Updated task name to: {vtask_name}\nUpdated contact to: {vresource_contact}", tool_call_id=tool_call_id)],
        "task_name": vtask_name,
        "re_contact": vresource_contact,
    })

@tool
def finish_execution(tool_call_id: Annotated[str, InjectedToolCallId]):
    """Finishes execution of the current portion of the resource assignment dialogue."""
    return Command(update={
        "messages": [ToolMessage(f"Execution of current node complete. Moving to next node.", tool_call_id=tool_call_id)],
        "finish": True,
    })

context_builder_tools = [get_resource_assignment_context]
context_builder = model.bind_tools(context_builder_tools)

resource_assigner_tools = [assign_resource, finish_execution]
resource_assigner = model.bind_tools(resource_assigner_tools)

def create_resource_assignment_context(state: ResourceAssignerState, config: RunnableConfig) -> Command[Literal["clarification", "context_tools", "dialogue"]]:
    if state["matching_resources"]:
        return Command(goto="dialogue")
    
    system_prompt = SystemMessage(
        """
        You are in a direct dialogue with the user helping them to assign a resource to a task as part of a project management application.
        Speak in the second person, as if in conversation with the user.
        A resource is defined as a person with a first and optionally last name.
        Your only job is to identify the first name and, if present, last name of the resource the user wants to assign.
        This job is internal to the application and should not be mentioned to the user.

        The first and last names provided must belong to an existing resource.
        Ask the user for a new first and/or last name if they enter ones that do not exist. The new names are the ones you should refer to at all times.
        Do not use any names that the user does not explicitly mention (e.g. placeholders like John Doe or Jane Doe).

        If the user only mentions that they would like to assign a resource, you must assume that you do not yet have the resource's name.

        Once you have gathered the correct resource first and last name, finish execution. 
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

def create_resource_assignment_dialogue(state: ResourceAssignerState, config: RunnableConfig) -> Command[Literal["clarification", "dialogue_tools", "commit"]]:
    if state["finish"]:
        return Command(goto="commit")
    
    Resource = namedtuple("Resource", ["first_name", "last_name", "contact"])

    system_prompt = SystemMessage(
        f"""
        You are in a direct dialogue with the user, helping them to assign a new resource to a task in a project as part of a project management application.
        Speak in the second person, as if in conversation with the user.
        A resource is defined as an individual who contributes to a project by completing tasks within the project.

        The following list contains information on the resources that match the name of the resource that the user would like to assign:
        {", ".join([str(Resource(*re)) for re in state["matching_resources"]])}
        Provide this information to the user and ask them which resource is the correct one that they wish to assign.
        Then, help the user to assign this resource to the appropriate task.

        The task to which the resource is assigned must be an existing task.
        Ask the user for a new task name if they enter one which does not exist. This is the one you should refer to at all times. 

        Once you have confirmed that the resource has been assigned, finish execution.
        Do not ask any followup questions at this point.
        You are not permitted to tell the user that the resource has been assigned. You may only provide the information you have and ask for confirmation that it is correct.
        """
    )
    response = resource_assigner.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "messages": [response],
            "redirect": "dialogue",
            "followup": response.content,
        }, goto="dialogue_tools" if response.tool_calls else "clarification",
    )

def create_resource_assignment_commit(state: ResourceAssignerState) -> OutputState:
    task_id = select("SELECT task_id FROM public.tasks WHERE name = !p1", state["task_name"])[0][0]
    resource_id = select("SELECT resource_id FROM public.resources WHERE contact = !p1", state["re_contact"])[0][0]

    execute("INSERT INTO public.resource_assignments(task_id, resource_id) VALUES(!p1, !p2)", task_id, resource_id)

    return {"output": f"Assigned resource with contact {state["re_contact"]} to task with name {state["task_name"]}"}

resource_assigner_workflow = StateGraph(ResourceAssignerState, output=OutputState)

resource_assigner_workflow.add_node("clarification", clarify_subgraph_input)
resource_assigner_workflow.add_node("context", create_resource_assignment_context)
resource_assigner_workflow.add_node("context_tools", ToolNode(context_builder_tools))
resource_assigner_workflow.add_node("dialogue", create_resource_assignment_dialogue)
resource_assigner_workflow.add_node("dialogue_tools", ToolNode(resource_assigner_tools))
resource_assigner_workflow.add_node("commit", create_resource_assignment_commit)

resource_assigner_workflow.set_entry_point("context")
resource_assigner_workflow.add_edge("context_tools", "context")
resource_assigner_workflow.add_edge("dialogue_tools", "dialogue")
resource_assigner_workflow.set_finish_point("commit")

resource_assigner_agent = resource_assigner_workflow.compile()