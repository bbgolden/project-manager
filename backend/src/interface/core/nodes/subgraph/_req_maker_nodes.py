from typing import Literal, Annotated
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from langgraph.graph import StateGraph
from interface.config import model
from interface.core.schemas import ReqMakerState, OutputState
from interface.utils._db_utils import execute, select
from interface.utils._agent_utils import clarify_subgraph_input

@tool
def get_requirement_context(tool_call_id: Annotated[str, InjectedToolCallId], project_name: str):
    """Retrieves necessary context for the project that the new requirement belongs to."""
    existing_projects = [project for project, in select("SELECT name FROM public.projects")]
    if project_name not in existing_projects:
        raise ValueError(f"Project with name {project_name} does not exist. Please enter a valid project. Existing projects are: {", ".join(existing_projects)}.")
    
    project_desc = select("SELECT description FROM public.projects WHERE name = !p1", project_name)[0][0]

    return Command(update={
        "messages": [ToolMessage(f"New requirement belongs to project with (name: {project_name}) and (description: {project_desc})", tool_call_id=tool_call_id)],
        "existing_projects": existing_projects,
        "project_name": project_name,
        "project_desc": project_desc,
    })

@tool
def add_requirement(
    current_project_name: Annotated[str, InjectedState("project_name")],
    current_description: Annotated[str, InjectedState("req_desc")],
    tool_call_id: Annotated[str, InjectedToolCallId], 
    project_name: str, 
    description: str,
):
    """Loads provided information into a new requirement to be created."""
    vproject_name = project_name if project_name else current_project_name
    vdescription = description if description else current_description

    return Command(update={
        "messages": [ToolMessage(f"Updated parent project to: {vproject_name}.\nUpdated description to: {vdescription}", tool_call_id=tool_call_id)],
        "project_name": vproject_name,
        "req_desc": vdescription,
    })

@tool
def finish_execution(tool_call_id: Annotated[str, InjectedToolCallId]):
    """Finishes execution of the current portion of the requirement creation dialogue."""
    return Command(update={
        "messages": [ToolMessage(f"Execution of current node complete. Moving to next node.", tool_call_id=tool_call_id)],
        "finish": True,
    })

context_builder_tools = [get_requirement_context]
context_builder = model.bind_tools(context_builder_tools)

req_maker_tools = [add_requirement, finish_execution]
req_maker = model.bind_tools(req_maker_tools)

def create_req_context(state: ReqMakerState, config: RunnableConfig) -> Command[Literal["clarification", "context_tools", "dialogue"]]:
    if state["project_name"] and state["project_name"] in state["existing_projects"]:
        return Command(goto="dialogue")

    system_prompt = SystemMessage(
        """
        You are in a direct dialogue with the user helping them to add a requirement to an existing project.
        Speak in the second person, as if in conversation with the user.
        Your only job is to identify the name of the project that the requirement belongs to.
        This job is internal to the application and should not be mentioned to the user.

        The project name that the user enters must be an existing project.
        Ask the user for a new project name if they enter one that does not exist. The new name is the one you should refer to at all times.

        If the user only mentions that they would like to add a new requirement, you must assume that you do not yet have the project name.

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

def create_req_dialogue(state: ReqMakerState, config: RunnableConfig) -> Command[Literal["clarification", "dialogue_tools", "commit"]]:
    if state["finish"]:
        return Command(goto="commit")
    
    system_prompt = SystemMessage(
        f"""
        You are in a direct dialogue with the user, helping them to add a new requirement to a project as part of a project management application.
        Speak in the second person, as if in conversation with the user.
        A requirement is defined as a condition or capability that must be fulfilled for a project to be considered successful.
        A requirement has a description (required).
        The requirement you are currently creating belongs to a parent project called {state["project_name"]}.
        This project has the following description (note that this is not the requirement description): {state["project_desc"]}

        Using your knowledge of the requirement's parent project, help the user to add the requirement.
        You must not add any details that the user does not explicitly mention, such as specific names.

        The requirement description must be formatted as a properly capitalized and punctuated paragraph that could be read without additional context. It should be in the third-person.

        Once you have confirmed that the requirement has been added, finish execution.
        Do not ask any followup questions at this point.
        You are not permitted to tell the user that the requirement has been added. You may only provide the information you have and ask for confirmation that it is correct.
        """
    )
    response = req_maker.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "messages": [response],
            "redirect": "dialogue",
            "followup": response.content,
        }, goto="dialogue_tools" if response.tool_calls else "clarification",
    )

def create_req_commit(state: ReqMakerState) -> OutputState:
    project_id = select("SELECT project_id FROM public.projects WHERE name = !p1", state["project_name"])[0][0]

    execute("INSERT INTO public.requirements(project_id, description) VALUES(!p1, !p2)", project_id, state["req_desc"])

    return {"output": f"New requirement added with\nName: {state["project_name"]}\nDescription: {state["req_desc"]}"}

req_maker_workflow = StateGraph(ReqMakerState, output=OutputState)

req_maker_workflow.add_node("clarification", clarify_subgraph_input)
req_maker_workflow.add_node("context", create_req_context)
req_maker_workflow.add_node("context_tools", ToolNode(context_builder_tools))
req_maker_workflow.add_node("dialogue", create_req_dialogue)
req_maker_workflow.add_node("dialogue_tools", ToolNode(req_maker_tools))
req_maker_workflow.add_node("commit", create_req_commit)

req_maker_workflow.set_entry_point("context")
req_maker_workflow.add_edge("context_tools", "context")
req_maker_workflow.add_edge("dialogue_tools", "dialogue")
req_maker_workflow.set_finish_point("commit")

req_maker_agent = req_maker_workflow.compile()