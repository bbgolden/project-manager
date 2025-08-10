import uvicorn
from uuid import UUID
from typing import Sequence
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from interface.core.schemas import Action, Task
from interface.core.project_manager import project_manager
from interface.utils import select

app = FastAPI(debug=True)

class UserMessage(BaseModel):
    content: str
    threadID: UUID
    isFirstMessage: bool

class AgentMessage(BaseModel):
    content: str

class StatusInfo(BaseModel):
    projects: Sequence[str]
    actions: Sequence[Action]
    timeline: Sequence[Task]

ORIGINS = (
    "http://localhost:3000",
)

app.add_middleware(
    CORSMiddleware, 
    allow_origins=ORIGINS, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat", response_model=AgentMessage)
def send_chat(message: UserMessage):
    config = {"configurable": {"thread_id": message.threadID}}

    if message.isFirstMessage:
        response = project_manager.invoke({"user_input": message.content}, config=config)
    else:
        response = project_manager.invoke(Command(resume=message.content), config=config)

    try:
        return AgentMessage(content=response["__interrupt__"][0].value)
    except KeyError:
        return AgentMessage(content=response["output"])
    
@app.get("/chat", response_model=StatusInfo)
def get_status(thread: UUID):
    config = {"configurable": {"thread_id": thread}}
    snapshot = project_manager.get_state(config=config)

    try:
        actions = snapshot.values["actions_taken"]
    except KeyError:
        actions = []

    projects = [project for project, in select("SELECT name FROM public.projects")]

    timeline = [Task(
        projectName=project_name,
        taskName=task_name,
        taskDesc=desc,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d") if end else end,
    ) for project_name, task_name, desc, start, end in select(
        """
        SELECT projects.name, tasks.name, tasks.description, start, \"end\" 
        FROM public.tasks
        LEFT JOIN public.projects
            ON projects.project_id = tasks.project_id 
        ORDER BY \"end\"
        """
    )]

    return StatusInfo(projects=projects, actions=actions, timeline=timeline)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)