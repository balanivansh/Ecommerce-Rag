"use client";

import { useState, useEffect, useRef } from "react";
import { MessageSquare, TrendingUp, Upload, Globe, ShoppingBag, Terminal, ExternalLink } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function Home() {
  const [activeTab, setActiveTab] = useState("chat");
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [statusMsg, setStatusMsg] = useState({ text: "", type: "" });
  const [loading, setLoading] = useState(false);

  // Server Status for Lazy Wake-up
  const [serverStatus, setServerStatus] = useState<"waking" | "online" | "offline">("waking");
  const [serverStatusText, setServerStatusText] = useState("Waking up server...");

  // Unified Chat Interface
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<{ role: string, content: string }[]>([
    { role: "assistant", content: "AI Store Analyst online. Awaiting data ingestion or query..." }
  ]);
  
  // Auto-scroll functionality
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  // Module C
  const [scrapedTemp, setScrapedTemp] = useState<any>(null);
  const [modCResult, setModCResult] = useState<string>("");

  // Custom Cursor State
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Lazy Wake-up Effect
  const wakeUpServer = async () => {
    setServerStatus("waking");
    setServerStatusText("Waking up server...");
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ecommerce-rag.onrender.com"}/api/health`, { method: "GET" });
      const data = await res.json();
      if (!data.vector_db_synced) {
        showMsg("Data Graph Uninitialized. Please Sync Data CSV.", "error");
        setMessages([
          { role: "assistant", content: "⚠️ SYSTEM NOTICE: The Vector Database is empty. I cannot answer general semantic questions until you upload Store Data CSV via the 'Sync Data' action in the topology menu." }
        ]);
      }
      setServerStatus("online");
      setServerStatusText("Server online");
    } catch (error) {
      setServerStatus("offline");
      setServerStatusText("Server offline");
    }
  };

  useEffect(() => {
    wakeUpServer();
    const interval = setInterval(wakeUpServer, 30000);
    return () => clearInterval(interval);
  }, []);

  const showMsg = (text: string, type: "success" | "error" = "success") => {
    setStatusMsg({ text, type });
    setTimeout(() => setStatusMsg({ text: "", type: "" }), 5000);
  };

  const processUpload = async (file: File) => {
    if (!file.name.endsWith(".csv")) return showMsg("Only CSV files are allowed.", "error");

    // Prevent upload if server is not online
    if (serverStatus !== 'online') {
      if (serverStatus === 'waking') {
        showMsg("Server is waking up. Please wait a moment...", "error");
      } else {
        showMsg("Server is unavailable. Please refresh the page.", "error");
      }
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      setLoading(true);
      showMsg("Initializing upload...", "success");

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ecommerce-rag.onrender.com"}/api/ingest/csv`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (!res.ok) {
        showMsg(data.detail || "Upload failed", "error");
        setLoading(false);
        return;
      }

      showMsg("✅ CSV uploaded successfully! Vector database syncing...", "success");
      setLoading(false);
      setTimeout(wakeUpServer, 3000);
    } catch (error: any) {
      console.error("Upload error:", error);
      showMsg("Upload failed. Please try again.", "error");
      setLoading(false);
    }
  };

  const uploadCSV = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processUpload(file);
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const file = e.dataTransfer.files[0];
    if (file) processUpload(file);
  };

  const [isDragging, setIsDragging] = useState(false);

  const sendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!chatInput.trim()) return;

    // Prevent RAG queries if server is not online
    if (serverStatus !== 'online') {
      if (serverStatus === 'waking') {
        showMsg("Server is waking up. Please wait a moment...", "error");
      } else {
        showMsg("Server is unavailable. Please refresh the page.", "error");
      }
      return;
    }

    const userQuery = chatInput;
    const currentMessages = [...messages];

    setMessages([...currentMessages, { role: "user", content: userQuery }]);
    setChatInput("");
    setLoading(true);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ecommerce-rag.onrender.com"}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userQuery, history: currentMessages }),
      });
      const data = await res.json();

      if (res.ok) {
        setMessages(prev => [...prev, { role: "assistant", content: data.response }]);
      } else {
        console.error('Chat API error:', res.status, data);
        showMsg(data.detail || "Error connecting to AI.", "error");
      }
    } catch (error: any) {
      console.error('Chat fetch error:', error);
      showMsg("Backend connection error.", "error");
    } finally {
      setLoading(false);
    }
  };

  const scrapeSite = async () => {
    if (!scrapeUrl.trim()) return showMsg("Please enter a valid URL.", "error");
    if (!scrapeUrl.startsWith("http")) return showMsg("URL must start with http:// or https://", "error");

    try {
      setLoading(true);
      setModCResult("");
      setScrapedTemp({ url: scrapeUrl });

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ecommerce-rag.onrender.com"}/api/audit/seo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: scrapeUrl }),
      });
      const data = await res.json();

      if (!res.ok) {
        showMsg(data.detail || "Audit failed", "error");
        setLoading(false);
        return;
      }

      showMsg("✅ SEO audit completed!", "success");
      setModCResult(data.result);
      setLoading(false);
    } catch (error: any) {
      console.error("Scrape error:", error);
      showMsg("Scraping failed. Please try again.", "error");
      setLoading(false);
    }
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  return (
    <div className="min-h-screen bg-black text-[#fcfcfc] font-sans selection:bg-[#d1ff26] selection:text-black overflow-hidden relative">

      {/* Custom Trailing Cursor */}
      <motion.div
        className="fixed top-0 left-0 w-8 h-8 rounded-full border border-[#d1ff26]/50 pointer-events-none z-[100] mix-blend-difference hidden md:block"
        animate={{ x: mousePos.x - 16, y: mousePos.y - 16 }}
        transition={{ type: "spring", stiffness: 200, damping: 20, mass: 0.5 }}
      />
      <motion.div
        className="fixed top-0 left-0 w-2 h-2 rounded-full bg-[#d1ff26] pointer-events-none z-[100] hidden md:block"
        animate={{ x: mousePos.x - 4, y: mousePos.y - 4 }}
        transition={{ type: "spring", stiffness: 500, damping: 25, mass: 0.1 }}
      />

      {/* Marquee Background Element */}
      <div className="absolute top-0 left-0 w-full overflow-hidden whitespace-nowrap opacity-[0.03] pointer-events-none z-0 user-select-none">
        <motion.div
          className="flex gap-8 text-[12rem] font-black font-grotesk tracking-tighter uppercase"
          animate={{ x: [0, -2000] }}
          transition={{ repeat: Infinity, ease: "linear", duration: 40 }}
        >
          <span>PRODUCT INSIGHTS</span>
          <span>INVENTORY ANALYTICS</span>
          <span>STORE INTELLIGENCE</span>
        </motion.div>
      </div>

      <div className="flex h-screen relative z-10 p-6 gap-6">

        {/* LEFT PANEL: NAVIGATION & INFRASTRUCTURE */}
        <motion.div
          initial={{ x: -50, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="w-80 bg-[#111] border border-[#222] rounded-[32px] flex flex-col p-8 relative overflow-hidden group"
        >
          {/* Subtle Glow */}
          <div className="absolute -top-32 -left-32 w-64 h-64 bg-[#d1ff26]/5 rounded-full blur-[80px] pointer-events-none transition-opacity duration-700 opacity-50 group-hover:opacity-100" />

          <div className="flex items-center gap-4 mb-8 relative z-10">
            <motion.div
              whileHover={{ rotate: 90 }}
              transition={{ type: "spring", stiffness: 200, damping: 10 }}
              className="h-12 w-12 bg-[#d1ff26] rounded-2xl flex items-center justify-center text-black"
            >
              <ShoppingBag size={24} strokeWidth={2.5} />
            </motion.div>
            <div className="flex-1">
              <h1 className="font-grotesk font-bold text-2xl tracking-tight leading-none text-white">StoreSight</h1>
              <p className="text-[10px] text-[#A0A0A0] font-bold tracking-[0.2em] uppercase mt-2">E-Commerce Intelligence</p>
            </div>
          </div>

          <div className="space-y-12 relative z-10 flex-1 overflow-y-auto pr-2 custom-scroll">

            {/* View Toggle */}
            <div className="flex flex-col gap-2">
              <h2 className="text-[10px] font-bold text-[#666] uppercase tracking-[0.2em] mb-2">Modules</h2>
              {[
                { id: "chat", label: "Product Analyst", icon: MessageSquare },
                { id: "business", label: "Market Audit", icon: TrendingUp },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-3 px-5 py-4 rounded-2xl text-sm font-bold transition-all duration-300 ${activeTab === tab.id
                    ? "bg-[#222] text-[#d1ff26] border border-[#333]"
                    : "text-[#888] hover:bg-[#1A1A1A] hover:text-white border border-transparent"
                    }`}
                >
                  <tab.icon size={18} strokeWidth={activeTab === tab.id ? 2.5 : 2} />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Infrastructure Source */}
            <div className="space-y-6">
              <h2 className="text-[10px] font-bold text-[#666] uppercase tracking-[0.2em]">Data Sources</h2>

              {/* Step-by-Step Guide */}
              <div className="bg-gradient-to-r from-[#d1ff26]/10 to-[#d1ff26]/5 border border-[#d1ff26]/20 rounded-2xl p-6 space-y-4">
                <div className="flex items-start gap-3">
                  <div className="bg-[#d1ff26] text-black rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">1</div>
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1">Download Sample CSV</h3>
                    <p className="text-xs text-[#A0A0A0]">Get our sample product catalog with 2000+ items to test the system</p>
                  </div>
                </div>
                
                <div className="flex items-start gap-3">
                  <div className="bg-[#d1ff26] text-black rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">2</div>
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1">Upload CSV File</h3>
                    <p className="text-xs text-[#A0A0A0]">Drag & drop or click the upload area below</p>
                  </div>
                </div>
                
                <div className="flex items-start gap-3">
                  <div className="bg-[#d1ff26] text-black rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">3</div>
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1">Wait for Processing</h3>
                    <p className="text-xs text-[#A0A0A0]">Watch the status bar for vector database sync completion</p>
                  </div>
                </div>
                
                <div className="flex items-start gap-3">
                  <div className="bg-[#d1ff26] text-black rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">4</div>
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1">Test Chat Interface</h3>
                    <p className="text-xs text-[#A0A0A0]">Ask questions about your products, categories, ratings, and more</p>
                  </div>
                </div>
              </div>

              {/* CSV Upload */}
              <div className="space-y-4 mt-6">
                <div className="bg-gradient-to-r from-[#222] to-[#1A1A1A] border border-[#333] rounded-2xl p-4">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="bg-[#d1ff26] text-black px-3 py-1 rounded-full text-xs font-bold">SAMPLE DATA</div>
                      <span className="text-sm font-bold text-white">Product Catalog (CSV)</span>
                    </div>
                    <a 
                      href="/sample_data.csv" 
                      download 
                      className="bg-[#d1ff26] hover:bg-white text-black hover:text-[#222] px-4 py-2 rounded-xl font-bold text-sm transition-all duration-300 flex items-center gap-2 group"
                    >
                      <ExternalLink size={16} className="group-hover:scale-110 transition-transform" />
                      Download Sample
                    </a>
                  </div>
                  <div className="text-xs text-[#888] mb-3">
                    <span className="text-[#d1ff26]">2,000+ products</span> • <span className="text-[#d1ff26]">4 categories</span> • <span className="text-[#d1ff26]">Ratings & Reviews</span>
                  </div>
                <label
                  onDragOver={onDragOver}
                  onDragLeave={onDragLeave}
                  onDrop={onDrop}
                  className={`flex flex-col items-center justify-center w-full p-6 border ${isDragging ? "border-solid border-[#d1ff26] bg-[#d1ff26]/10" : "border-dashed border-[#333]"} rounded-2xl hover:border-[#d1ff26] hover:bg-[#d1ff26]/5 transition-all duration-300 cursor-pointer group`}
                >
                  <div className="flex flex-col items-center gap-3">
                    <motion.div animate={isDragging ? { y: -10, scale: 1.1 } : { y: 0, scale: 1 }} transition={{ type: "spring" }}>
                      <Upload size={24} className={`${isDragging ? "text-[#d1ff26]" : "text-[#666]"} group-hover:text-[#d1ff26] transition-colors`} />
                    </motion.div>
                    <span className="text-xs text-[#888] font-bold uppercase tracking-wider group-hover:text-white transition-colors">
                      {isDragging ? "Drop to Upload" : "Drag & Drop or Click"}
                    </span>
                  </div>
                  <input type="file" accept=".csv" className="hidden" onChange={uploadCSV} />
                </label>
              </div>

              {/* Scraper Input */}
              <div className="space-y-3 pt-6 border-t border-[#222]">
                <span className="text-xs text-[#A0A0A0] font-medium">Competitor Analysis</span>
                <div className="flex bg-[#0A0A0A] border border-[#222] rounded-2xl overflow-hidden focus-within:border-[#d1ff26] transition-colors">
                  <input
                    type="text"
                    placeholder="https://..."
                    value={scrapeUrl}
                    onChange={(e) => setScrapeUrl(e.target.value)}
                    className="flex-1 bg-transparent px-4 py-3 text-sm text-white focus:outline-none placeholder-[#444]"
                  />
                  <button onClick={scrapeSite} className="bg-[#1A1A1A] hover:bg-[#d1ff26] hover:text-black transition-colors px-4 text-[#888]">
                    <Terminal size={16} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* RIGHT PANEL: MAIN INTERFACE */}
        <div className="flex-1 flex flex-col relative h-full">

          {/* Status Notifications */}
          <AnimatePresence>
            {statusMsg.text && (
              <motion.div
                initial={{ opacity: 0, y: -20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95, y: -10 }}
                className={`absolute top-0 right-0 z-50 px-6 py-4 rounded-2xl shadow-2xl backdrop-blur-xl border flex items-center gap-4 text-sm font-bold tracking-wide ${statusMsg.type === "success" ? "bg-[#d1ff26]/10 border-[#d1ff26]/30 text-[#d1ff26]" : "bg-red-500/10 border-red-500/30 text-red-500"
                  }`}
              >
                <div className={`w-2 h-2 rounded-full ${statusMsg.type === 'success' ? 'bg-[#d1ff26]' : 'bg-red-500'} animate-pulse`} />
                {statusMsg.text}
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence mode="wait">

            {/* --- CHAT INTERFACE --- */}
            {activeTab === "chat" && (
              <motion.div
                key="chat"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col h-full pl-6"
              >
                <div className="mb-8">
                  <h2 className="text-6xl font-black font-grotesk tracking-tighter text-white">Product <span className="text-[#d1ff26]">Intelligence.</span></h2>
                  <p className="text-[#888] mt-2 font-medium">Get AI-powered insights about your products, customers, and sales performance.</p>
                </div>

                <div className="flex-1 bg-[#111]/50 backdrop-blur-3xl border border-[#222] rounded-[32px] overflow-hidden flex flex-col relative shadow-2xl">

                  {loading && (
                    <div className="absolute inset-0 bg-black/40 backdrop-blur-sm z-40 flex items-center justify-center">
                      <div className="w-16 h-16 border-4 border-[#333] border-t-[#d1ff26] rounded-full animate-spin" />
                    </div>
                  )}

                  <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-8 space-y-8 custom-scroll">
                    {messages.map((msg, idx) => (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        key={idx}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                      >
                        <div className={`max-w-[75%] rounded-3xl p-6 ${msg.role === "user"
                          ? "bg-[#d1ff26] text-black rounded-br-sm shadow-[0_10px_40px_rgba(209,255,38,0.15)]"
                          : "bg-[#1A1A1A] text-[#dedede] rounded-bl-sm border border-[#333]"
                          }`}>
                          <p className={`text-base leading-relaxed ${msg.role === "user" ? "font-bold" : "font-medium"} whitespace-pre-wrap`}>
                            {msg.content}
                          </p>
                        </div>
                      </motion.div>
                    ))}
                  </div>

                  <div className="p-4 bg-[#111]">
                    <form onSubmit={sendMessage} className="relative flex items-center">
                      <div className="absolute left-6 text-[#666]">
                        <Terminal size={20} />
                      </div>
                      <input
                        type="text"
                        className="w-full bg-[#1A1A1A] border border-[#333] rounded-[24px] pl-14 pr-32 py-5 text-white placeholder-[#666] focus:outline-none focus:border-[#d1ff26] transition-colors font-medium text-lg shadow-inner"
                        placeholder="Type your command..."
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        disabled={loading}
                      />
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        type="submit"
                        disabled={loading || !chatInput.trim()}
                        className="absolute right-3 bg-[#d1ff26] hover:bg-white text-black px-6 py-3 rounded-[16px] font-bold tracking-wide disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        EXECUTE
                      </motion.button>
                    </form>
                  </div>
                </div>
              </motion.div>
            )}

            {/* --- AUDITOR INTERFACE --- */}
            {activeTab === "business" && (
              <motion.div
                key="business"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col h-full pl-6"
              >
                <div className="mb-8 flex justify-between items-end">
                  <div>
                    <h2 className="text-6xl font-black font-grotesk tracking-tighter text-white">Market <span className="text-[#d1ff26]">Intelligence.</span></h2>
                    <p className="text-[#888] mt-2 font-medium">
                      {scrapedTemp ? `Analyzing: ${scrapedTemp.url}` : "Analyze competitor products and market trends..."}
                    </p>
                  </div>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={scrapeSite}
                    disabled={loading || !scrapeUrl.trim()}
                    className="bg-[#d1ff26] hover:bg-white text-black hover:text-[#222] px-6 py-3 rounded-[16px] font-bold tracking-wide disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  >
                    <Globe size={16} />
                    AUDIT SITE
                  </motion.button>
                </div>

                <div className="flex-1 bg-[#1A1A1A]/80 backdrop-blur-xl border border-[#333] rounded-[32px] p-10 overflow-y-auto custom-scroll relative">
                  {modCResult ? (
                    <motion.div
                      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                      className="prose prose-invert max-w-none prose-p:text-[#CCC] prose-headings:text-white prose-headings:font-grotesk prose-strong:text-[#d1ff26]"
                    >
                      <pre className="font-sans whitespace-pre-wrap leading-loose text-[15px]">{modCResult}</pre>
                    </motion.div>
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-[#444] space-y-6">
                      <TrendingUp size={64} strokeWidth={1} />
                      <div className="text-center space-y-2">
                        <p className="text-lg font-medium tracking-wide">Ready for Market Analysis</p>
                        <p className="text-sm text-[#666]">Enter a competitor URL to generate insights</p>
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
