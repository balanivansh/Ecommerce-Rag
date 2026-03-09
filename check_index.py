import os
from dotenv import load_dotenv
from core.rag_engine import RAGEngine

load_dotenv(override=True)

eng = RAGEngine()
print("PC API KEY FIRST 10:", os.getenv("PINECONE_API_KEY")[:10] if os.getenv("PINECONE_API_KEY") else "None")

try:
    stats = eng.index.describe_index_stats()
    print("INDEX STATS:", stats)
except Exception as e:
    print("STATS ERROR:", e)
