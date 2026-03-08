import os
from groq import Groq
import pandas as pd
from tenacity import retry, wait_exponential, stop_after_attempt
import json
import uuid
import requests
from pinecone import Pinecone, ServerlessSpec

class RAGEngine:
    def __init__(self, use_demo_data: bool = False):
        # Initialize Groq Client
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=self.groq_api_key) if self.groq_api_key else None
        
        self.model_name = "llama-3.3-70b-versatile"
        
        self.hf_token = os.getenv("HF_TOKEN")
        self.hf_api_url = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.index_name = "ecommerce-data"
        
        self.pc = Pinecone(api_key=self.pinecone_api_key) if self.pinecone_api_key else None
        self.index = None
        
        if self.pc:
            if self.index_name not in self.pc.list_indexes().names():
                self.pc.create_index(
                    name=self.index_name,
                    dimension=384, # The dimension for paraphrase-multilingual-MiniLM-L12-v2
                    metric='cosine',
                    spec=ServerlessSpec(cloud='aws', region='us-east-1')
                )
            self.index = self.pc.Index(self.index_name)

    def _get_embeddings(self, texts: list) -> list:
        if not self.hf_token:
            raise Exception("HF_TOKEN not set in environment variables.")
            
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        
        import time
        for attempt in range(5):
            response = requests.post(self.hf_api_url, headers=headers, json={"inputs": texts, "options": {"wait_for_model": True}})
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 503:
                print(f"HF Model loading, waiting 10s (attempt {attempt+1}/5)...")
                time.sleep(10)
            else:
                raise Exception(f"HF API Error {response.status_code}: {response.text}")
                
        raise Exception("HF API Error: Model took too long to load.")

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
    def _call_llm_with_retry(self, **kwargs) -> str:
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _call_llm(self, system_prompt: str, user_prompt: str, response_format=None) -> str:
        if not self.client:
            return "Error: Groq API Key is missing. Please add it to your environment variables."
            
        kwargs = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3
        }
        
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
            
        try:
            from tenacity import RetryError
            return self._call_llm_with_retry(**kwargs)
        except RetryError as e:
            error_msg = str(e.last_attempt.exception())
            if "AuthenticationError" in error_msg or "401" in error_msg:
                if response_format == "json":
                    return '{"error": "Authentication Failed. Please check your Groq API Key."}'
                return f"Error: Authentication Failed. Please check your Groq API Key. Detail: {error_msg}"
            return f"Error connecting to LLM: {error_msg}"

    def ingest_csv(self, df: pd.DataFrame, progress_tracker: dict = None):
        if not self.index:
            if progress_tracker:
                progress_tracker["status"] = "failed"
                progress_tracker["message"] = "Pinecone not initialized. Check PINECONE_API_KEY."
            return

        total_rows = len(df)
        if progress_tracker:
            progress_tracker["total"] = total_rows
            
        vectors = []
        batch_texts = []
        batch_ids = []
        batch_metas = []
        
        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            prod_name = row_dict.get('Product Name', 'Unknown Product')
            
            if progress_tracker:
                progress_tracker["progress"] = idx + 1
                progress_tracker["message"] = f"Processing {idx + 1}/{total_rows}: {prod_name[:30]}..."
                
            text = f"Product: {prod_name}\nDescription: {row_dict.get('Description', '')}\nReview: {row_dict.get('Review', '')}"
            meta = {k: str(v) for k, v in row_dict.items() if pd.notna(v)}
            prod_id = str(row_dict.get("Product ID", f"doc_{idx}_{uuid.uuid4().hex[:8]}"))
            
            batch_texts.append(text)
            batch_ids.append(prod_id)
            batch_metas.append(meta)
            
            if len(batch_texts) >= 50:
                if progress_tracker:
                    progress_tracker["message"] = "Generating embeddings and saving to Pinecone..."
                embs = self._get_embeddings(batch_texts)
                for i in range(len(embs)):
                    vectors.append({"id": batch_ids[i], "values": embs[i], "metadata": batch_metas[i]})
                self.index.upsert(vectors=vectors)
                batch_texts, batch_ids, batch_metas, vectors = [], [], [], []
            
        if batch_texts:
            if progress_tracker:
                progress_tracker["message"] = "Finalizing vector database save..."
            embs = self._get_embeddings(batch_texts)
            for i in range(len(embs)):
                vectors.append({"id": batch_ids[i], "values": embs[i], "metadata": batch_metas[i]})
            self.index.upsert(vectors=vectors)

    def ingest_scraped_data(self, data: dict):
        if not data.get("success") or not self.index:
            return
            
        text = f"Title: {data.get('title')}\nDescription: {data.get('description')}\nContent: {data.get('full_text')[:1000]}"
        meta = {"url": data.get("url"), "source": "scraper"}
        doc_id = str(uuid.uuid4())
        
        emb = self._get_embeddings([text])[0]
        self.index.upsert(vectors=[{"id": doc_id, "values": emb, "metadata": meta}])

    def chat_with_data(self, query: str, session_history: list = None) -> str:
        if not session_history:
            session_history = []
            
        routing_sys = """You are a router. Classify the user query into exactly one of two categories: 'ANALYTICAL' or 'SEMANTIC'.
- 'ANALYTICAL': Questions about counts, totals, categories, stock, or grouping (e.g., 'How many categories do we have', 'What is the total stock').
- 'SEMANTIC': Questions about meaning, reviews, feelings, or specific problems (e.g., 'Why are shoes being returned', 'Find positive reviews').
Only output the exact word ANALYTICAL or SEMANTIC."""
        classification = self._call_llm(routing_sys, query).strip().upper()
        
        context_block = ""
        
        if "ANALYTICAL" in classification:
            try:
                import pandas as pd
                df = pd.read_csv("sample_data.csv")
                
                schema = str(df.dtypes.to_dict())
                
                pandas_sys_prompt = f"""You are a Python Pandas Data Scientist.
You have a DataFrame named `df` with the following schema:
{schema}

Write exactly ONE line of Python code that evaluates to the answer for the user's query.
The code must be an expression that `eval()` can execute (e.g., `df['Category'].unique().tolist()` or `len(df[df['Status'] == 'Returned'])`).
Do NOT include the word python, backticks, variables, or print statements. Output strictly the code expression."""
                
                generated_code = self._call_llm(pandas_sys_prompt, query).strip()
                
                if generated_code.startswith("```"):
                    generated_code = generated_code.split("\n")[1].replace("```", "").strip()
                
                local_vars = {"df": df, "pd": pd}
                try:
                    raw_result = eval(generated_code, {"__builtins__": {}}, local_vars)
                    
                    context_block = f"""[ANALYTICAL AGGREGATIONS]
These are precise statistics computed directly from the tabular database. Trust these numbers absolutely.
Result: {str(raw_result)}
(Code Executed: {generated_code})"""
                except Exception as code_error:
                    context_block = f"Failed to execute analytical query correctly. AI generated: {generated_code}. Error: {str(code_error)}"
            except Exception as e:
                context_block = f"Critical Pandas Error: {str(e)}"
                
        else:
            intent_sys_prompt = "Extract purely the search keywords from this user query. No formatting, no chat. Just keywords."
            search_intent = self._call_llm(intent_sys_prompt, query)
            
            if self.index:
                query_emb = self._get_embeddings([search_intent])[0]
                results = self.index.query(vector=query_emb, top_k=15, include_metadata=True)
                
                context_data = []
                for i, match in enumerate(results.get("matches", [])):
                    meta = match.get("metadata", {})
                    context_data.append(f"[Row {i+1}] {json.dumps(meta)}")
                        
                context_block = "\n".join(context_data) if context_data else "No relevant database records found."
            else:
                context_block = "Vector database is not initialized."
        
        system_prompt = f"""You are a Principal E-Commerce Business Analyst AI.
You help the store owner understand their sales, returns, and customer satisfaction by chatting with them.
Answer the user's question directly, clearly, and concisely based ONLY on the following context block.
If the answer is a metric (like 'how many categories'), use the explicit ANALYTICAL AGGREGATIONS provided.
If the context does not contain the answer, state that clearly. Be conversational but highly analytical.

CONTEXT BLOCK:
{context_block}
"""
        messages = [{"role": "system", "content": system_prompt}]
        for msg in session_history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
        messages.append({"role": "user", "content": query})
        
        if not self.client:
            return "Error: Groq API Key is missing in the backend environment."
            
        try:
            from tenacity import RetryError
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.3
            )
            return response.choices[0].message.content
        except RetryError as e:
            error_msg = str(e.last_attempt.exception())
            return f"Error connecting to LLM: {error_msg}"
        except Exception as e:
            return f"Agent Execution Error: {str(e)}"

    def module_c_business_auditor(self, scraped_data: dict) -> str:
        """Module C: Compare & Suggest against SEO/CRO best practices."""
        system_prompt = """You are a senior SEO and Conversion Rate Optimization (CRO) auditor.
Analyze the following scraped page data. Compare it against best practices (e.g., clear headings, persuasive descriptions, call-to-actions, keyword richness).
Provide actionable suggestions for improvement. The output should be professional markdown."""

        content_to_audit = f"""
URL: {scraped_data.get('url')}
Title: {scraped_data.get('title')}
Headings: {', '.join(scraped_data.get('headings', []))}
Description: {scraped_data.get('description')}
Content Snippet: {scraped_data.get('full_text', '')[:1000]}
"""
        return self._call_llm(system_prompt, content_to_audit)
