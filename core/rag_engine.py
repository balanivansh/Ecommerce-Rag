import os
import chromadb
from groq import Groq
import pandas as pd
from tenacity import retry, wait_exponential, stop_after_attempt
import json
import uuid

class RAGEngine:
    def __init__(self, use_demo_data: bool = False):
        # Initialize Groq Client
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        if not self.groq_api_key and not use_demo_data:
            pass
        self.client = Groq(api_key=self.groq_api_key) if self.groq_api_key else None
        
        # Using a reliable model for mixed language & structured responses format
        self.model_name = "llama-3.3-70b-versatile"
        
        # Initialize ChromaDB persistent client (HF spaces friendly inside project path)
        self.db_path = "./chroma_db"
        
        # Check if dir exists, if not Chroma handles it.
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        
        # Use a proper multilingual embedding model for English/Hindi
        from chromadb.utils import embedding_functions
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="paraphrase-multilingual-MiniLM-L12-v2")
        
        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection("ecommerce_data", embedding_function=self.ef)
        
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
    def _call_llm_with_retry(self, **kwargs) -> str:
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _call_llm(self, system_prompt: str, user_prompt: str, response_format=None) -> str:
        if not self.client:
            return "Error: Groq API Key is missing. Please add it to your environment variables or the sidebar."
            
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
            # Re-raise the inner exception (e.g. AuthenticationError)
            error_msg = str(e.last_attempt.exception())
            if "AuthenticationError" in error_msg or "401" in error_msg:
                # Format to JSON if required since Module B expects JSON parseable output on error sometimes
                if response_format == "json":
                    return '{"error": "Authentication Failed. Please check your Groq API Key."}'
                return f"Error: Authentication Failed. Please check your Groq API Key. Detail: {error_msg}"
            return f"Error connecting to LLM: {error_msg}"

    def ingest_csv(self, df: pd.DataFrame, progress_tracker: dict = None):
        """Ingest pandas dataframe into ChromaDB with optional progress tracking."""
        docs = []
        metadatas = []
        ids = []
        
        total_rows = len(df)
        if progress_tracker:
            progress_tracker["total"] = total_rows
            
        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            prod_name = row_dict.get('Product Name', 'Unknown Product')
            
            if progress_tracker:
                progress_tracker["progress"] = idx + 1
                progress_tracker["message"] = f"Processing {idx + 1}/{total_rows}: {prod_name[:30]}..."
                
            # Construct text representation for embedding
            text = f"Product: {prod_name}\nDescription: {row_dict.get('Description', '')}\nReview: {row_dict.get('Review', '')}"
            docs.append(text)
            
            # Clean metadata (ChromaDB only accepts str, int, float, bool)
            meta = {k: str(v) for k, v in row_dict.items() if pd.notna(v)}
            metadatas.append(meta)
            
            # Use Product ID if available, else generate using uuid based on index
            prod_id = row_dict.get("Product ID", f"doc_{idx}_{uuid.uuid4().hex[:8]}")
            ids.append(str(prod_id))
            
            # Batch upsert every 50 to avoid massive memory spikes or blocking
            if len(docs) >= 50:
                if progress_tracker:
                    progress_tracker["message"] = f"Saving batch of 50 to vector database..."
                self.collection.upsert(documents=docs, metadatas=metadatas, ids=ids)
                docs, metadatas, ids = [], [], []
            
        # Flush remaining
        if docs:
            if progress_tracker:
                progress_tracker["message"] = f"Finalizing vector database save..."
            self.collection.upsert(
                documents=docs,
                metadatas=metadatas,
                ids=ids
            )
            
    def ingest_scraped_data(self, data: dict):
        if not data.get("success"):
            return
            
        text = f"Title: {data.get('title')}\nDescription: {data.get('description')}\nContent: {data.get('full_text')[:1000]}"
        meta = {"url": data.get("url"), "source": "scraper"}
        doc_id = str(uuid.uuid4())
        
        self.collection.upsert(
            documents=[text],
            metadatas=[meta],
            ids=[doc_id]
        )

    def chat_with_data(self, query: str, session_history: list = None) -> str:
        """Intelligent Router Chat RAG combining semantics, stats, memory, and LLM synthesis."""
        if not session_history:
            session_history = []
            
        # 1. Router Classification
        routing_sys = """You are a router. Classify the user query into exactly one of two categories: 'ANALYTICAL' or 'SEMANTIC'.
- 'ANALYTICAL': Questions about counts, totals, categories, stock, or grouping (e.g., 'How many categories do we have', 'What is the total stock').
- 'SEMANTIC': Questions about meaning, reviews, feelings, or specific problems (e.g., 'Why are shoes being returned', 'Find positive reviews').
Only output the exact word ANALYTICAL or SEMANTIC."""
        classification = self._call_llm(routing_sys, query).strip().upper()
        
        context_block = ""
        
        # 2A. Analytical Pipeline (Bypass Vector DB, Use Real Stats via Pandas Agent)
        if "ANALYTICAL" in classification:
            try:
                import pandas as pd
                # We assume sample_data.csv is available in the root
                df = pd.read_csv("sample_data.csv")
                
                # Get the schema to help the LLM write code
                schema = str(df.dtypes.to_dict())
                
                pandas_sys_prompt = f"""You are a Python Pandas Data Scientist.
You have a DataFrame named `df` with the following schema:
{schema}

Write exactly ONE line of Python code that evaluates to the answer for the user's query.
The code must be an expression that `eval()` can execute (e.g., `df['Category'].unique().tolist()` or `len(df[df['Status'] == 'Returned'])`).
Do NOT include the word python, backticks, variables, or print statements. Output strictly the code expression."""
                
                # Ask LLM to generate the python code
                generated_code = self._call_llm(pandas_sys_prompt, query).strip()
                
                # Strip markdown code blocks if the LLM accidentally included them
                if generated_code.startswith("```"):
                    generated_code = generated_code.split("\n")[1].replace("```", "").strip()
                
                # Execute the LLM's code safely against our DataFrame
                local_vars = {"df": df, "pd": pd}
                try:
                    # We use eval since we requested a single expression
                    raw_result = eval(generated_code, {"__builtins__": {}}, local_vars)
                    
                    context_block = f"""[ANALYTICAL AGGREGATIONS]
These are precise statistics computed directly from the tabular database. Trust these numbers absolutely.
Result: {str(raw_result)}
(Code Executed: {generated_code})"""
                except Exception as code_error:
                    # Fallback if the AI writes bad code
                    context_block = f"Failed to execute analytical query correctly. AI generated: {generated_code}. Error: {str(code_error)}"
            except Exception as e:
                context_block = f"Critical Pandas Error: {str(e)}"
                
        # 2B. Semantic Pipeline (Vector DB)
        else:
            intent_sys_prompt = "Extract purely the search keywords from this user query. No formatting, no chat. Just keywords."
            search_intent = self._call_llm(intent_sys_prompt, query)
            
            # Retrieve relevant context from ChromaDB (bumped to 15 for better context)
            results = self.collection.query(query_texts=[search_intent], n_results=15)
            
            context_data = []
            if results and results.get('documents') and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i]
                    context_data.append(f"[Row {i+1}] {json.dumps(meta)}")
                    
            context_block = "\n".join(context_data) if context_data else "No relevant database records found."
        
        # 3. Main Synthesis Prompt
        system_prompt = f"""You are a Principal E-Commerce Business Analyst AI.
You help the store owner understand their sales, returns, and customer satisfaction by chatting with them.
Answer the user's question directly, clearly, and concisely based ONLY on the following context block.
If the answer is a metric (like 'how many categories'), use the explicit ANALYTICAL AGGREGATIONS provided.
If the context does not contain the answer, state that clearly. Be conversational but highly analytical.

CONTEXT BLOCK:
{context_block}
"""
        # 4. Construct messages with explicit history
        messages = [{"role": "system", "content": system_prompt}]
        for msg in session_history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
        # Append latest query
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
