import uvicorn
from uuid import UUID
from typing import Sequence
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from interface.core.schemas import Action
from interface.core.project_manager import project_manager

app = FastAPI(debug=True)

class UserMessage(BaseModel):
    content: str
    thread_id: UUID
    is_first_message: bool

class AgentMessage(BaseModel):
    content: str

class Thread(BaseModel):
    thread_id: UUID

class StatusInfo(BaseModel):
    actions: Sequence[Action]

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
    config = {"configurable": {"thread_id": message.thread_id}}

    if message.is_first_message:
        response = project_manager.invoke({"user_input": message.content}, config=config)
    else:
        response = project_manager.invoke(Command(resume=message.content), config=config)

    try:
        return AgentMessage(content=response["__interrupt__"][0].value)
    except KeyError:
        return AgentMessage(content=response["output"])
    
@app.get("/status", response_model=StatusInfo)
def get_status(thread: Thread):
    config = {"configurable": {"thread_id": thread.thread_id}}
    snapshot = project_manager.get_state(config=config)

    try:
        actions = snapshot.values["actions_taken"]
    except KeyError:
        actions = []

    return StatusInfo(actions=actions)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)