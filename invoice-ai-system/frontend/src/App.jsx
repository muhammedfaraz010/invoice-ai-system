import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import {
  LayoutDashboard, FileText, Upload, MessageSquare,
  Bell, LogOut, Menu, X, ShieldCheck
} from "lucide-react";
import Dashboard from "./pages/Dashboard";
import UploadPage from "./pages/UploadPage";
import InvoicesPage from "./pages/InvoicesPage";
import ChatPage from "./pages/ChatPage";
import ActionsPage from "./pages/ActionsPage";
import LoginPage from "./pages/LoginPage";
import "./index.css";

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const handleLogout = () => {
    localStorage.removeItem("token");
    setToken(null);
  };

  const navItems = [
    { to: "/", icon: <LayoutDashboard size={18} />, label: "Dashboard" },
    { to: "/upload", icon: <Upload size={18} />, label: "Upload" },
    { to: "/invoices", icon: <FileText size={18} />, label: "Invoices" },
    { to: "/chat", icon: <MessageSquare size={18} />, label: "AI Chat" },
    { to: "/actions", icon: <Bell size={18} />, label: "Actions" },
  ];

  if (!token) return <LoginPage onLogin={setToken} />;

  return (
    <BrowserRouter>
      <Toaster position="top-right" />
      <div className="flex h-screen bg-gray-50 font-sans">
        {/* Sidebar */}
        <aside
          className={`${
            sidebarOpen ? "w-56" : "w-16"
          } bg-gradient-to-b from-blue-900 to-blue-800 text-white flex flex-col transition-all duration-300`}
        >
          {/* Logo */}
          <div className="flex items-center gap-3 px-4 py-5 border-b border-blue-700">
            <ShieldCheck className="text-blue-300 shrink-0" size={24} />
            {sidebarOpen && (
              <span className="font-bold text-sm tracking-wide">Invoice AI</span>
            )}
            <button
              className="ml-auto text-blue-300 hover:text-white"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
            </button>
          </div>

          {/* Nav */}
          <nav className="flex-1 py-4 space-y-1 px-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                    isActive
                      ? "bg-white/20 text-white font-medium"
                      : "text-blue-200 hover:bg-white/10 hover:text-white"
                  }`
                }
              >
                {item.icon}
                {sidebarOpen && <span>{item.label}</span>}
              </NavLink>
            ))}
          </nav>

          {/* Logout */}
          <div className="p-3 border-t border-blue-700">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-blue-200 hover:bg-white/10 hover:text-white transition-colors"
            >
              <LogOut size={18} />
              {sidebarOpen && <span>Logout</span>}
            </button>
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/invoices" element={<InvoicesPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/actions" element={<ActionsPage />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;