from typing import Literal, Annotated, Any
from langchain_core.messages import HumanMessage
from langgraph.types import Command, interrupt
from interface.core.schemas import SubgraphState, Action

def get_invalid_values[T](vals_to_check: list[T], existing_vals: list[T]) -> list[T]:
    """Returns all values in vals_to_check that are not present in existing_vals."""
    bool_mask = [val not in existing_vals for val in vals_to_check]
    invalid_vals = [val for val, bool in zip(vals_to_check, bool_mask) if bool]

    return invalid_vals

def clarify_subgraph_input(state: SubgraphState) -> Command[Literal["context", "dialogue"]]:
    new_request = interrupt(state.followup)

    return Command(
        update={"messages": [HumanMessage(new_request)]},
        goto=state.redirect,
    )

def compile_action_data(name: str, state: SubgraphState) -> Action:
    param_flag = type(Annotated[Any, "__action_param__"])
    params = {}

    for field, value in state.model_dump().items():
        try:
            annot = state.__annotations__[field]
        except KeyError:
            continue

        if (
            type(annot) is param_flag
            and hasattr(annot, "__metadata__")
            and "__action_param__" in annot.__metadata__
        ):
            params.update({field: value})

    return Action(name=name, params=params)