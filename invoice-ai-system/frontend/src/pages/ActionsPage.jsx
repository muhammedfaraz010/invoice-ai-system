import React, { useState, useEffect } from "react";
import { getAgentActions, resolveAction } from "../services/api";
import {
  Bell, AlertTriangle, CheckCircle, Copy, TrendingUp,
  RefreshCw, Filter
} from "lucide-react";
import toast from "react-hot-toast";

const ACTION_META = {
  duplicate_alert: {
    icon: <Copy size={16} />,
    color: "bg-orange-50 border-orange-200",
    iconColor: "text-orange-500",
    label: "Duplicate Invoice",
    badge: "badge-yellow",
  },
  missing_gst: {
    icon: <AlertTriangle size={16} />,
    color: "bg-red-50 border-red-200",
    iconColor: "text-red-500",
    label: "Missing GST",
    badge: "badge-red",
  },
  high_value_approval: {
    icon: <TrendingUp size={16} />,
    color: "bg-blue-50 border-blue-200",
    iconColor: "text-blue-500",
    label: "High Value",
    badge: "badge-blue",
  },
  validation_failure: {
    icon: <AlertTriangle size={16} />,
    color: "bg-yellow-50 border-yellow-200",
    iconColor: "text-yellow-500",
    label: "Validation Failure",
    badge: "badge-yellow",
  },
};

export default function ActionsPage() {
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAgentActions(filter ? { status: filter } : {});
      setActions(res.data);
    } catch { toast.error("Failed to load actions"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [filter]);

  const handleResolve = async (id) => {
    try {
      await resolveAction(id);
      toast.success("Action resolved");
      load();
    } catch { toast.error("Failed to resolve"); }
  };

  const counts = {
    all: actions.length,
    triggered: actions.filter(a => a.action_status === "triggered").length,
    resolved: actions.filter(a => a.action_status === "resolved").length,
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Agent Actions</h1>
          <p className="text-sm text-gray-500">Automated alerts and workflow triggers</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Actions", value: counts.all, color: "text-gray-700", bg: "bg-gray-50" },
          { label: "Pending", value: counts.triggered, color: "text-orange-600", bg: "bg-orange-50" },
          { label: "Resolved", value: counts.resolved, color: "text-green-600", bg: "bg-green-50" },
        ].map(c => (
          <div key={c.label} className={`card ${c.bg} border-0`}>
            <p className={`text-2xl font-bold ${c.color}`}>{c.value}</p>
            <p className="text-sm text-gray-500">{c.label}</p>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div className="flex gap-2">
        {["", "triggered", "resolved"].map(s => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === s
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {s === "" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Action Cards */}
      {loading ? (
        <div className="text-center py-12">
          <RefreshCw className="animate-spin mx-auto text-gray-400 mb-2" size={24} />
          <p className="text-gray-400 text-sm">Loading actions...</p>
        </div>
      ) : actions.length === 0 ? (
        <div className="card text-center py-12">
          <Bell className="mx-auto text-gray-300 mb-3" size={40} />
          <p className="text-gray-500 font-medium">No agent actions yet</p>
          <p className="text-gray-400 text-sm mt-1">
            Actions are triggered automatically when invoices are processed
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {actions.map(action => {
            const meta = ACTION_META[action.action_type] || {
              icon: <Bell size={16} />,
              color: "bg-gray-50 border-gray-200",
              iconColor: "text-gray-500",
              label: action.action_type,
              badge: "badge-gray",
            };
            const isPending = action.action_status === "triggered";

            return (
              <div key={action.id} className={`card border p-4 ${meta.color} ${isPending ? "" : "opacity-70"}`}>
                <div className="flex items-start gap-3">
                  <div className={`w-9 h-9 rounded-lg bg-white flex items-center justify-center shrink-0 shadow-sm ${meta.iconColor}`}>
                    {meta.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={meta.badge}>{meta.label}</span>
                      <span className={isPending ? "badge-yellow" : "badge-green"}>
                        {isPending ? "Pending" : "Resolved"}
                      </span>
                      <span className="text-xs text-gray-400 ml-auto">
                        {new Date(action.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 mt-1.5">{action.message}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      Invoice: <code className="bg-white px-1 rounded">{action.invoice_id?.slice(0,12)}…</code>
                    </p>
                  </div>

                  {isPending && (
                    <button
                      onClick={() => handleResolve(action.id)}
                      className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-green-700 bg-green-100 hover:bg-green-200 rounded-lg transition-colors"
                    >
                      <CheckCircle size={13} /> Resolve
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
