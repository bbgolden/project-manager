import uuid
from langgraph.types import Command
from interface.core.project_manager import project_manager

if __name__ == "__main__":
    config = {"configurable": {"thread_id": uuid.uuid4()}}
    result = project_manager.invoke({"user_input": input("")}, config=config)

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
    print(result["actions_taken"])