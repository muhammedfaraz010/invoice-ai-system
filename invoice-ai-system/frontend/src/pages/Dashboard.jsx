import React, { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend
} from "recharts";
import {
  FileText, CheckCircle, XCircle, AlertTriangle, TrendingUp, RefreshCw
} from "lucide-react";
import { getAnalytics } from "../services/api";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

const StatCard = ({ label, value, icon, color, sub }) => (
  <div className="card flex items-center gap-4">
    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
      {icon}
    </div>
    <div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-sm text-gray-500">{label}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  </div>
);

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAnalytics();
      setData(res.data);
    } catch {
      // demo fallback
      setData({
        total_invoices: 0, total_amount: 0, valid_invoices: 0,
        invalid_invoices: 0, duplicate_invoices: 0, pending_invoices: 0,
        top_vendors: [], monthly_spend: []
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <RefreshCw className="animate-spin text-blue-500" size={32} />
    </div>
  );

  const fmt = (n) => n >= 100000
    ? `₹${(n / 100000).toFixed(1)}L`
    : `₹${Number(n).toLocaleString("en-IN")}`;

  const pieData = [
    { name: "Valid", value: data.valid_invoices },
    { name: "Invalid", value: data.invalid_invoices },
    { name: "Duplicate", value: data.duplicate_invoices },
    { name: "Pending", value: data.pending_invoices },
  ].filter(d => d.value > 0);

  const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Invoice processing overview</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        <StatCard
          label="Total Invoices"
          value={data.total_invoices}
          icon={<FileText className="text-blue-600" size={20} />}
          color="bg-blue-50"
        />
        <StatCard
          label="Total Spend"
          value={fmt(data.total_amount)}
          icon={<TrendingUp className="text-green-600" size={20} />}
          color="bg-green-50"
        />
        <StatCard
          label="Valid"
          value={data.valid_invoices}
          icon={<CheckCircle className="text-emerald-600" size={20} />}
          color="bg-emerald-50"
        />
        <StatCard
          label="Invalid"
          value={data.invalid_invoices}
          icon={<XCircle className="text-red-600" size={20} />}
          color="bg-red-50"
        />
        <StatCard
          label="Duplicates"
          value={data.duplicate_invoices}
          icon={<AlertTriangle className="text-yellow-600" size={20} />}
          color="bg-yellow-50"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly Spend Bar */}
        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Monthly Spend</h2>
          {data.monthly_spend.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.monthly_spend.map(d => ({
                name: monthNames[d.month - 1],
                total: d.total
              }))}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
                <Tooltip formatter={v => [`₹${Number(v).toLocaleString("en-IN")}`, "Spend"]} />
                <Bar dataKey="total" fill="#3b82f6" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-52 flex items-center justify-center text-gray-400 text-sm">
              No spend data yet. Upload invoices to see analytics.
            </div>
          )}
        </div>

        {/* Status Pie */}
        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Invoice Status</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90}
                  dataKey="value" paddingAngle={3}>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-52 flex items-center justify-center text-gray-400 text-sm">
              No data to display yet.
            </div>
          )}
        </div>
      </div>

      {/* Top Vendors */}
      <div className="card">
        <h2 className="text-base font-semibold text-gray-800 mb-4">Top Vendors by Spend</h2>
        {data.top_vendors.length > 0 ? (
          <div className="space-y-3">
            {data.top_vendors.map((v, i) => {
              const max = data.top_vendors[0]?.total || 1;
              const pct = Math.round((v.total / max) * 100);
              return (
                <div key={i}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 font-medium">{v.vendor || "Unknown"}</span>
                    <span className="text-gray-500">{fmt(v.total)}</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full">
                    <div className="h-2 rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-gray-400">No vendor data yet.</p>
        )}
      </div>
    </div>
  );
}
