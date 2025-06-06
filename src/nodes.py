from typing import Annotated, Literal
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState, ToolNode
from langgraph.types import Command, interrupt
from states import OutputState, ProjectState

model = ChatOllama(model="qwen3:8b")

@tool
def analyze_budget(state: Annotated[ProjectState, InjectedState]) -> str:
    """Extract budget information about the user's project from the conversation history stored in the state."""
    system_prompt = SystemMessage(
        """
        You are an expert in the field of project budget management. You are currently helping to develop a project plan.
        Read the given history of messages and provide a succinct but detailed summary of only the information pertaining to the project's budget.
        This may include details such as the overall budget, individual expenses, subscriptions, and other related information.
        """
    )
    response = model.invoke([system_prompt] + state["messages"])

    return response.content

@tool
def analyze_timeline(state: Annotated[ProjectState, InjectedState]) -> str:
    """Extract timeline information about the user's project from the conversation history stored in the state."""
    system_prompt = SystemMessage(
        """
        You are an expert in the field of project timeline management. You are currently helping to develop a project plan.
        Read the given history of messages and provide a succinct but detailed summary of only the information pertaining to the project's timeline.
        This may include details such as the overall schedule, specific deliverables, and other related information.
        """
    )
    response = model.invoke([system_prompt] + state["messages"])

    return response.content

@tool
def analyze_scope(state: Annotated[ProjectState, InjectedState]) -> str:
    """Extract scope information about the user's project from the conversation history stored in the state."""
    system_prompt = SystemMessage(
        """
        You are an expert in the field of project scope management. You are currently helping to develop a project plan.
        Read the given history of messages and provide a succinct but detailed summary of only the information pertaining to the project's scope.
        This may include details such as the project's title, description, methodology, goals, and other related information.
        """
    )
    response = model.invoke([system_prompt] + state["messages"])

    return response.content

class ClarificationResponse(BaseModel):
    clarify: bool = Field(description="A boolean value of True if additional clarification is necessary and False if not.")
    followup: str = Field(description="A followup question that asks the user for the needed clarification if necessary.")

tools = [analyze_budget, analyze_timeline, analyze_scope]
tools_by_name = {tool.name: tool for tool in tools}
model_with_tools = model.bind_tools(tools)
model_with_structure = model.with_structured_output(ClarificationResponse)

def contact_user(state: ProjectState, config: RunnableConfig) -> Command[Literal["manager", "clarification"]]:
    system_prompt = SystemMessage(
        """
        You are a friendly but professional AI liaison responsible for getting information about upcoming business projects from users.

        Given a user's description of their project, determine whether you have the necessary information about the following factors:
        1. Scope, including the project's title and a description of its purpose and methodology.
        2. Budget, including overall spending and potentially the individual expenses if the user has access to them.
        3. Timeline, including an overall schedule and potentially specific deliverables if the user has access to them.

        Determine if additional clarification is required and, if so, ask followup questions to learn more about the project. If not, leave the followup blank.
        Prompt the user for information in all three categories to create a fuller and more comprehensive project plan. 
        However, ask only one or two followup questions at a time to avoid overwhelming the user.
        """
    )
    response = model_with_structure.invoke([system_prompt] + state["messages"], config)

    goto = "clarification" if response.clarify else "manager"
        
    return Command(
        update={"messages": [AIMessage(response.followup)]} if response.followup else {}, 
        goto=goto
    )

def clarify_input(state: ProjectState) -> ProjectState:
    answer = interrupt(state["messages"][-1].content)

    return {"messages": [HumanMessage(answer)]}

def extract_from_input(state: ProjectState, config: RunnableConfig) -> ProjectState:
    system_prompt = SystemMessage(
        """
        You are a capable and efficient project manager. 
        Given a history of conversation with a user about their project, extract and isolate information pertaining to the project's budget, scope, and timeline.
        If you lack information on one of these three factors, do not call its associated tool. Do not provide any of your own arguments to the tools.
        """
    )
    response = model_with_tools.invoke([system_prompt] + state["messages"], config)

    return {"messages": [response]}

def tool_node():
    return ToolNode([analyze_budget, analyze_scope, analyze_timeline])

def assemble_plan(state: ProjectState) -> OutputState:
    return {"project_plan": state["scope_info"] + state["timeline_info"] + state["budget_info"]}

def should_continue(state: ProjectState):
    if state["messages"][-1].tool_calls:
        return "tools"
    else:
        return "assembly"