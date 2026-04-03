import requests
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def keep_render_awake():
    """Keep Render backend awake by making periodic requests"""
    backend_url = "https://ecommerce-rag.onrender.com/api/health"
    
    while True:
        try:
            response = requests.get(backend_url, timeout=10)
            if response.status_code == 200:
                logging.info(f"✅ Backend awake - Status: {response.text}")
            else:
                logging.warning(f"⚠️ Backend returned status: {response.status_code}")
        except Exception as e:
            logging.error(f"❌ Failed to ping backend: {str(e)}")
        
        # Wait 10 minutes (Render free tier sleep time is ~15 minutes)
        time.sleep(600)  # 10 minutes

if __name__ == "__main__":
    logging.info("🚀 Starting Render keep-alive service...")
    logging.info("📊 Backend URL: https://ecommerce-rag.onrender.com/api/health")
    logging.info("⏰ Pinging every 10 minutes to prevent sleep")
    keep_render_awake()
