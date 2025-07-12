from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt
from .states import OverallState, OutputState
from libs.database import execute, select

model = ChatOllama(model="llama3.1:8b")

@tool
def add_project(name: str, description: str = "NULL"):
    """Adds a new project with the provided name and description information."""
    if description != "NULL":
        description = "'" + description + "'"

    execute(f"INSERT INTO public.projects(name, description) VALUES('{name}', {description})")

@tool
def add_requirement(project_name: str, description: str):
    """Adds a new requirement for an existing project. A requirement is a condition or capability that must be fulfilled for a project to be successful."""
    project_id = select(f"SELECT project_id FROM public.projects WHERE name = '{project_name}'")[0][0]

    execute(f"INSERT INTO public.requirements(project_id, description) VALUES('{project_id}', '{description}')")

@tool
def add_task(name: str, project_name: str, description: str = "NULL", start_date: str = date.today().strftime("%Y-%m-%d"), end_date: str = "NULL"):
    """Adds a new task. The task must belong to an existing project."""
    if description != "NULL":
        description = "'" + description + "'"
    if end_date != "NULL":
        end_date = "'" + end_date + "'"

    project_id = select(f"SELECT project_id FROM public.projects WHERE name = '{project_name}'")[0][0]
    
    execute(f"INSERT INTO public.tasks(name, description, project_id, start, \"end\") VALUES('{name}', {description}, {project_id}, '{start_date}', {end_date})")

@tool
def add_resource(first_name: str, contact: str, last_name: str = "NULL"):
    """Adds a new resource. A resource is a named person who contributes to a task."""
    if last_name != "NULL":
        last_name = "'" + last_name + "'"

    execute(f"INSERT INTO public.resources(first_name, last_name, contact) VALUES('{first_name}', {last_name}, '{contact}')")

@tool
def assign_resource(task_name: str, resource_first_name: str, resource_last_name: str = ""):
    """Assigns an existing resource to an existing task."""

    task_id = select(f"SELECT task_id FROM public.tasks WHERE name = '{task_name}'")[0][0]

    if resource_last_name:
        query = f"SELECT resource_id FROM public.resources WHERE first_name = '{resource_first_name}' and last_name = '{resource_last_name}'"
    else:
        query = f"SELECT resource_id FROM public.resources WHERE first_name = '{resource_first_name}' and last_name IS NULL"
    resource_id = select(query)[0][0]

    execute(f"INSERT INTO public.resource_assignments(task_id, resource_id) VALUES({task_id}, {resource_id})")

class WorkflowOutput(BaseModel):
    add_project: int = Field(
        description="The number of times that the user wants to create a new project.",
        default=0,
    )
    add_requirement: int = Field(
        description="The number of times that the user wants to create a new requirement for an existing project.",
        default=0,
    )
    add_task: int = Field(
        description="The number of times that the user wants to create a new task.",
        default=0,
    )
    add_resource: int = Field(
        description="The number of times that the user wants to create a new resource.",
        default=0,
    )
    assign_resource: int = Field(
        description="The number of times that the user wants to assign a resource to an existing task.",
        default=0,
    )
    followup: str = Field(
        description="A followup question asking the user to provide more clear information, if necessary.",
        default="",
    )

class DirectionalOutput(BaseModel):
    followup: str = Field(description="A followup question for the user to answer and give further clarification, if necessary.")

queue_builder = model.with_structured_output(WorkflowOutput)
directional_manager = model.with_structured_output(DirectionalOutput)

project_maker_tools = [add_project, add_requirement]
project_maker = model.bind_tools(project_maker_tools)

task_maker_tools = [add_task]
task_maker = model.bind_tools(task_maker_tools)

resource_manager_tools = [add_resource, assign_resource]
resource_manager = model.bind_tools(resource_manager_tools)

