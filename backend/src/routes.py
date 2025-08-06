import uvicorn
from uuid import UUID
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from interface.project_manager import project_manager

app = FastAPI(debug=True)

class UserMessage(BaseModel):
    content: str
    thread_id: UUID
    is_first_message: bool

class AgentMessage(BaseModel):
    content: str

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

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)