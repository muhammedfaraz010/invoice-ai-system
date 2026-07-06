import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { MessageSquare, RefreshCw, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import {
  getUserActivityLog,
  getUserChatHistory,
  getUserInvoices,
  getUserProfile,
  getUserStorage,
  requestInvoiceDelete,
} from "../services/api";
import { formatCurrency } from "../utils/currency";

const formatBytes = (value = 0) => {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
};

export default function UserWorkspacePage() {
  const { id } = useParams();
  const [profile, setProfile] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [chat, setChat] = useState([]);
  const [logs, setLogs] = useState([]);
  const [storage, setStorage] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [profileRes, invoiceRes, chatRes, logRes, storageRes] = await Promise.all([
        getUserProfile(id),
        getUserInvoices(id),
        getUserChatHistory(id),
        getUserActivityLog(id),
        getUserStorage(id),
      ]);
      setProfile(profileRes.data);
      setInvoices(invoiceRes.data.invoices);
      setChat(chatRes.data);
      setLogs(logRes.data);
      setStorage(storageRes.data);
    } catch {
      toast.error("Failed to load user workspace");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  const handleDeleteRequest = async (invoice) => {
    const reason = window.prompt(`Reason for deleting ${invoice.filename || invoice.invoice_number || "invoice"}?`);
    if (reason === null) return;
    try {
      await requestInvoiceDelete(invoice.id, reason);
      toast.success("Deletion request sent");
    } catch {
      toast.error("Request failed");
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{profile?.full_name || profile?.username || "User Workspace"}</h1>
          <p className="text-sm text-gray-500">{profile?.email || "Selected user workspace"}</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card"><p className="text-sm text-gray-500">Role</p><p className="text-xl font-semibold capitalize">{profile?.role || "--"}</p></div>
        <div className="card"><p className="text-sm text-gray-500">Status</p><p className="text-xl font-semibold">{profile?.status || "--"}</p></div>
        <div className="card"><p className="text-sm text-gray-500">Invoices</p><p className="text-xl font-semibold">{storage?.invoice_count || 0}</p></div>
        <div className="card"><p className="text-sm text-gray-500">Storage</p><p className="text-xl font-semibold">{formatBytes(storage?.storage_bytes)}</p></div>
      </div>

      <div className="card p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 font-semibold">User Invoices</div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {["Invoice", "Vendor", "Date", "Amount", "Status", ""].map((head) => (
                <th key={head} className="text-left text-xs font-medium text-gray-500 uppercase px-4 py-3">{head}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {invoices.map((invoice) => (
              <tr key={invoice.id}>
                <td className="px-4 py-3 font-medium">{invoice.invoice_number || invoice.filename || "--"}</td>
                <td className="px-4 py-3">{invoice.vendor_name || "--"}</td>
                <td className="px-4 py-3">{invoice.invoice_date || "--"}</td>
                <td className="px-4 py-3">{formatCurrency(invoice.total_amount, invoice.currency)}</td>
                <td className="px-4 py-3">{invoice.validation_status || "--"}</td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => handleDeleteRequest(invoice)} className="text-red-600 hover:text-red-700" title="Request deletion">
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {invoices.length === 0 && (
              <tr><td colSpan={6} className="text-center py-10 text-gray-400">No invoices for this user.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-3 flex items-center gap-2"><MessageSquare size={16} /> AI Chat</h2>
          <div className="space-y-3 max-h-80 overflow-auto">
            {chat.map((item) => (
              <div key={item.id} className="border-b border-gray-100 pb-3">
                <p className="text-sm font-medium text-gray-800">{item.question}</p>
                <p className="text-sm text-gray-500 mt-1 line-clamp-3">{item.answer}</p>
              </div>
            ))}
            {chat.length === 0 && <p className="text-sm text-gray-400">No chat history.</p>}
          </div>
        </div>

        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-3">Activity Log</h2>
          <div className="space-y-2 max-h-80 overflow-auto">
            {logs.map((log) => (
              <div key={log.id} className="flex justify-between gap-3 text-sm border-b border-gray-50 pb-2">
                <span className="text-gray-700">{log.action}</span>
                <span className="text-gray-400">{log.created_at}</span>
              </div>
            ))}
            {logs.length === 0 && <p className="text-sm text-gray-400">No activity yet.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