def assign_workflow(state: OverallState, config: RunnableConfig) -> Command[Literal["supervisor", "clarification"]]:
    new_messages = [HumanMessage(state["user_input"])]

    system_prompt = SystemMessage(
        """
        You are an AI that determines which project management functions the user wants to utilize and how many times they wish to utilize each function.
        This does not refer to external function, but rather internal ones like creating a project, adding tasks, etc.
        Do not explicitly ask the user for which functions they would like to use. It is your job to inference that information from their messages.
        Based on the user's request, return the appropriate number of function calls for each function at your disposal.
        If and only if you cannot understand the user's request, return a followup question (in the form of a comprehensible sentence) that respectfully asks the user to give a different request.
        """
    )
    response = queue_builder.invoke([system_prompt] + state["messages"] + new_messages, config=config)

    if len(response.followup) > 30:
        new_messages.append(AIMessage(response.followup))

    tool_queue = list[str]()
    for i in range(response.add_project + response.add_requirement):
        tool_queue.append("project_maker_check")
    for i in range(response.add_task):
        tool_queue.append("task_maker_check")
    for i in range(response.add_resource + response.assign_resource):
        tool_queue.append("resource_manager_check")

    return Command(
        update={
            "messages": new_messages,
            "tool_queue": tool_queue,
            "prev": "liaison",
            "followup": response.followup,
        }, goto="clarification" if len(response.followup) > 30 else "supervisor"
    )


def direct_workflow(state: OverallState) -> Command[Literal["project_maker_check", "task_maker_check", "resource_manager_check", "scoper", "analyst"]]:
    return Command(
        update={"tool_queue": state["tool_queue"][1:]},
        goto=state["tool_queue"][0],
    )

def clarify_input(state: OverallState) -> Command[Literal["liaison", "project_maker_check", "task_maker_check", "resource_manager_check", "suggestion_commit"]]:
    new_request = interrupt(state["followup"])

    return Command(
        update={"user_input": new_request} if state["prev"] == "liaison" else {"messages": [AIMessage(state["followup"]), HumanMessage(new_request)]},
        goto=state["prev"],
    )

def create_project_check(state: OverallState, config: RunnableConfig) -> Command[Literal["project_maker", "clarification"]]:
    system_prompt = SystemMessage(
        """
        You are helping to make projects in a project management application.
        You may be asked to either create a new project or add requirements to an existing project.
        Requirements are defined as conditions or capabilities that must be fulfilled for a project to be successful.
        If the user wants to perform both of these functions, or multiple of each, approach them one at a time.
        Remember that you are only gathering information, not performing the actual tasks themselves. 
        Thus, do not remark on when a task has been completed, only ask for confirmation whether your information is correct.

        If the user wants to create a new project, determine whether the provided message history has sufficient information about both the project's name and description.
        If you determine that there is not enough information about these factors, return a followup question that respectfully asks for specific further details.
        Before taking this step, ensure that the information you are asking for is not already provided by the user.
        Once you determine that there is sufficient information, make sure to ask the user if they would like to specify any additional requirements for the project.
        If they do, follow the steps to add a new requirement by asking followup questions.
        If not, return only an empty string and nothing else.

        If the user wants to add requirements to an existing project, determine whether the provided message history has sufficient information about the name of the project that the requirement belongs to and a description of the requirement.
        If you determine that there is not enough information about these factors, return a followup question that respectfully asks for specific further details.
        Once you determine that there is sufficient information, return only an empty string and nothing else.
        """
    )
    response = directional_manager.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "prev": "project_maker_check",
            "followup": response.followup,
        }, goto="clarification" if len(response.followup) > 30 else "project_maker"
    )

def create_project(state: OverallState, config: RunnableConfig) -> Command[Literal["project_maker_tools", "suggestion"]]:
    system_prompt = SystemMessage(
        """
        You are helping to make projects in a project management application.
        You may be asked to either create a new project or add requirements to an existing project.
        Requirements are defined as conditions or capabilities that must be fulfilled for a project to be successful.

        If the user wants to create a new project, you need information about the project's name and description from the given message history.
        The project's name absolutely must be quoted directly from the user's messages. 
        The description should be formatted as a properly capitalized and punctuated paragraph that could be read without additional context. It should be in the third-person.

        If the user wants to add a requirement to an existing project, you need information about the name of the project which the requirement belongs to and the description of the requirement from the given message history.
        The name of the project which the requirement belongs absolutely must be quoted directly from the user's messages.
        The description should be formatted as a properly capitalized and punctuated paragraph that could be read without additional context. It should be in the third-person.
        
        Call the appropriate tools based on the information present in the user's most recent messages.
        Make sure that you perform all tasks (e.g. adding projects, adding requirements) that have not yet been completed (meaning that the appropriate tool has not yet been called)
        If, based on these messages, you determine you must both create a new project and add a requirement to it, ensure that you create the project first.
        You must not add any details that the user does not mention, such as names.
        """
    )
    response = project_maker.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={"messages": [response]},
        goto="project_maker_tools" if response.tool_calls else "suggestion",
    )

