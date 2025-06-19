import uuid
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver
from libs.graph import InputState, OutputState, OverallState
from libs.graph import (
    direct_workflow, 
    clarify_input, 
    create_project,
    create_project_check,
    create_project_tools, 
    manage_schedule, 
    manage_scope, 
    analyze_project,
    should_finish
)

load_dotenv()

workflow = StateGraph(OverallState, input=InputState, output=OutputState)

workflow.add_node("liaison", direct_workflow)
workflow.add_node("input_helper", clarify_input)
workflow.add_node("project_maker", create_project)
workflow.add_node("project_maker_check", create_project_check)
workflow.add_node("project_maker_tools", create_project_tools())
workflow.add_node("scheduler", manage_schedule)
workflow.add_node("scoper", manage_scope)
workflow.add_node("analyst", analyze_project)

workflow.set_entry_point("liaison")
workflow.add_conditional_edges(
    "project_maker", 
    should_finish,
    {
        "tools": "project_maker_tools",
        "end": END,
    }
)
workflow.add_edge("project_maker_tools", "project_maker")
workflow.set_finish_point("scheduler")
workflow.set_finish_point("scoper")
workflow.set_finish_point("analyst")

checkpointer = MemorySaver()
project_manager = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": uuid.uuid4()}}
result = project_manager.invoke({"user_input": input("What would you like to do? ")}, config=config)

while True:
    try:
        result = project_manager.invoke(
            Command(
                resume=input(result["__interrupt__"][0].value + " ")
            ), config=config
        )
    except KeyError:
        break

print(result["output"])