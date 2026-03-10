#!/usr/bin/env python3

import sys
import os
sys.path.append('/opt/render/project/src')

try:
    from core.rag_engine import RAGEngine
    print("✅ RAG Engine imported successfully")
    
    eng = RAGEngine()
    print("✅ RAG Engine initialized")
    
    # Test a simple query
    result = eng.chat_with_data("How many categories?", [])
    print(f"✅ Query result: {result}")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
