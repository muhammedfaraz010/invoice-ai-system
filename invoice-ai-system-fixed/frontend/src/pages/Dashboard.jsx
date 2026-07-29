import React, { useEffect, useState } from "react";
import {
  FileText, CheckCircle, XCircle, AlertTriangle, TrendingUp, RefreshCw, Info, Gauge,
  Users, Trash2,
} from "lucide-react";
import { getAnalytics, getAdminOverview, listInvoices } from "../services/api";
import { formatCurrency } from "../utils/currency";

const StatCard = ({ label, value, icon, color, sub }) => (
  <div className="card flex items-center gap-4">
    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
      {icon}
    </div>
    <div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-sm text-blue-300">{label}</p>
      {sub && <p className="text-xs text-blue-400/70 mt-0.5">{sub}</p>}
    </div>
  </div>
);

function AdminOverview() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAdminOverview();
      setData(res.data);
    } catch {
      setData({
        active_users: 0,
        total_invoices: 0,
        pending_review: 0,
        pending_delete_requests: 0,
        recent_activity: [],
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <RefreshCw className="animate-spin text-cyan-400" size={32} />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">System Overview</h1>
          <p className="text-sm text-blue-300 mt-0.5">Architected admin dashboard layout with streamlined navigation components</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Active Users" value={data.active_users} icon={<Users className="text-primary-400" size={20} />} color="bg-primary-500/10" />
        <StatCard label="Invoices, All Users" value={data.total_invoices} icon={<FileText className="text-cyan-400" size={20} />} color="bg-cyan-500/10" />
        <StatCard label="Pending Review" value={data.pending_review} icon={<AlertTriangle className="text-warning-400" size={20} />} color="bg-warning-600/10" />
        <StatCard label="Delete Requests" value={data.pending_delete_requests} icon={<Trash2 className="text-danger-400" size={20} />} color="bg-danger-600/10" />
      </div>

      <div className="card">
        <h2 className="text-base font-semibold text-white mb-4">Recent User Activity</h2>
        {data.recent_activity.length > 0 ? (
          <div className="divide-y divide-blue-900/40">
            {data.recent_activity.map((activity, i) => (
              <div key={i} className="flex items-center justify-between py-3">
                <span className="font-medium text-blue-100">{activity.username}</span>
                <span className="text-sm text-blue-300">
                  {activity.invoice_count} invoice{activity.invoice_count !== 1 ? "s" : ""}
                  {activity.last_login ? `, last login ${new Date(activity.last_login).toLocaleDateString()}` : ""}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-blue-400/60">No recent activity yet.</p>
        )}
      </div>
    </div>
  );
}

const CURRENCY_LABELS = {
  INR: "INR (₹)",
  USD: "USD ($)",
  AED: "AED (د.إ)",
};

function CurrencyBreakdown({ invoices }) {
  const counts = invoices.reduce((acc, inv) => {
    const code = (inv.currency || "INR").toUpperCase();
    acc[code] = (acc[code] || 0) + 1;
    return acc;
  }, {});

  const currencies = Object.keys(counts);
  if (currencies.length === 0) {
    return null;
  }

  return (
    <div className="card">
      <h2 className="text-base font-semibold text-white mb-3">Invoices by Currency</h2>
      <div className="flex flex-wrap gap-3">
        {currencies.sort().map((code) => (
          <div
            key={code}
            className="flex items-center gap-2 bg-blue-900/30 border border-blue-800/40 rounded-lg px-4 py-2"
          >
            <span className="text-sm font-medium text-blue-100">{CURRENCY_LABELS[code] || code}</span>
            <span className="text-sm font-bold text-white">{counts[code]}</span>
            <span className="text-xs text-blue-400">invoice{counts[code] !== 1 ? "s" : ""}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function UserDashboard({ user }) {
  const [data, setData] = useState(null);
  const [recentInvoices, setRecentInvoices] = useState([]);
  const [allInvoices, setAllInvoices] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [analyticsRes, recentRes, allRes] = await Promise.all([
        getAnalytics(),
        listInvoices({ page: 1, size: 5 }),
        listInvoices({ page: 1, size: 100 }),
      ]);
      setData(analyticsRes.data);
      setRecentInvoices(recentRes.data.invoices || []);
      setAllInvoices(allRes.data.invoices || []);
    } catch {
      setData({
        total_invoices: 0,
        verified_invoices: 0,
        complete_invoices: 0,
        needs_review_invoices: 0,
        currency: "INR",
      });
      setRecentInvoices([]);
      setAllInvoices([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <RefreshCw className="animate-spin text-cyan-400" size={32} />
      </div>
    );
  }

  const fmt = (n, currency = "INR") => formatCurrency(n, currency);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-blue-300 mt-0.5">Invoice processing overview</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="My Invoices" value={data.total_invoices} icon={<FileText className="text-primary-400" size={20} />} color="bg-primary-500/10" />
        <StatCard label="Verified" value={data.verified_invoices} icon={<CheckCircle className="text-success-400" size={20} />} color="bg-success-600/10" />
        <StatCard label="Needs Review" value={data.needs_review_invoices} icon={<AlertTriangle className="text-warning-400" size={20} />} color="bg-warning-600/10" />
        <StatCard label="Complete" value={data.complete_invoices} icon={<Info className="text-cyan-400" size={20} />} color="bg-cyan-500/10" />
      </div>

      <CurrencyBreakdown invoices={allInvoices} />

      <div className="card">
        <h2 className="text-base font-semibold text-white mb-4">Recent Invoices</h2>
        {recentInvoices.length > 0 ? (
          <div className="divide-y divide-blue-900/40">
            {recentInvoices.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between py-3">
                <span className="font-medium text-blue-100">
                  Invoice #{inv.invoice_number || inv.id?.slice(0, 8)}
                </span>
                <span className="text-sm text-blue-300">
                  {fmt(inv.total_amount, inv.currency || "INR")}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-blue-400/60">No invoices yet. Upload one to get started.</p>
        )}
      </div>
    </div>
  );
}

export default function Dashboard({ user }) {
  if (user?.role === "admin") {
    return <AdminOverview />;
  }
  return <UserDashboard user={user} />;
}
