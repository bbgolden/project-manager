from dotenv import load_dotenv
from langchain_ollama import ChatOllama

# Omit load_dotenv to disable LangSmith tracing
load_dotenv()

llm = ChatOllama(model="qwen3:8b", temperature=0)
messages = [("system", "You are a knowledgable meteorologist that likes to be concise. Respond to user requests with simple, two sentence summaries that convey all necessary information."), ("human", "What is the weather in Texas this time of year? It's currently May 28.")]

response = llm.invoke(messages)
print(response.content)