def create_project_tools():
    return ToolNode(project_maker_tools)

def create_task_check(state: OverallState, config: RunnableConfig) -> Command[Literal["task_maker", "clarification"]]:
    system_prompt = SystemMessage(
        """
        You are helping to create a new task belonging to an existing project. If the user wants to create multiple, approach them one at a time.
        Do not concern yourself with any information not pertaining to the creation of a task.
        Remember that you are only gathering information, not performing the actual tasks themselves. 
        Thus, do not remark on when a task has been completed, only ask for confirmation whether your information is correct.
        Determine whether the provided message history has sufficient information about the task's name, description, the name of the project it belongs to, and optionally its start and end date.
        If you determine that there is not enough information about these factors, return a followup question that respectfully asks for specific further details. 
        Before taking this step, ensure that the information you are asking for is not already provided by the user. 
        Do not ask for any information about the project that the task belongs to other than its name.
        You must also ask a followup question if you determine from the message history that some tasks have been added in the current user session, but there are still more to create.
        This question should begin to ask for information about the next task that the user would like to create.
        If you determine that there is sufficient information about the current task, return only an empty string. Only do this once information about name, description, and the name of the project the task belongs to are present.
        If there is sufficient information, do not tell the user or offer confirmation of process completion. Simply return an empty string.
        """
    )
    response = directional_manager.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "prev": "task_maker_check",
            "followup": response.followup,
        }, goto="clarification" if len(response.followup) > 30 else "task_maker"
    )

def create_task(state: OverallState, config: RunnableConfig) -> Command[Literal["task_maker_tools", "suggestion"]]:
    system_prompt = SystemMessage(
        f"""
        You are helping to create a new task that belongs to an existing project. Only create one task at a time.
        From the given message history, extract information about the task's name, description, start date, end date, and name of the project it belongs to and pass it to the appropriate tools.
        This information should come from the most recent task that the user has provided the information for.
        Do not concern yourself with any information not pertaining to the creation of a task.

        The task's name absolutely must be quoted directly from the user's messages. 
        The description should be formatted as a properly capitalized and punctuated paragraph that could be read without additional context. It should be in the third-person.
        The start and end date, if present, should be formatted as YYYY-MM-DD. As a reference point, today's date is {date.today()}.
        If the start date is not explicitly mentioned, you may assume that it is today's date.
        If the end date is not explicitly mentioned, try to infer it based on the information provided by the user and your knowledge of today's date.
        The name of the project that the task belongs to absolutely must be quoted directly from the user's messages.
        You must not add any details that the user does not mention, such as names.
        """
    )
    response = task_maker.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={"messages": [response]},
        goto="task_maker_tools" if response.tool_calls else "suggestion",
    )

def create_task_tools():
    return ToolNode(task_maker_tools)

def manage_resources_check(state: OverallState, config: RunnableConfig) -> Command[Literal["resource_manager", "clarification"]]:
    system_prompt = SystemMessage(
        """
        You are helping to manage the resources assigned to specific tasks within a project.
        Resources are defined as named persons (with a required first and optional last name) that contribute their work to said tasks.
        You may be asked to either create a new resource or assign an existing resource to a task. 
        If the user wants to perform both of these functions, or multiple of each, approach them one at a time.
        Remember that you are only gathering information, not performing the actual tasks themselves. 
        Thus, do not remark on when a task has been completed, only ask for confirmation whether your information is correct.

        To create a new resource, determine whether the provided message history has sufficient information regarding the resource's first name, (optionally) its last name, and its contact information.
        If you determine that there is not enough information regarding these factors, return a followup question that respectfully asks the user for more details.
        Ensure that you get information about the resource's contact information, preferably an email address.
        Once you determine that there is sufficient information, make sure to ask the user if they would like to also assign this resource to an existing task as a followup question.
        If so, follow the steps to get the appropriate information by asking followup questions.
        If not, return only an empty string and nothing else.

        To assign an existing resource to a task, determine whether the provided message history has sufficient information regarding the resource's first and (optionally) last name as well as the name of the task to which the resource must be assigned.
        If you determine that there is not enough information regarding these factors, return a followup question that respectfully asks the user for more details.
        Once you determine that there is sufficient information, return only an empty string and nothing else.
        """
    )
    response = directional_manager.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={
            "prev": "resource_manager_check",
            "followup": response.followup,
        }, goto="clarification" if len(response.followup) > 30 else "resource_manager"
    )

