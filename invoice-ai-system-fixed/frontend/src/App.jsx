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
    { to: "/upload", icon: <Upload size={18} />, label: "Upload" },
    { to: "/invoices", icon: <FileText size={18} />, label: "Invoices" },
    { to: "/chat", icon: <MessageSquare size={18} />, label: "AI Chat" },
    { to: "/actions", icon: <Bell size={18} />, label: "Actions" },
  ];

  const adminItems = [
    { to: "/manage-users", icon: <Users size={18} />, label: "Manage Users" },
    { to: "/delete-requests", icon: <ClipboardList size={18} />, label: "Delete Requests" },
    { to: "/audit-logs", icon: <ScrollText size={18} />, label: "Audit Logs" },
    { to: "/notifications", icon: <Bell size={18} />, label: "Notifications" },
    { to: "/settings", icon: <Settings size={18} />, label: "Settings" },
  ];

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
            {sidebarOpen && user?.role === "admin" && (
              <div className="px-3 pb-2 text-[11px] uppercase tracking-wide text-blue-300">Admin Workspace</div>
            )}
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
            {user?.role === "admin" && (
              <>
                {sidebarOpen && (
                  <div className="px-3 pt-5 pb-2 text-[11px] uppercase tracking-wide text-blue-300">Manage Users</div>
                )}
                {adminItems.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
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
              </>
            )}
            {user?.role !== "admin" && (
              <NavLink
                to="/notifications"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                    isActive
                      ? "bg-white/20 text-white font-medium"
                      : "text-blue-200 hover:bg-white/10 hover:text-white"
                  }`
                }
              >
                <Bell size={18} />
                {sidebarOpen && <span>Notifications</span>}
              </NavLink>
            )}
            {user?.role !== "admin" && (
              <NavLink
                to="/settings"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                    isActive
                      ? "bg-white/20 text-white font-medium"
                      : "text-blue-200 hover:bg-white/10 hover:text-white"
                  }`
                }
              >
                <Settings size={18} />
                {sidebarOpen && <span>Settings</span>}
              </NavLink>
            )}
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
        <div className="flex-1 flex flex-col min-w-0">
          <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Welcome</p>
              <h1 className="text-lg font-semibold text-gray-900">
                {user?.full_name || user?.username || "Invoice AI"}
              </h1>
            </div>
            <div className="relative">
              <button
                type="button"
                onClick={() => setProfileOpen((open) => !open)}
                className="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                <span className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center">
                  <User size={16} />
                </span>
                <span className="hidden sm:block text-left">
                  <span className="block font-medium leading-tight">{user?.full_name || user?.username}</span>
                  <span className="block text-xs text-gray-400 capitalize">{user?.role}</span>
                </span>
                <ChevronDown size={14} />
              </button>
              {profileOpen && (
                <div className="absolute right-0 mt-2 w-48 rounded-lg border border-gray-100 bg-white shadow-lg py-1 z-20">
                  <NavLink onClick={() => setProfileOpen(false)} to="/profile" className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                    Profile
                  </NavLink>
                  <NavLink onClick={() => setProfileOpen(false)} to="/settings" className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                    Settings
                  </NavLink>
                  <button onClick={handleLogout} className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50">
                    Logout
                  </button>
                </div>
              )}
            </div>
          </header>
          <main className="flex-1 overflow-auto">
            <Routes>
              <Route path="/" element={<Dashboard user={user} />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/invoices" element={<InvoicesPage />} />
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
