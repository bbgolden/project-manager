from typing import Literal
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, interrupt
from interface.config import model
from interface.core.schemas import RouterSchema, DialogueSchema, OverallState
from interface.core.nodes.subgraph._project_maker_nodes import project_maker_agent
from interface.core.nodes.subgraph._req_maker_nodes import req_maker_agent
from interface.core.nodes.subgraph._task_maker_nodes import task_maker_agent
from interface.core.nodes.subgraph._dep_maker_nodes import dep_maker_agent
from interface.core.nodes.subgraph._resource_maker_nodes import resource_maker_agent
from interface.core.nodes.subgraph._resource_assigner_nodes import resource_assigner_agent
from interface.core.nodes.subgraph._analyst_nodes import analyst_agent

queue_builder = model.with_structured_output(RouterSchema)
directional_manager = model.with_structured_output(DialogueSchema)

# Threshold for "unvaluable" response from agents (characters)
value_thresh = 30
tool_to_direction = {
        "add_project": "project_maker",
        "add_requirement": "req_maker",
        "add_task": "task_maker",
        "add_task_dependency": "dep_maker",
        "add_resource": "resource_maker",
        "assign_resource": "resource_assigner",
        "analyze_project": "analyst",
}

def assign_workflow(state: OverallState, config: RunnableConfig) -> Command[Literal["supervisor", "clarification"]]:
    new_messages = [HumanMessage(state["user_input"])]

    system_prompt = SystemMessage(
        """
        You are an AI that determines which project management functions the user wants to utilize and how many times they wish to utilize each function.
        This does not refer to external function, but rather internal ones like creating a project, adding tasks, etc.
        Do not explicitly ask the user for which functions they would like to use. It is your job to inference that information from their messages.
        The following are functions the user may want to use . They are each distinct and should be treated as such.

        Adding a new project
        Adding a new requirement to a project
        Adding a new task
        Adding a new task dependency
        Adding a new resource
        Assigning a resource
        Asking questions about/analyzing the project

        Based on the user's request, return the appropriate number of function calls for each function at your disposal.
        If and only if you cannot understand the user's request, return a followup question (in the form of a comprehensible sentence) that respectfully asks the user to give a different request.
        """
    )
    response = queue_builder.invoke([system_prompt] + state["messages"] + new_messages, config=config).model_dump()

    if len(response["followup"]) > value_thresh:
        new_messages.append(AIMessage(response["followup"]))

    tool_queue = list[str]()
    for tool, direction in tool_to_direction.items():
        tool_queue.extend([direction] * response[tool])

    return Command(
        update={
            "messages": new_messages,
            "tool_queue": tool_queue,
            "prev": "liaison",
            "followup": response["followup"],
        }, goto="clarification" if len(response["followup"]) > value_thresh else "supervisor",
    )

def direct_workflow(state: OverallState) -> Command[Literal["project_maker", "req_maker", "task_maker", "dep_maker", "resource_maker", "resource_assigner", "analyst", "suggestion_commit"]]:
    return Command(
        update={"tool_queue": state["tool_queue"][1:]},
        goto=state["tool_queue"][0] if state["tool_queue"] else "suggestion_commit",
    )

def clarify_input(state: OverallState) -> Command[Literal["liaison", "suggestion_commit"]]:
    new_request = interrupt(state["followup"])

    return Command(
        update={"user_input": new_request} if state["prev"] == "liaison" else {"messages": [AIMessage(state["followup"]), HumanMessage(new_request)]},
        goto=state["prev"],
    )

def create_project(state: OverallState) -> OverallState:
    response = project_maker_agent.invoke({
        "messages": state["messages"],
        "project_name": "",
        "project_desc": "",
        "finish": False,
    })

    return {
        "messages": [AIMessage(response["output"])],
        "prev": "adding a new project",
    }

