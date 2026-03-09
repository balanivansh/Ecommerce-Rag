from core.rag_engine import RAGEngine
from dotenv import load_dotenv

load_dotenv(override=True)
print("Initializing engine...")
engine = RAGEngine(use_demo_data=True)
print("Running chat query...")
ans = engine.chat_with_data("How many returned speakers are there?")
print("AI Response:", ans)
