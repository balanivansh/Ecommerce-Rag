import os
import shutil
import pandas as pd
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI, HTTPException, UploadFile, File, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rag_engine import RAGEngine
from core.scraper import scrape_product_info

app = FastAPI(title="E-Commerce Intelligence RAG API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Since Next.js is another port, we allow all for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instance
engine = None

def get_engine():
    global engine
    if engine is None:
        print("Initializing RAGEngine (this may take a minute to download models)...")
        engine = RAGEngine(use_demo_data=True)
    return engine

class ScrapeReq(BaseModel):
    url: str

class AuditorReq(BaseModel):
    scraped_data: Dict[str, Any]

# Global task tracker for background uploads
upload_tasks = {}

def _process_csv_background(task_id: str, temp_path: str):
    """Background processor for CSV ingestion."""
    try:
        df = pd.read_csv(temp_path)
        eng = get_engine()
        eng.ingest_csv(df, progress_tracker=upload_tasks[task_id])
        upload_tasks[task_id]["status"] = "completed"
        upload_tasks[task_id]["message"] = f"Successfully ingested {len(df)} rows."
    except Exception as e:
        upload_tasks[task_id]["status"] = "failed"
        upload_tasks[task_id]["message"] = str(e)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/api/ingest/csv")
async def ingest_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")
        
    try:
        task_id = str(uuid.uuid4())
        upload_tasks[task_id] = {"status": "processing", "progress": 0, "total": 0, "message": "Initializing..."}
        
        # Save temp file for background worker
        temp_path = f"temp_{uuid.uuid4().hex}_{file.filename}"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        background_tasks.add_task(_process_csv_background, task_id, temp_path)
        return {"status": "success", "task_id": task_id, "message": "Upload started in background"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/task/status/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in upload_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return upload_tasks[task_id]

@app.post("/api/ingest/scrape")
async def ingest_scrape(req: ScrapeReq):
    scraped_data = scrape_product_info(req.url)
    if scraped_data.get("success"):
        eng = get_engine()
        eng.ingest_scraped_data(scraped_data)
        return {"status": "success", "data": scraped_data}
    raise HTTPException(status_code=500, detail=scraped_data.get("error", "Failed to scrape"))

class ChatReq(BaseModel):
    query: str
    history: list = []

@app.post("/api/chat")
async def chat(req: ChatReq):
    eng = get_engine()
    if not eng.client:
        raise HTTPException(status_code=401, detail="Groq API Key is missing.")
        
    try:
        response_text = eng.chat_with_data(req.query, req.history)
        return {"status": "success", "response": response_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/modules/auditor")
async def run_auditor(req: AuditorReq):
    eng = get_engine()
    if not eng.client:
        raise HTTPException(status_code=401, detail="Groq API Key is missing.")
        
    try:
        report = eng.module_c_business_auditor(req.scraped_data)
        return {"status": "success", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
