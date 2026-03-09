import requests
import time

def evaluate_model():
    questions = [
        "Hello, I am the owner of this store. What is the total number of products we have?",
        "How many categories do we have?",
        "Can you list what they are?",
        "What is our most returned product?",
        "Why is it being returned so much?",
        "How many total returns have we had across all products?",
        "What is the average rating of our products?",
        "Which product has the absolute highest rating, and what is its rating?",
        "Can you give me a summary of how my business is doing based on this data?",
        "What should I focus on improving next month?"
    ]
    
    history = []
    
    with open("eval_out.md", "w", encoding="utf-8") as f:
        f.write("# RAG LLM Context & Capability Evaluation\n\n")
        f.write("## Simulated Company Owner Conversation\n\n")
        
        for i, q in enumerate(questions):
            f.write(f"**Q{i+1}:** {q}\n")
            
            start_time = time.time()
            try:
                res = requests.post(
                    "http://localhost:8000/api/chat",
                    json={"query": q, "history": history}
                )
                res.raise_for_status()
                ans = res.json().get("response", "No response field in JSON.")
            except Exception as e:
                ans = f"API Error: {str(e)}"
                
            elapsed = time.time() - start_time
            
            f.write(f"**A{i+1}:** {ans}\n")
            f.write(f"*(Latency: {elapsed:.2f}s)*\n\n")
            print(f"Completed Q{i+1}")
            
            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": ans})
            
        f.write("--- EVALUATION COMPLETE ---\n")

if __name__ == "__main__":
    evaluate_model()
