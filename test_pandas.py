from core.rag_engine import RAGEngine
import logging
import logging
from dotenv import load_dotenv
load_dotenv(override=True)

engine = RAGEngine(use_demo_data=True)
query = "what is the most returned product"
print("\n--- QUERY ---")
print(query)
routing_sys = """You are a router. Classify the user's 'Latest Query' into exactly one of two categories: 'ANALYTICAL' or 'SEMANTIC'.
- 'ANALYTICAL': ONLY use this for strict mathematical numbers, counts, averages, or totals (e.g., 'How many...', 'What is the total...', 'Average rating...').
- 'SEMANTIC': Use this for literally EVERYTHING ELSE. Reading text, finding product names, viewing categories, semantic meaning, or any general question (e.g., 'What are the categories?', 'List the returned products', 'Why are items returned').
If in doubt, ALWAYS output SEMANTIC. Only output the exact word ANALYTICAL or SEMANTIC."""
print("CLASSIFICATION:", engine._call_llm(routing_sys, query).strip().upper())
ans = engine.chat_with_data(query)
print("\n--- FINAL ANSWER ---")
print(ans)
