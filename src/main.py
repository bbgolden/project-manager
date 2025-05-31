import uuid
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver
from states import OutputState, ProjectState
from nodes import contact_user, clarify_input, extract_from_input, tool_node, assemble_plan, should_continue

# Omit load_dotenv to disable LangSmith tracing
load_dotenv()

# remember to pass in {"messages": HumanMessage(user_input)} to initial graph.invoke
workflow = StateGraph(ProjectState, output=OutputState)

workflow.add_node("liaison", contact_user)
workflow.add_node("clarification", clarify_input)
workflow.add_node("manager", extract_from_input)
workflow.add_node("tools", tool_node())
workflow.add_node("assembly", assemble_plan)

workflow.set_entry_point("liaison")
workflow.add_edge("clarification", "liaison")
workflow.add_conditional_edges("manager", should_continue)
workflow.add_edge("tools", "manager")
workflow.set_finish_point("assembly")

checkpointer = MemorySaver()
project_manager = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": uuid.uuid4()}}
result = project_manager.invoke({
    "messages": HumanMessage(input("Enter project info:")),
    "budget_info": "",
    "timeline_info": "",
    "scope_info": "",
}, config=config)

while True:
    try:
        result = project_manager.invoke(Command(resume=input(result["__interrupt__"][0].value)), config=config)
    except KeyError:
        break

print(result)