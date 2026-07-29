import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShieldCheck, Eye, EyeOff } from "lucide-react";
import { login } from "../services/api";
import toast from "react-hot-toast";

export default function LoginPage({ onLogin }) {
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await login(form.username, form.password);
      onLogin(res.data);
      navigate("/");
      toast.success("Logged in successfully!");
    } catch (err) {
      const data = err.response?.data;
      const message = data?.error || data?.detail || data?.details || err.message || "Unable to reach authentication server";
      toast.error(data?.stage ? `${data.stage}: ${message}` : message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center p-4 overflow-hidden bg-gradient-to-br from-slate-900 via-primary-900 to-slate-950">
      {/* Ambient glow accents */}
      <div className="absolute -top-24 -left-24 w-96 h-96 bg-primary-500/20 rounded-full blur-3xl" />
      <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-cyan-500/20 rounded-full blur-3xl" />

      <div className="relative bg-slate-800/60 backdrop-blur-xl rounded-2xl shadow-2xl shadow-black/40 border border-slate-700/60 w-full max-w-md p-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-primary-500 to-cyan-500 rounded-2xl mb-4 shadow-lg shadow-primary-900/50">
            <ShieldCheck className="text-white" size={32} />
          </div>
          <h1 className="text-2xl font-bold text-white">Invoice AI System</h1>
          <p className="text-slate-400 text-sm mt-1">Sign in to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Username</label>
            <input
              type="text"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="w-full bg-slate-900/60 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
              placeholder="Enter username"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
            <div className="relative">
              <input
                type={showPass ? "text" : "password"}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full bg-slate-900/60 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent pr-10"
                placeholder="Enter password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPass(!showPass)}
                className="absolute right-3 top-2.5 text-slate-500 hover:text-slate-300"
              >
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-primary-600 to-cyan-600 hover:from-primary-500 hover:to-cyan-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg transition-all text-sm shadow-lg shadow-primary-900/40"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <div className="mt-5 flex items-center justify-between text-sm">
          <Link to="/forgot-password" className="text-cyan-400 hover:text-cyan-300">
            Forgot password?
          </Link>
          <Link to="/register" className="text-cyan-400 hover:text-cyan-300 font-medium">
            Create account
          </Link>
        </div>
      </div>
    </div>
  );
}