#!/usr/bin/env python3
"""
Script to ingest sample CSV data into the RAG system
"""
import os
import sys
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to the path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rag_engine import RAGEngine

def main():
    print("Starting sample data ingestion...")
    
    # Initialize the RAG engine
    engine = RAGEngine(use_demo_data=False)
    
    if not engine.index:
        print("ERROR: Pinecone not initialized. Check PINECONE_API_KEY.")
        return
    
    # Path to the sample CSV file
    csv_path = Path(__file__).parent.parent / "frontend" / "public" / "sample_data.csv"
    
    if not csv_path.exists():
        print(f"ERROR: Sample CSV not found at {csv_path}")
        return
    
    print(f"Loading CSV from: {csv_path}")
    df = pd.read_csv(csv_path)
    
    print(f"Found {len(df)} rows in CSV")
    print("Columns:", df.columns.tolist())
    print("Sample data:")
    print(df.head(2))
    
    # Create a progress tracker
    progress_tracker = {
        "status": "processing",
        "progress": 0,
        "total": len(df),
        "message": "Starting ingestion..."
    }
    
    # Ingest the data
    try:
        engine.ingest_csv(df, progress_tracker=progress_tracker)
        print("✅ Successfully ingested sample data!")
        
        # Check the final status
        stats = engine.index.describe_index_stats()
        print(f"Vector database now has {stats.get('total_vector_count', 0)} vectors")
        
    except Exception as e:
        print(f"❌ Error during ingestion: {e}")
        progress_tracker["status"] = "failed"
        progress_tracker["message"] = str(e)

if __name__ == "__main__":
    main()
