"use client";

import { useState, useEffect } from "react";
import { MessageSquare, Search, BarChart3, TrendingUp, Key, Upload, Globe, Settings, ShoppingBag, Terminal } from "lucide-react";

export default function Home() {
  const [activeTab, setActiveTab] = useState("chat");
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [statusMsg, setStatusMsg] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(false);

  // Unified Chat Interface
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<{ role: string, content: string }[]>([
    { role: "assistant", content: "Hello! I am your AI Store Analyst. I can answer questions about your inventory, calculate return rates, or analyze customer sentiment based on your uploaded data. How can I help you today?" }
  ]);

  // Module C
  const [scrapedTemp, setScrapedTemp] = useState<any>(null);
  const [modCResult, setModCResult] = useState<string>("");

  const showMsg = (text: string, type: "success" | "error" = "success") => {
    setStatusMsg({ text, type });
    setTimeout(() => setStatusMsg({ text: "", type: "" }), 5000);
  };

  const uploadCSV = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    const formData = new FormData();
    formData.append("file", e.target.files[0]);

    try {
      setLoading(true);
      showMsg("Initializing upload...", "success");

      // Start background upload
      const res = await fetch("https://ecommerce-rag.onrender.com/api/ingest/csv", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (!res.ok) {
        showMsg(data.detail, "error");
        setLoading(false);
        return;
      }

      const taskId = data.task_id;
      let isDone = false;

      // Poll until completed or failed
      while (!isDone) {
        await new Promise(r => setTimeout(r, 800)); // Poll every 800ms

        const statusRes = await fetch(`https://ecommerce-rag.onrender.com/api/task/status/${taskId}`);
        if (!statusRes.ok) continue;

        const statusData = await statusRes.json();

        if (statusData.status === "processing") {
          // Update toast with dynamic message from backend (e.g. "Processing 54/500...")
          setStatusMsg({ text: statusData.message || "Processing data...", type: "success" });
        } else if (statusData.status === "completed") {
          showMsg(statusData.message, "success");
          isDone = true;
        } else if (statusData.status === "failed") {
          showMsg(statusData.message, "error");
          isDone = true;
        }
      }
    } catch (e) {
      showMsg("Backend connection error.", "error");
    } finally {
      setLoading(false);
    }
  };

  const scrapeSite = async () => {
    if (!scrapeUrl) return;
    try {
      setLoading(true);
      const res = await fetch("https://ecommerce-rag.onrender.com/api/ingest/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: scrapeUrl }),
      });
      const data = await res.json();
      if (res.ok) {
        setScrapedTemp(data.data);
        showMsg(`Scraped: ${data.data.title}`, "success");
      } else showMsg(data.detail, "error");
    } catch (e) {
      showMsg("Backend error.", "error");
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!chatInput.trim()) return;

    const userQuery = chatInput;
    const currentMessages = [...messages];

    // Optimistic UI update
    setMessages([...currentMessages, { role: "user", content: userQuery }]);
    setChatInput("");
    setLoading(true);

    try {
      const res = await fetch("https://ecommerce-rag.onrender.com/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userQuery, history: currentMessages }),
      });
      const data = await res.json();

      if (res.ok) {
        setMessages(prev => [...prev, { role: "assistant", content: data.response }]);
      } else {
        showMsg(data.detail || "Error connecting to AI.", "error");
      }
    } catch (error) {
      showMsg("Backend connection error.", "error");
    } finally {
      setLoading(false);
    }
  };

  const runModC = async () => {
    if (!scrapedTemp) return showMsg("Please scrape a URL first.", "error");
    try {
      setLoading(true);
      const res = await fetch("https://ecommerce-rag.onrender.com/api/modules/auditor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scraped_data: scrapedTemp }),
      });
      const data = await res.json();
      if (res.ok) setModCResult(data.report);
      else showMsg(data.detail, "error");
    } catch (e) {
      showMsg("Backend error.", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 font-sans selection:bg-indigo-500">
      <div className="flex h-screen overflow-hidden">
        {/* SIDEBAR */}
        <div className="w-80 bg-slate-800/50 border-r border-slate-700/50 flex flex-col p-6 overflow-y-auto">
          <div className="flex items-center gap-3 mb-8">
            <div className="h-10 w-10 bg-indigo-500 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <ShoppingBag className="text-white" size={24} />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight tracking-tight">E-Com RAG</h1>
              <p className="text-xs text-slate-400 font-medium tracking-wide uppercase">Intelligence Engine</p>
            </div>
          </div>

          <div className="space-y-8">
            <section>
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <Globe size={14} /> Data Sources
              </h2>

              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-700/50">
                  <span className="text-sm">Store Data Template (CSV)</span>
                  <a
                    href="/sample_data.csv"
                    download
                    className="px-3 py-1.5 rounded-md text-xs font-medium transition-colors bg-indigo-500 hover:bg-indigo-600 text-white inline-block"
                  >
                    Download
                  </a>
                </div>

                <div className="space-y-2">
                  <label className="text-sm text-slate-300 block">Upload Orders/Returns CSV</label>
                  <label className="flex items-center justify-center w-full p-4 border-2 border-dashed border-slate-700 rounded-xl hover:border-indigo-500 hover:bg-indigo-500/5 transition-all cursor-pointer group">
                    <div className="flex flex-col items-center gap-2">
                      <Upload size={20} className="text-slate-500 group-hover:text-indigo-400 transition-colors" />
                      <span className="text-xs text-slate-400 font-medium">Click to upload</span>
                    </div>
                    <input type="file" accept=".csv" className="hidden" onChange={uploadCSV} />
                  </label>
                </div>

                <div className="space-y-2 pt-2">
                  <label className="text-sm text-slate-300 block">Audit Landing Page (URL)</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="https://..."
                      value={scrapeUrl}
                      onChange={(e) => setScrapeUrl(e.target.value)}
                      className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 text-sm focus:border-indigo-500 focus:outline-none transition-colors"
                    />
                    <button onClick={scrapeSite} className="bg-slate-700 hover:bg-slate-600 px-3 py-2 rounded-lg transition-colors">
                      <Terminal size={16} />
                    </button>
                  </div>

                  <div className="pt-4 border-t border-slate-700/50 mt-4">
                    <label className="text-xs text-slate-400 block mb-2">Or load example targets:</label>
                    <div className="flex flex-col gap-2">
                      <button
                        onClick={() => {
                          setScrapedTemp({
                            url: "https://www.flipkart.com/example-shirt",
                            title: "Men's Cotton Solid Casual Shirt - Buy Online",
                            headings: ["Product Details", "Customer Reviews", "Related Items"],
                            description: "Buy Men's Cotton Solid Casual Shirt online at best prices. Fast Delivery, Easy Returns.",
                            full_text: "Upgrade your wardrobe with this premium pure cotton shirt. Featuring a modern slim fit, breathable fabric, and durable stitching. Perfect for formal and casual occasions. Buy now and get 20% off on your first order. 30-day easy return policy."
                          });
                          showMsg("Loaded Example Flipkart Target", "success");
                        }}
                        className="text-left px-3 py-2 text-xs bg-slate-900 border border-slate-700 rounded-lg hover:border-indigo-500 hover:bg-indigo-500/10 transition-colors"
                      >
                        🛍️ Example Flipkart Product
                      </button>
                      <button
                        onClick={() => {
                          setScrapedTemp({
                            url: "https://www.myntra.com/example-shoes",
                            title: "Nike Air Zoom Pegasus - Running Shoes for Men",
                            headings: ["Product Description", "Material & Care", "Reviews"],
                            description: "Nike Air Zoom Pegasus running shoes. Experience unparalleled comfort and energy return.",
                            full_text: "Built for speed and comfort. The Nike Air Zoom Pegasus features responsive cushioning and a breathable mesh upper. Ideal for long-distance running. Check size chart carefully before ordering small sizes."
                          });
                          showMsg("Loaded Example Myntra Target", "success");
                        }}
                        className="text-left px-3 py-2 text-xs bg-slate-900 border border-slate-700 rounded-lg hover:border-indigo-500 hover:bg-indigo-500/10 transition-colors"
                      >
                        👟 Example Myntra Product
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>

        {/* MAIN CONTENT */}
        <div className="flex-1 flex flex-col relative overflow-hidden bg-slate-900">

          {/* Status Toast */}
          {statusMsg.text && (
            <div className={`absolute top-6 mx-auto left-0 right-0 w-max max-w-md z-50 px-4 py-3 rounded-lg shadow-xl shadow-black/20 text-sm font-medium border flex items-center gap-3 animate-in fade-in slide-in-from-top-4 ${statusMsg.type === "success" ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" : "bg-red-500/10 border-red-500/20 text-red-400"
              }`}>
              <div className={`w-2 h-2 rounded-full ${statusMsg.type === 'success' ? 'bg-emerald-400' : 'bg-red-400'} animate-pulse`} />
              {statusMsg.text}
            </div>
          )}

          {/* Fixed Header with Navigation */}
          <div className="px-8 pt-8 pb-4 border-b border-slate-800">
            <h1 className="text-2xl font-bold mb-6 tracking-tight">Business Intelligence Dashboard</h1>
            <div className="flex gap-2">
              {[
                { id: "chat", label: "AI Store Analyst", icon: MessageSquare },
                { id: "business", label: "SEO & Growth", icon: TrendingUp },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === tab.id
                    ? "bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                    }`}
                >
                  <tab.icon size={16} />
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Scrollable Content Area */}
          <div className="flex-1 overflow-y-auto p-8 relative">

            {/* Loading Overlay */}
            {loading && (
              <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm z-40 flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                  <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
                  <span className="text-sm font-medium text-slate-300 animate-pulse">Running analysis...</span>
                </div>
              </div>
            )}

            {/* MODULE A/B: Unified Chat Interface */}
            {activeTab === "chat" && (
              <div className="max-w-4xl mx-auto h-[calc(100vh-140px)] flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500">
                {/* Chat Messages Area */}
                <div className="flex-1 bg-slate-800/30 border border-slate-700/50 rounded-t-2xl p-6 overflow-y-auto space-y-4">
                  {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                      <div className={`max-w-[80%] rounded-2xl px-5 py-3 ${msg.role === "user"
                        ? "bg-indigo-500 text-white rounded-br-none"
                        : "bg-slate-700/50 text-slate-200 rounded-bl-none border border-slate-600/50"
                        }`}>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                      </div>
                    </div>
                  ))}
                  {loading && (
                    <div className="flex justify-start">
                      <div className="bg-slate-700/50 rounded-2xl rounded-bl-none px-5 py-3 border border-slate-600/50 flex space-x-1">
                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" />
                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75" />
                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150" />
                      </div>
                    </div>
                  )}
                </div>

                {/* Chat Input Area */}
                <div className="bg-slate-800 border border-slate-700/50 rounded-b-2xl p-4">
                  <form onSubmit={sendMessage} className="flex gap-3">
                    <input
                      type="text"
                      className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all placeholder-slate-500"
                      placeholder="Ask about inventory, returns, or sentiment..."
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      disabled={loading}
                    />
                    <button
                      type="submit"
                      disabled={loading || !chatInput.trim()}
                      className="bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl font-medium text-sm transition-all shadow-lg shadow-indigo-500/20 flex items-center gap-2"
                    >
                      <Terminal size={18} />
                      Ask Analyst
                    </button>
                  </form>
                </div>
              </div>
            )}
            {/* MODULE C: Business Auditor */}
            {activeTab === "business" && (
              <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="flex items-center justify-between bg-slate-800/30 border border-slate-700/50 rounded-2xl p-6">
                  <div>
                    <h2 className="text-lg font-semibold mb-1">SEO & Page Metrics</h2>
                    <p className="text-sm text-slate-400">
                      {scrapedTemp ? `Target: ${scrapedTemp.url}` : "No page target scraped yet. Start in sidebar."}
                    </p>
                  </div>
                  <button onClick={runModC} disabled={!scrapedTemp} className={`px-6 py-3 rounded-xl font-medium transition-all ${scrapedTemp ? 'bg-indigo-500 hover:bg-indigo-600 shadow-lg shadow-indigo-500/20' : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                    }`}>
                    Audit Architecture
                  </button>
                </div>

                {modCResult && (
                  <div className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-8 animate-in fade-in">
                    <div className="prose prose-invert prose-slate max-w-none prose-headings:text-indigo-300 prose-a:text-indigo-400 prose-strong:text-emerald-400">
                      <pre className="whitespace-pre-wrap font-sans text-sm text-slate-300 leading-loose">{modCResult}</pre>
                    </div>
                  </div>
                )}
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
