from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.8)