def manage_resources(state: OverallState, config: RunnableConfig) -> Command[Literal["resource_manager_tools", "suggestion"]]:
    system_prompt = SystemMessage(
        """
        You are helping to manage the resources assigned to specific tasks within a project.
        Resources are defined as named persons (with a required first and optional last name) that contribute their work to said tasks.
        You may be asked to either create a new resource or assign an existing resource to a task. 
        If the user wants to perform both of these functions, or multiple of each, approach them one at a time.

        To create a new resource, you need its first name, (optionally) last name, and contact (which should preferably be an email address).
        These values absolutely must be quoted directly from the user's messages.

        To assign an existing resource to a task, you need the resource's first name and, if present, last name as well as the name of the task to assign to.
        All of these values absolutely must be quoted directly from the user's messages.

        Call the appropriate tools based on the information present in the user's most recent messages. If the last name is unknown, do not pass any argument to the tools you are using.
        If, based on these messages, you determine you must both create and assign a resource, ensure that you create the resource first.
        You must not add any details that the user does not mention, such as names.
        """
    )
    response = resource_manager.invoke([system_prompt] + state["messages"], config=config)

    return Command(
        update={"messages": [response]},
        goto="resource_manager_tools" if response.tool_calls else "suggestion",
    )

def manage_resources_tools():
    return ToolNode(resource_manager_tools)

def manage_scope(state: OverallState) -> OutputState:
    return {"output": "Ran manage_scope"}

def analyze_project(state: OverallState) -> OutputState:
    return {"output": "Ran analyze_project"}

def suggest_next(state: OverallState, config: RunnableConfig) -> OverallState:
    system_prompt = SystemMessage(
        f"""
        You are helping the user to create and manage their projects as part of a project management software.
        Your task is to recommend the use of a secondary project management function based on the most recent one that the user has utilized.
        The following are existing project management functions and which recommendations to offer in each case.

        Adding a new project - recommended secondary functions are adding a new requirement
        Adding a new requirement - there are no recommended secondary functions
        Adding a new task - recommended secondary functions are adding a new resource and assigning a resource to that task
        Adding a new resource - recommended secondary functions are assigning that resource to a task
        Assigning a new resource - there are no recommended secondary functions

        The user's most recently used function is {state["prev"]}
        Take into consideration this information, their most recent messages, and the above list.
        Return a followup question using context from the conversation that respectfully asks the user whether they would like to utilize an appropriate secondary function.
        """
    )
    response = directional_manager.invoke([system_prompt] + state["messages"], config=config)

    return {"prev": "suggestion_commit", "followup": response.followup}

def suggest_commit(state: OverallState, config: RunnableConfig) -> OverallState:
    system_prompt = SystemMessage(
        """
        You are helping the user to create and manage their projects as part of a project management software.
        Your task is to recommend the use of a secondary project management function based on the most recent one that the user has utilized.

        Examine the provided messages and context to determine which project functions the user would like to use and how many of each.
        Based on the user's request, return the appropriate number of calls for each function at your disposal.
        Remember that it is possible that the user may not wish to use any tools at all.
        """
    )
    response = queue_builder.invoke([system_prompt] + state["messages"][-2:], config=config)

    new_tools = list[str]()
    for i in range(response.add_project + response.add_requirement):
        new_tools.append("project_maker_check")
    for i in range(response.add_task):
        new_tools.append("task_maker_check")
    for i in range(response.add_resource + response.assign_resource):
        new_tools.append("resource_manager_check")

    return {"tool_queue": new_tools + state["tool_queue"], "output": "Runtime complete"}

def should_finish(state: OverallState):
    if state["tool_queue"]:
        return "loop"
    return "end"