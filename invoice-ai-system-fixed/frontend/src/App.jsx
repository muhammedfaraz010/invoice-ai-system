import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import {
  LayoutDashboard, FileText, Upload, MessageSquare,
  Bell, LogOut, Menu, X, ShieldCheck, User, Settings, ChevronDown, Users, ClipboardList, ScrollText
} from "lucide-react";
import Dashboard from "./pages/Dashboard";
import UploadPage from "./pages/UploadPage";
import InvoicesPage from "./pages/InvoicesPage";
import ChatPage from "./pages/ChatPage";
import ActionsPage from "./pages/ActionsPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ProfilePage from "./pages/ProfilePage";
import SettingsPage from "./pages/SettingsPage";
import ManageUsersPage from "./pages/ManageUsersPage";
import UserWorkspacePage from "./pages/UserWorkspacePage";
import DeleteRequestsPage from "./pages/DeleteRequestsPage";
import NotificationsPage from "./pages/NotificationsPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import {
  clearAuth, getMe, getStoredToken, getStoredUser, storeAuth,
} from "./services/api";
import "./index.css";

function App() {
  const [token, setToken] = useState(getStoredToken());
  const [user, setUser] = useState(getStoredUser());
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [profileOpen, setProfileOpen] = useState(false);

  const handleLogout = () => {
    clearAuth();
    setToken(null);
    setUser(null);
  };

  const handleLogin = (payload) => {
    storeAuth(payload);
    setToken(payload.access_token);
    setUser(payload.user);
  };

  useEffect(() => {
    if (!token) return;
    getMe()
      .then((res) => {
        sessionStorage.setItem("user", JSON.stringify(res.data));
        setUser(res.data);
      })
      .catch(() => handleLogout());
  }, [token]);

  const navItems = [
    { to: "/", icon: <LayoutDashboard size={18} />, label: "Dashboard" },
    { to: "/chat", icon: <MessageSquare size={18} />, label: "AI Chat" },
    { to: "/actions", icon: <Bell size={18} />, label: "Actions" },
  ];

  const userOnlyItems = [
    { to: "/upload", icon: <Upload size={18} />, label: "Upload" },
    { to: "/invoices", icon: <FileText size={18} />, label: "Invoices" },
  ];

  const adminItems = [
    { to: "/manage-users", icon: <Users size={18} />, label: "Manage Users" },
    { to: "/delete-requests", icon: <ClipboardList size={18} />, label: "Delete Requests" },
    { to: "/audit-logs", icon: <ScrollText size={18} />, label: "Audit Logs" },
    { to: "/notifications", icon: <Bell size={18} />, label: "Notifications" },
    { to: "/settings", icon: <Settings size={18} />, label: "Settings" },
  ];

  const navLinkClass = ({ isActive }) =>
    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
      isActive
        ? "bg-gradient-to-r from-primary-600/80 to-cyan-600/80 text-white font-medium shadow-inner shadow-black/20"
        : "text-blue-200 hover:bg-white/5 hover:text-white"
    }`;

  return (
    <BrowserRouter>
      <Toaster position="top-right" />
      {!token ? (
        <Routes>
          <Route path="/login" element={<LoginPage onLogin={handleLogin} />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      ) : (
      <div className="flex h-screen bg-slate-950 font-sans relative overflow-hidden">
        {/* Ambient glow accents */}
        <div className="pointer-events-none fixed -top-32 left-1/3 w-[32rem] h-[32rem] bg-primary-600/10 rounded-full blur-3xl" />
        <div className="pointer-events-none fixed bottom-0 right-0 w-[28rem] h-[28rem] bg-cyan-600/10 rounded-full blur-3xl" />

        {/* Sidebar */}
        <aside
          className={`relative z-10 ${
            sidebarOpen ? "w-56" : "w-16"
          } bg-gradient-to-b from-slate-900 via-blue-950 to-slate-950 text-white flex flex-col transition-all duration-300 shadow-xl shadow-black/40 border-r border-blue-900/40`}
        >
          {/* Logo */}
          <div className="flex items-center gap-3 px-4 py-5 border-b border-blue-900/50">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-cyan-500 shrink-0">
              <ShieldCheck className="text-white" size={18} />
            </div>
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
          <nav className="flex-1 py-4 space-y-1 px-2 overflow-y-auto">
            {sidebarOpen && user?.role === "admin" && (
              <div className="px-3 pb-2 text-[11px] uppercase tracking-wide text-cyan-400/80">Admin Workspace</div>
            )}
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === "/"} className={navLinkClass}>
                {item.icon}
                {sidebarOpen && <span>{item.label}</span>}
              </NavLink>
            ))}
            {user?.role !== "admin" && userOnlyItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={navLinkClass}>
                {item.icon}
                {sidebarOpen && <span>{item.label}</span>}
              </NavLink>
            ))}
            {user?.role === "admin" && (
              <>
                {sidebarOpen && (
                  <div className="px-3 pt-5 pb-2 text-[11px] uppercase tracking-wide text-cyan-400/80">Manage Users</div>
                )}
                {adminItems.map((item) => (
                  <NavLink key={item.to} to={item.to} className={navLinkClass}>
                    {item.icon}
                    {sidebarOpen && <span>{item.label}</span>}
                  </NavLink>
                ))}
              </>
            )}
            {user?.role !== "admin" && (
              <NavLink to="/notifications" className={navLinkClass}>
                <Bell size={18} />
                {sidebarOpen && <span>Notifications</span>}
              </NavLink>
            )}
            {user?.role !== "admin" && (
              <NavLink to="/settings" className={navLinkClass}>
                <Settings size={18} />
                {sidebarOpen && <span>Settings</span>}
              </NavLink>
            )}
          </nav>

          {/* Logout */}
          <div className="p-3 border-t border-blue-900/50">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-blue-200 hover:bg-white/5 hover:text-white transition-colors"
            >
              <LogOut size={18} />
              {sidebarOpen && <span>Logout</span>}
            </button>
          </div>
        </aside>

        {/* Main */}
        <div className="relative z-10 flex-1 flex flex-col min-w-0">
          <header className="bg-slate-900/60 backdrop-blur-sm border-b border-blue-900/40 px-6 py-3 flex items-center justify-between">
            <div>
              <p className="text-sm text-blue-300">Welcome</p>
              <h1 className="text-lg font-semibold text-white">
                {user?.full_name || user?.username || "Invoice AI"}
              </h1>
            </div>
            <div className="relative">
              <button
                type="button"
                onClick={() => setProfileOpen((open) => !open)}
                className="flex items-center gap-2 rounded-lg border border-blue-800/50 px-3 py-2 text-sm text-blue-100 hover:bg-blue-900/40"
              >
                <span className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-cyan-500 text-white flex items-center justify-center">
                  <User size={16} />
                </span>
                <span className="hidden sm:block text-left">
                  <span className="block font-medium leading-tight text-white">{user?.full_name || user?.username}</span>
                  <span className="block text-xs text-blue-300 capitalize">{user?.role}</span>
                </span>
                <ChevronDown size={14} />
              </button>
              {profileOpen && (
                <div className="absolute right-0 mt-2 w-48 rounded-lg border border-blue-800/50 bg-slate-800 shadow-lg py-1 z-20">
                  <NavLink onClick={() => setProfileOpen(false)} to="/profile" className="block px-4 py-2 text-sm text-blue-100 hover:bg-blue-900/40">
                    Profile
                  </NavLink>
                  <NavLink onClick={() => setProfileOpen(false)} to="/settings" className="block px-4 py-2 text-sm text-blue-100 hover:bg-blue-900/40">
                    Settings
                  </NavLink>
                  <button onClick={handleLogout} className="w-full text-left px-4 py-2 text-sm text-danger-400 hover:bg-blue-900/40">
                    Logout
                  </button>
                </div>
              )}
            </div>
          </header>
          <main className="flex-1 overflow-auto">
            <Routes>
              <Route path="/" element={<Dashboard user={user} />} />
              <Route path="/upload" element={user?.role === "admin" ? <Navigate to="/" replace /> : <UploadPage />} />
              <Route path="/invoices" element={user?.role === "admin" ? <Navigate to="/" replace /> : <InvoicesPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/actions" element={<ActionsPage />} />
              <Route path="/profile" element={<ProfilePage user={user} onUserChange={setUser} />} />
              <Route path="/settings" element={<SettingsPage user={user} />} />
              <Route path="/manage-users" element={user?.role === "admin" ? <ManageUsersPage /> : <Navigate to="/" replace />} />
              <Route path="/users/:id" element={user?.role === "admin" ? <UserWorkspacePage /> : <Navigate to="/" replace />} />
              <Route path="/delete-requests" element={<DeleteRequestsPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/audit-logs" element={user?.role === "admin" ? <AuditLogsPage /> : <Navigate to="/" replace />} />
              <Route path="/login" element={<Navigate to="/" replace />} />
              <Route path="/register" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </main>
        </div>
      </div>
      )}
    </BrowserRouter>
  );
}

export default App;