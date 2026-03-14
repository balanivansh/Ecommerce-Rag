#!/usr/bin/env python3

import sys
import os
sys.path.append('/opt/render/project/src')

try:
    from core.rag_engine import RAGEngine
    
    print("=== DEBUG: Initializing RAG Engine ===")
    eng = RAGEngine()
    print(f"=== DEBUG: Client initialized: {eng.client is not None}")
    print(f"=== DEBUG: Index initialized: {eng.index is not None}")
    
    print("=== DEBUG: Testing simple query ===")
    result = eng.chat_with_data("Test query", [])
    print(f"=== DEBUG: Query result: {result}")
    print(f"=== DEBUG: Result type: {type(result)}")
    
except Exception as e:
    print(f"=== DEBUG: Exception occurred: {str(e)}")
    import traceback
    traceback.print_exc()
