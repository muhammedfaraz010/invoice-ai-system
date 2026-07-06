import React, { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  FileText, CheckCircle, XCircle, AlertTriangle, TrendingUp, RefreshCw, Info, Gauge,
} from "lucide-react";
import { getAnalytics } from "../services/api";
import { formatCurrency } from "../utils/currency";

const COLORS = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"];

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
      setData({
        total_invoices: 0,
        total_amount: 0,
        verified_invoices: 0,
        complete_invoices: 0,
        needs_review_invoices: 0,
        failed_invoices: 0,
        average_extraction_score: 0,
        average_ai_confidence: 0,
        duplicate_invoices: 0,
        pending_invoices: 0,
        top_vendors: [],
        monthly_spend: [],
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
        <RefreshCw className="animate-spin text-blue-500" size={32} />
      </div>
    );
  }

  const fmt = (n, currency = "INR", compact = false) => formatCurrency(n, currency, compact);

  const pieData = [
    { name: "Verified", value: data.verified_invoices },
    { name: "Complete", value: data.complete_invoices },
    { name: "Needs Review", value: data.needs_review_invoices },
    { name: "Failed", value: data.failed_invoices },
  ].filter((d) => d.value > 0);

  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const currencyTotals = data.currency_totals || [];
  const hasMixedCurrencies = currencyTotals.length > 1 || data.currency === "MIXED";
  const spendValue = hasMixedCurrencies
    ? `${currencyTotals.length} currencies`
    : fmt(data.total_amount, data.currency || "INR", true);
  const spendSub = hasMixedCurrencies
    ? currencyTotals.map((c) => fmt(c.total, c.currency)).join(" | ")
    : null;
  const activeCurrencies = currencyTotals.map((c) => c.currency);
  const monthlyChartData = Object.values((data.monthly_spend || []).reduce((acc, item) => {
    const key = `${item.year}-${item.month}`;
    if (!acc[key]) {
      acc[key] = { name: monthNames[item.month - 1] };
    }
    acc[key][item.currency || data.currency || "INR"] = item.total;
    return acc;
  }, {}));
  const vendorsByCurrency = (data.top_vendors || []).reduce((acc, vendor) => {
    const code = vendor.currency || data.currency || "INR";
    acc[code] = acc[code] || [];
    acc[code].push(vendor);
    return acc;
  }, {});

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Invoice processing overview</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <StatCard label="Total Invoices" value={data.total_invoices} icon={<FileText className="text-blue-600" size={20} />} color="bg-blue-50" />
        <StatCard label="Total Spend" value={spendValue} sub={spendSub} icon={<TrendingUp className="text-green-600" size={20} />} color="bg-green-50" />
        <StatCard label="Verified" value={data.verified_invoices} icon={<CheckCircle className="text-emerald-600" size={20} />} color="bg-emerald-50" />
        <StatCard label="Complete" value={data.complete_invoices} icon={<Info className="text-blue-600" size={20} />} color="bg-blue-50" />
        <StatCard label="Needs Review" value={data.needs_review_invoices} icon={<AlertTriangle className="text-orange-600" size={20} />} color="bg-orange-50" />
        <StatCard label="Failed" value={data.failed_invoices} icon={<XCircle className="text-red-600" size={20} />} color="bg-red-50" />
        <StatCard label="Average Extraction Score" value={`${data.average_extraction_score || 0}%`} icon={<Gauge className="text-violet-600" size={20} />} color="bg-violet-50" />
        <StatCard label="Average AI Confidence" value={`${data.average_ai_confidence || 0}%`} icon={<CheckCircle className="text-teal-600" size={20} />} color="bg-teal-50" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Monthly Spend</h2>
          {data.monthly_spend.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={monthlyChartData}
              >
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => (hasMixedCurrencies ? Number(v).toLocaleString() : fmt(v, data.currency || "INR", true))} />
                <Tooltip formatter={(v, name) => [fmt(v, name), "Spend"]} />
                {activeCurrencies.length > 0 ? activeCurrencies.map((currency, index) => (
                  <Bar key={currency} dataKey={currency} fill={COLORS[index % COLORS.length]} radius={[4, 4, 0, 0]} />
                )) : (
                  <Bar dataKey={data.currency || "INR"} fill="#3b82f6" radius={[4, 4, 0, 0]} />
                )}
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-52 flex items-center justify-center text-gray-400 text-sm">
              No spend data yet. Upload invoices to see analytics.
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Invoice Status</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value" paddingAngle={3}>
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

      <div className="card">
        <h2 className="text-base font-semibold text-gray-800 mb-4">Top Vendors by Spend</h2>
        {data.top_vendors.length > 0 ? (
          <div className="space-y-5">
            {Object.entries(vendorsByCurrency).map(([currency, vendors]) => {
              const max = vendors[0]?.total || 1;
              return (
                <div key={currency} className="space-y-3">
                  {hasMixedCurrencies && (
                    <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      {currency}
                    </div>
                  )}
                  {vendors.map((v, i) => {
                    const pct = Math.round((v.total / max) * 100);
                    return (
                      <div key={`${currency}-${v.vendor}-${i}`}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-gray-700 font-medium">{v.vendor || "Unknown"}</span>
                          <span className="text-gray-500">{fmt(v.total, currency)}</span>
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full">
                          <div className="h-2 rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
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
