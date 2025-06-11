import uuid
from dotenv import load_dotenv
from langgraph.graph import StateGraph
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver
from states import InputState, OutputState, OverallState
from nodes import direct_workflow, clarify_direction, create_project, manage_schedule, manage_scope, analyze_project

# Omit load_dotenv to disable LangSmith tracing
load_dotenv()

workflow = StateGraph(OverallState, input=InputState, output=OutputState)

workflow.add_node("liaison", direct_workflow)
workflow.add_node("input_helper", clarify_direction)
workflow.add_node("project_maker", create_project)
workflow.add_node("scheduler", manage_schedule)
workflow.add_node("scoper", manage_scope)
workflow.add_node("analyst", analyze_project)

workflow.set_entry_point("liaison")
workflow.add_edge("input_helper", "liaison")
workflow.set_finish_point("project_maker")
workflow.set_finish_point("scheduler")
workflow.set_finish_point("scoper")
workflow.set_finish_point("analyst")

checkpointer = MemorySaver()
project_manager = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": uuid.uuid4()}}
result = project_manager.invoke({"user_input": input("What would you like to do today?")}, config=config)

while True:
    try:
        result = project_manager.invoke(Command(resume=input(result["__interrupt__"][0].value)), config=config)
    except KeyError:
        break

print(result)