def create_req(state: OverallState) -> OverallState:
    response = req_maker_agent.invoke({
        "messages": state["messages"],
        "project_name": "",
        "req_desc": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "adding a new requirement",
    }

def create_task(state: OverallState) -> OverallState:
    response = task_maker_agent.invoke({
        "messages": state["messages"],
        "project_name": "",
        "task_name": "",
        "task_desc": "",
        "start_date": "",
        "end_date": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "adding a new task",
    }

def create_dep(state: OverallState) -> OverallState:
    response = dep_maker_agent.invoke({
        "messages": state["messages"],
        "task1_name": "",
        "task2_name": "",
        "dep_desc": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "adding a new task dependency",
    }

def create_resource(state: OverallState) -> OverallState:
    response = resource_maker_agent.invoke({
        "messages": state["messages"],
        "first_name": "",
        "last_name": "",
        "contact": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "adding a new resource",
    }

def assign_resource(state: OverallState) -> OverallState:
    response = resource_assigner_agent.invoke({
        "messages": state["messages"],
        "matching_resources": [],
        "task_name": "",
        "re_first_name": "",
        "re_last_name": "",
        "re_contact": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "assigning a resource",
    }

def analyze_project(state: OverallState) -> OverallState:
    response = analyst_agent.invoke({
        "messages": state["messages"],
        "project_name": "",
        "finish": False,
    })

    return {
        "messages": AIMessage(response["output"]),
        "prev": "asking questions about/analyzing the project",
    }

def suggest_next(state: OverallState, config: RunnableConfig) -> Command[Literal["clarification", "supervisor"]]:
    system_prompt = SystemMessage(
        f"""
        You are helping the user to create and manage their projects as part of a project management software.
        Your task is to recommend the use of a secondary project management function based on the most recent one that the user has utilized.
        The following are existing project management functions and which recommendations to offer in each case.

        Adding a new project: recommended secondary functions are adding a new requirement
        Adding a new requirement: recommended secondary functions are adding another requirement
        Adding a new task: recommended secondary functions are adding a new task dependency, adding a new resource, and assigning a resource to that task
        Adding a new task dependency: recommended secondary functions are adding another task dependency
        Adding a new resource: recommended secondary functions are assigning that resource to a task
        Assigning a resource: recommended secondary functions are adding a new resource
        Asking questions about/analyzing the project: there are no recommended secondary functions

        The user's most recently used function is {state["prev"]}
        Take into consideration this information, recent message context, and the above list.
        Also consider any questions asked in the AI message after the latest tool call.
        Return a followup question using these factors that respectfully asks the user whether they would like to utilize an appropriate secondary function.
        Ensure that the question is formatted as a proper sentence.
        """
    )
    response = directional_manager.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "prev": "suggestion_commit", 
            "followup": response.followup,
        }, goto="clarification" if len(response.followup) > value_thresh else "supervisor",
    )

def suggest_commit(state: OverallState, config: RunnableConfig) -> OverallState:
    system_prompt = SystemMessage(
        """
        You are helping the user to create and manage their projects as part of a project management software.
        Your task is to recommend the use of a secondary project management function based on the most recent one that the user has utilized.

        Examine the provided messages and context to determine which project functions the user would like to use and how many of each.
        Based on the user's response to the AI-prompted question, return the appropriate number of calls for each function at your disposal.
        Remember that it is possible that the user may not wish to use any tools at all.

        If the user's response is negative, assume that they do not wish to add any tools.
        """
    )
    response = queue_builder.invoke([system_prompt] + state["messages"][-2:], config=config).model_dump()

    new_tools = list[str]()
    for tool, direction in tool_to_direction.items():
        new_tools.extend([direction] * response[tool])

    return {
        "tool_queue": new_tools + state["tool_queue"], 
        "output": "New tools added: " + (", ".join(new_tools) if new_tools else "None"),
    }

def should_finish(state: OverallState) -> Literal["loop", "end"]:
    if state["tool_queue"]:
        return "loop"
    return "end"