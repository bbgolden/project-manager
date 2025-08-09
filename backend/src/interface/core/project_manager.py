from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from interface.core.schemas import InputState, OutputState, OverallState
from interface.core.nodes.graph.parent_nodes import (
    assign_workflow,
    direct_workflow, 
    clarify_input, 
    create_project,
    create_req,
    create_task,
    create_dep,
    create_resource,
    assign_resource,
    analyze_project,
    suggest_next,
    suggest_commit,
    should_finish,
)

workflow = StateGraph(OverallState, input=InputState, output=OutputState)

workflow.add_node("liaison", assign_workflow)
workflow.add_node("supervisor", direct_workflow)
workflow.add_node("clarification", clarify_input)
workflow.add_node("project_maker", create_project)
workflow.add_node("req_maker", create_req)
workflow.add_node("task_maker", create_task)
workflow.add_node("dep_maker", create_dep)
workflow.add_node("resource_maker", create_resource)
workflow.add_node("resource_assigner", assign_resource)
workflow.add_node("analyst", analyze_project)
workflow.add_node("suggestion", suggest_next)
workflow.add_node("suggestion_commit", suggest_commit)

workflow.set_entry_point("liaison")
workflow.add_edge("project_maker", "suggestion")
workflow.add_edge("req_maker", "suggestion")
workflow.add_edge("task_maker", "suggestion")
workflow.add_edge("dep_maker", "suggestion")
workflow.add_edge("resource_maker", "suggestion")
workflow.add_edge("resource_assigner", "suggestion")
workflow.add_edge("analyst", "suggestion")
workflow.add_conditional_edges(
    "suggestion_commit",
    should_finish,
    {
        "loop": "supervisor",
        "end": END,
    },
)

checkpointer = MemorySaver()
project_manager = workflow.compile(checkpointer=checkpointer)