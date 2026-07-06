import React, { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import toast from "react-hot-toast";
import { getAuditLog } from "../services/api";

export default function AuditLogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAuditLog();
      setLogs(res.data);
    } catch {
      toast.error("Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
          <p className="text-sm text-gray-500">Security and workflow activity across the system.</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {["Action", "Actor", "Target User", "Invoice", "IP", "When"].map((head) => (
                <th key={head} className="text-left text-xs font-medium text-gray-500 uppercase px-4 py-3">{head}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {logs.map((log) => (
              <tr key={log.id}>
                <td className="px-4 py-3 font-medium">{log.action}</td>
                <td className="px-4 py-3 font-mono text-xs">{log.actor_id || "--"}</td>
                <td className="px-4 py-3 font-mono text-xs">{log.target_user_id || "--"}</td>
                <td className="px-4 py-3 font-mono text-xs">{log.invoice_id || "--"}</td>
                <td className="px-4 py-3">{log.ip_address || "--"}</td>
                <td className="px-4 py-3 text-gray-500">{log.created_at}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr><td colSpan={6} className="text-center py-12 text-gray-400">No audit logs.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
