import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import toast from "react-hot-toast";
import { register } from "../services/api";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    username: "",
    email: "",
    full_name: "",
    password: "",
  });

  const getErrorMessage = (err) => {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      return detail[0]?.msg || "Registration failed";
    }
    return err.response?.data?.error || "Registration failed";
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.username.trim()) {
      toast.error("Username is required");
      return;
    }
    if (!form.email.trim()) {
      toast.error("Email is required");
      return;
    }
    if (form.password.length < 8) {
      toast.error("Password too short");
      return;
    }
    setLoading(true);
    try {
      const payload = {
        username: form.username.trim(),
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        password: form.password,
      };
      const res = await register(payload);
      toast.success(res.data?.message || "Registration successful");
      navigate("/login");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden">
      <div className="pointer-events-none fixed -top-32 left-1/3 w-[32rem] h-[32rem] bg-primary-600/10 rounded-full blur-3xl" />
      <div className="pointer-events-none fixed bottom-0 right-0 w-[28rem] h-[28rem] bg-cyan-600/10 rounded-full blur-3xl" />

      <div className="card p-8 w-full max-w-md relative z-10">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-500/10 rounded-2xl mb-4">
            <ShieldCheck className="text-primary-400" size={32} />
          </div>
          <h1 className="text-2xl font-bold text-white">Create Account</h1>
          <p className="text-blue-300 text-sm mt-1">Start processing your invoices securely</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {[
            ["full_name", "Full Name", "text"],
            ["username", "Username", "text"],
            ["email", "Email", "email"],
            ["password", "Password", "password"],
          ].map(([name, label, type]) => (
            <div key={name}>
              <label className="block text-sm font-medium text-blue-200 mb-1">{label}</label>
              <input
                type={type}
                value={form[name]}
                onChange={(e) => setForm({ ...form, [name]: e.target.value })}
                className="w-full border border-blue-800/50 bg-blue-950/30 text-white placeholder-blue-400 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
                minLength={name === "password" ? 8 : undefined}
              />
            </div>
          ))}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-900/40 text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
          >
            {loading ? "Creating..." : "Register"}
          </button>
        </form>

        <p className="mt-5 text-sm text-center text-blue-300">
          Already have an account?{" "}
          <Link to="/login" className="text-primary-400 hover:text-primary-300 font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
