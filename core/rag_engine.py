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
        self.hf_api_url = "https://router.huggingface.co/hf-inference/pipeline/feature-extraction/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        
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
            
        from huggingface_hub import InferenceClient
        import time
        
        client = InferenceClient(token=self.hf_token)
        
        for attempt in range(5):
            try:
                # InferenceClient handles optimal routing internally
                embeddings = client.feature_extraction(texts, model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
                # Return list of lists for Pinecone compatibility
                return embeddings.tolist()
            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg or "Model is loading" in error_msg or "timeout" in error_msg.lower():
                    print(f"HF Model loading, waiting 10s (attempt {attempt+1}/5)...")
                    time.sleep(10)
                else:
                    raise Exception(f"HF API Error: {error_msg}")
                    
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
            
        augmented_query = query
        if session_history:
            history_text = "\n".join([f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in session_history[-4:]])
            augmented_query = f"Chat History:\n{history_text}\n\nLatest Query: {query}\n\n(Note: Answer or write code based on the 'Latest Query', but use 'Chat History' to resolve any 'it', 'they', or context)"
            
        routing_sys = """You are an intelligent query classifier for an e-commerce RAG system. Classify the user's query into exactly one of these categories:

CATEGORICAL: Questions about categories, types, counts, totals, averages, or any aggregate data
Examples: "How many categories?", "What categories do you have?", "Total products", "Average rating", "Count of returned items"

PRODUCT_SPECIFIC: Questions about specific products, product details, comparisons, or product features
Examples: "Tell me about wireless mouse", "Compare TV and keyboard", "Product details for P0001", "Kitchen products"

SEMANTIC: General questions, reviews, opinions, reasons, or any text-based analysis
Examples: "Why are items returned?", "What do customers think?", "Best rated products", "Customer feedback"

Only output the exact category name: CATEGORICAL, PRODUCT_SPECIFIC, or SEMANTIC"""
        classification = self._call_llm(routing_sys, augmented_query).strip().upper()
        
        context_block = ""
        
        if "CATEGORICAL" in classification:
            # Use metadata-based analytical approach for categorical questions
            context_block = self._handle_categorical_query(augmented_query)
        elif "PRODUCT_SPECIFIC" in classification:
            # Use targeted vector search for product-specific questions
            context_block = self._handle_product_query(augmented_query)
        else:
            # Use semantic search for general questions
            context_block = self._handle_semantic_query(augmented_query)
    
    def _handle_categorical_query(self, query: str) -> str:
        """Handle categorical questions using metadata aggregation"""
        try:
            if not self.index:
                return "Vector database is not initialized."
                
            # For categorical queries, fetch multiple diverse samples to ensure comprehensive coverage
            # Use different random vectors to get diverse data points
            all_categories = set()
            all_data = []
            sample_size = 500  # Get larger sample for better coverage
            
            # Fetch data in multiple batches to ensure diversity
            for batch in range(3):  # 3 different random seeds
                import random
                random_vector = [random.uniform(-1, 1) for _ in range(384)]
                response = self.index.query(vector=random_vector, top_k=sample_size//3, include_metadata=True)
                
                if response and response.get('matches'):
                    for match in response['matches']:
                        meta = match.get('metadata', {})
                        all_data.append(meta)
                        if 'Category' in meta:
                            all_categories.add(meta['Category'])
            
            if not all_data:
                return "No data available in vector database."
            
            # Comprehensive aggregation from all collected data
            categories = list(all_categories)
            total_products = len(all_data)
            status_counts = {}
            rating_sum = 0
            rating_count = 0
            stock_count = 0
            sold_count = 0
            transit_count = 0
            returned_count = 0
            
            for item in all_data:
                # Count statuses
                status = item.get('Status', 'Unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
                
                if status == 'Sold':
                    sold_count += 1
                elif status == 'In Transit':
                    transit_count += 1
                elif status == 'Returned':
                    returned_count += 1
                elif 'Stock' in status:
                    stock_count += 1
                
                # Aggregate ratings
                rating = item.get('Rating')
                if rating and rating != '0':
                    try:
                        rating_sum += float(rating)
                        rating_count += 1
                    except:
                        pass
            
            # Calculate percentages and averages
            avg_rating = rating_sum / rating_count if rating_count > 0 else 0
            sold_transit_total = sold_count + transit_count
            
            # Create comprehensive context for LLM
            context = f"""COMPREHENSIVE DATA ANALYSIS:
Total Products Analyzed: {total_products}
Unique Categories Found: {categories}
Category Count: {len(categories)}
Status Breakdown: {dict(sorted(status_counts.items()))}
Stock Count: {stock_count}
Sold Count: {sold_count}
In Transit Count: {transit_count}
Returned Count: {returned_count}
Total Sold+In Transit: {sold_transit_total}
Average Rating: {avg_rating:.2f} (based on {rating_count} ratings)

Data Quality Check: This analysis is based on {total_products} products sampled from vector database. Categories found: {len(categories)}.

Sample Products by Category:
"""
            
            # Add representative samples from each category found
            category_samples = {}
            for item in all_data[:50]:  # First 50 items for samples
                cat = item.get('Category', 'Unknown')
                if cat not in category_samples and len(category_samples) < 10:
                    category_samples[cat] = item
            
            for cat, sample_item in category_samples.items():
                context += f"\n[{cat}] Product: {sample_item.get('Product Name', 'N/A')}, Status: {sample_item.get('Status', 'N/A')}, Rating: {sample_item.get('Rating', 'N/A')}, Stock: {sample_item.get('Stock', 'N/A')}"
            
            return context
            
        except Exception as e:
            return f"Error analyzing categorical data: {str(e)}"
    
    def _handle_product_query(self, query: str) -> str:
        """Handle product-specific questions with targeted vector search"""
        try:
            # Extract product keywords for better search
            intent_sys = "Extract the main product keywords from this query. Just the keywords, no extra text."
            search_intent = self._call_llm(intent_sys, query)
            
            if not self.index:
                return "Vector database is not initialized."
            
            # Use vector search for product-specific queries
            query_emb = self._get_embeddings([search_intent])[0]
            results = self.index.query(vector=query_emb, top_k=20, include_metadata=True)
            
            context_data = []
            for i, match in enumerate(results.get("matches", [])):
                meta = match.get("metadata", {})
                context_data.append(f"[Product {i+1}] {json.dumps(meta)}")
                    
            return "\n".join(context_data) if context_data else "No relevant products found."
            
        except Exception as e:
            return f"Error searching for products: {str(e)}"
    
    def _handle_semantic_query(self, query: str) -> str:
        """Handle semantic questions with broad vector search"""
        try:
            intent_sys_prompt = "Extract purely the search keywords from this user query. No formatting, no chat. Just keywords."
            search_intent = self._call_llm(intent_sys_prompt, query)
            
            if not self.index:
                return "Vector database is not initialized."
            
            # Use broader search for semantic queries
            query_emb = self._get_embeddings([search_intent])[0]
            results = self.index.query(vector=query_emb, top_k=25, include_metadata=True)
            
            context_data = []
            for i, match in enumerate(results.get("matches", [])):
                meta = match.get("metadata", {})
                context_data.append(f"[Row {i+1}] {json.dumps(meta)}")
                    
return "\n".join(context_data) if context_data else "No relevant database records found."
            
        except Exception as e:
            return f"Error performing semantic search: {str(e)}"
    
    def module_c_business_auditor(self, scraped_data: dict) -> str:
        """Module C: Compare & Suggest against SEO/CRO best practices."""
        system_prompt = f"""You are a Principal E-Commerce Business Analyst AI.
You help the store owner understand their sales, returns, and customer satisfaction by chatting with them.
Answer the user's question directly, clearly, and concisely based ONLY on the following context block.

CRITICAL VALIDATION RULES:
1. For inventory questions: NEVER say "0 products in stock" unless data explicitly shows this
2. For category questions: ALWAYS report ALL categories found in data
3. For count questions: Provide exact numbers from context, don't extrapolate
4. For percentage questions: Calculate from actual data provided
5. If data seems incomplete: State limitations clearly

system_prompt = f"""You are a Principal E-Commerce Business Analyst AI.
You help the store owner understand their sales, returns, and customer satisfaction by chatting with them.
Answer the user's question directly, clearly, and concisely based ONLY on the following context block.

CRITICAL VALIDATION RULES:
1. For inventory questions: NEVER say "0 products in stock" unless data explicitly shows this
2. For category questions: ALWAYS report ALL categories found in data
3. For count questions: Provide exact numbers from context, don't extrapolate
4. For percentage questions: Calculate from actual data provided
5. If data seems incomplete: State limitations clearly

For categorical questions, use the comprehensive aggregated data provided.
For product questions, use specific product details.
For semantic questions, use provided context samples.
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
    
    def chat_with_data(self, query: str, session_history: list = None) -> str:
        if not session_history:
            session_history = []
            
        augmented_query = query
        if session_history:
            history_text = "\n".join([f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in session_history[-4:]])
            augmented_query = f"Chat History:\n{history_text}\n\nLatest Query: {query}\n\n(Note: Answer or write code based on 'Latest Query', but use 'Chat History' to resolve any 'it', 'they', or context)"
            
        routing_sys = """You are an intelligent query classifier for an e-commerce RAG system. Classify the user's query into exactly one of these categories:

CATEGORICAL: Questions about categories, types, counts, totals, averages, or any aggregate data
Examples: "How many categories?", "What categories do you have?", "Total products", "Average rating", "Count of returned items"

PRODUCT_SPECIFIC: Questions about specific products, product details, comparisons, or product features
Examples: "Tell me about wireless mouse", "Compare TV and keyboard", "Product details for P0001", "Kitchen products"

SEMANTIC: General questions, reviews, opinions, reasons, or any text-based analysis
Examples: "Why are items returned?", "What do customers think?", "Best rated products", "Customer feedback"

Only output the exact category name: CATEGORICAL, PRODUCT_SPECIFIC, or SEMANTIC"""
        classification = self._call_llm(routing_sys, augmented_query).strip().upper()
        
        context_block = ""
        
        if "CATEGORICAL" in classification:
            # Use metadata-based analytical approach for categorical questions
            context_block = self._handle_categorical_query(augmented_query)
        elif "PRODUCT_SPECIFIC" in classification:
            # Use targeted vector search for product-specific questions
            context_block = self._handle_product_query(augmented_query)
        else:
            # Use semantic search for general questions
            context_block = self._handle_semantic_query(augmented_query)
    
    def _handle_categorical_query(self, query: str) -> str:
