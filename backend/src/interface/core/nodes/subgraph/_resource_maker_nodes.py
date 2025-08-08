from typing import Literal, Annotated
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from langgraph.graph import StateGraph
from interface.config import model
from interface.core.schemas import ResourceMakerState, SubgraphOutputState
from interface.utils._db_utils import execute, select
from interface.utils._agent_utils import clarify_subgraph_input, compile_action_data

@tool
def add_resource(
    existing_contacts: Annotated[list[str], InjectedState("existing_contacts")],
    current_first_name: Annotated[str, InjectedState("first_name")],
    current_last_name: Annotated[str, InjectedState("last_name")],
    current_contact: Annotated[str, InjectedState("contact")],
    tool_call_id: Annotated[str, InjectedToolCallId],
    first_name: str,
    last_name: str,
    contact: str,
):
    """Loads provided first name, last name, and contact into a new resource to be created."""
    vfirst_name = first_name if first_name else current_first_name
    vlast_name =  last_name if last_name else current_last_name
    vcontact = contact if contact else current_contact

    if vcontact in existing_contacts:
        raise ValueError(f"Resource with contact {vcontact} already exists. Please enter a valid contact.")
    
    return Command(update={
        "messages": [ToolMessage(
            f"""
            Updated first name to: {vfirst_name}
            Updated last name to: {vlast_name}
            Updated contact to: {vcontact}
            """, tool_call_id=tool_call_id)],
        "first_name": vfirst_name,
        "last_name": vlast_name,
        "contact": vcontact,
    })

@tool
def finish_execution(tool_call_id: Annotated[str, InjectedToolCallId]):
    """Finishes execution of the current portion of the resource creation dialogue."""
    return Command(update={
        "messages": [ToolMessage(f"Execution of current node complete. Moving to next node.", tool_call_id=tool_call_id)],
        "finish": True,
    })

resource_maker_tools = [add_resource, finish_execution]
resource_maker = model.bind_tools(resource_maker_tools)

def create_resource_context(state: ResourceMakerState) -> ResourceMakerState:
    existing_contacts = [contact for contact, in select("SELECT contact FROM public.resources")]

    return {"existing_contacts": existing_contacts}

def create_resource_dialogue(state: ResourceMakerState, config: RunnableConfig) -> Command[Literal["clarification", "dialogue_tools", "commit"]]:
    if state["finish"]:
        return Command(goto="commit")
    
    system_prompt = SystemMessage(
        """
        You are in a direct dialogue with the user, helping them to add a new resource to a project as part of a project management application.
        Speak in the second person, as if in conversation with the user.
        A resource is defined as an individual who contributes to a project by completing tasks within the project.
        A resource has a first name (required), last name (optional), and contact (required)

        Using your knowledge of what a resource is, help the user to add the new resource.
        You must not add any details that the user does not explicitly mention, such as specific names.

        The resource's first name must be properly capitalized as a proper noun.
        The resource's last name must be properly capitalized as a proper noun. You must ask the user for the resource's last name, but it is permissible that they do not provide it.
        The resource's contact should preferably be an email but can be any means of communication.
        The resource's contact cannot be the same as any existing resources' contacts.
        Ask the user for a new contact if they enter one that exists already. This is the one you should refer to at all times.

        Once you have confirmed that the resource has been added, finish execution.
        Do not ask any followup questions at this point.
        You are not permitted to tell the user that the resource has been added. You may only provide the information you have and ask for confirmation that it is correct.
        """
    )
    response = resource_maker.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "messages": [response],
            "redirect": "dialogue",
            "followup": response.content,
        }, goto="dialogue_tools" if response.tool_calls else "clarification",
    )

def create_resource_commit(state: ResourceMakerState) -> SubgraphOutputState:
    execute("INSERT INTO public.resources(first_name, last_name, contact) VALUES(!p1, !p2, !p3)", state["first_name"], state["last_name"], state["contact"])

    return {"action": compile_action_data("resource_maker", state)}

resource_maker_workflow = StateGraph(ResourceMakerState, output=SubgraphOutputState)

resource_maker_workflow.add_node("clarification", clarify_subgraph_input)
resource_maker_workflow.add_node("context", create_resource_context)
resource_maker_workflow.add_node("dialogue", create_resource_dialogue)
resource_maker_workflow.add_node("dialogue_tools", ToolNode(resource_maker_tools))
resource_maker_workflow.add_node("commit", create_resource_commit)

resource_maker_workflow.set_entry_point("context")
resource_maker_workflow.add_edge("context", "dialogue")
resource_maker_workflow.add_edge("dialogue_tools", "dialogue")
resource_maker_workflow.set_finish_point("commit")

resource_maker_agent = resource_maker_workflow.compile()