import React, { useState, useRef, useEffect } from "react";
import { queryChatbot } from "../services/api";
import { Send, Bot, User, Loader, Lightbulb, MessageSquare } from "lucide-react";

const SUGGESTIONS = [
  "Show all invoices above ₹50,000",
  "Which vendor billed the most this month?",
  "List all invoices with missing GSTIN",
  "Are there any duplicate invoices?",
  "What is the total spend for this quarter?",
  "Show invoices from vendor XYZ",
];

const Message = ({ msg }) => {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
        isUser ? "bg-blue-600" : "bg-gray-700"
      }`}>
        {isUser ? <User size={14} className="text-white" /> : <Bot size={14} className="text-white" />}
      </div>
      <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm ${
        isUser
          ? "bg-blue-600 text-white rounded-tr-sm"
          : "bg-white border border-gray-100 text-gray-800 rounded-tl-sm shadow-sm"
      }`}>
        <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
        {msg.sources?.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <p className="text-xs text-gray-400 mb-1">Sources:</p>
            {msg.sources.map((s, i) => (
              <span key={i} className="inline-block text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded mr-1 mb-1">
                {s.invoice_number || s.invoice_id?.slice(0,8)}
                {s.vendor_name ? ` · ${s.vendor_name}` : ""}
              </span>
            ))}
          </div>
        )}
        <p className={`text-xs mt-1 ${isUser ? "text-blue-200" : "text-gray-400"}`}>
          {new Date(msg.ts).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
};

export default function ChatPage() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "👋 Hello! I'm your Invoice AI assistant. Ask me anything about your invoices — vendor spend, compliance issues, duplicates, totals, and more.",
      ts: Date.now(),
      sources: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (question) => {
    const q = question || input.trim();
    if (!q || loading) return;
    setInput("");

    const userMsg = { role: "user", content: q, ts: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await queryChatbot(q);
      setMessages(prev => [...prev, {
        role: "assistant",
        content: res.data.answer,
        sources: res.data.sources || [],
        ts: Date.now(),
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "⚠️ Sorry, I couldn't process your query. Please ensure the backend is running and OpenAI API key is configured.",
        sources: [],
        ts: Date.now(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl flex items-center justify-center">
            <MessageSquare className="text-white" size={18} />
          </div>
          <div>
            <h1 className="font-bold text-gray-900">Invoice AI Chat</h1>
            <p className="text-xs text-gray-500">RAG-powered • Searches your invoice database</p>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
            <span className="text-xs text-gray-500">Online</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map((msg, i) => <Message key={i} msg={msg} />)}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center">
              <Bot size={14} className="text-white" />
            </div>
            <div className="bg-white border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2 text-gray-400">
                <Loader size={14} className="animate-spin" />
                <span className="text-sm">Searching invoices and generating answer...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {messages.length <= 1 && (
        <div className="px-6 pb-3">
          <div className="flex items-center gap-2 mb-2">
            <Lightbulb size={13} className="text-yellow-500" />
            <span className="text-xs text-gray-500 font-medium">Try asking</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s, i) => (
              <button
                key={i}
                onClick={() => send(s)}
                className="text-xs bg-white border border-gray-200 hover:border-blue-400 hover:text-blue-600 text-gray-600 px-3 py-1.5 rounded-full transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="bg-white border-t border-gray-100 px-6 py-4">
        <div className="flex gap-3 items-end">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask about your invoices... (Enter to send)"
            rows={1}
            className="flex-1 border border-gray-300 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            style={{ minHeight: "44px", maxHeight: "120px" }}
          />
          <button
            onClick={() => send()}
            disabled={!input.trim() || loading}
            className="w-11 h-11 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 flex items-center justify-center transition-colors shrink-0"
          >
            <Send size={16} className={input.trim() ? "text-white" : "text-gray-400"} />
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2 text-center">
          Answers are generated from your invoice database using RAG
        </p>
      </div>
    </div>
  );
}
