import React, { useEffect, useState } from "react";
import { CheckCircle, RefreshCw, XCircle } from "lucide-react";
import toast from "react-hot-toast";
import {
  approveDelete,
  approveUserDelete,
  listDeleteRequests,
  listDeleteUserRequests,
  rejectUserDelete,
  rejectDelete,
} from "../services/api";

export default function DeleteRequestsPage() {
  const [requests, setRequests] = useState([]);
  const [userRequests, setUserRequests] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [invoiceRes, userRes] = await Promise.all([
        listDeleteRequests(),
        listDeleteUserRequests(),
      ]);
      setRequests(invoiceRes.data);
      setUserRequests(userRes.data);
    } catch {
      toast.error("Failed to load delete requests");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const decide = async (requestId, approved) => {
    try {
      if (approved) {
        await approveDelete(requestId);
      } else {
        await rejectDelete(requestId);
      }
      toast.success(approved ? "Deletion approved" : "Deletion rejected");
      load();
    } catch {
      toast.error("Decision failed");
    }
  };

  const decideUser = async (requestId, approved) => {
    try {
      if (approved) {
        await approveUserDelete(requestId);
      } else {
        await rejectUserDelete(requestId);
      }
      toast.success(approved ? "Account deletion approved" : "Account deletion rejected");
      load();
    } catch {
      toast.error("Decision failed");
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Delete Requests</h1>
          <p className="text-sm text-gray-500">Approve or reject pending invoice deletion requests.</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      <div className="card p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 font-semibold">Invoice Deletion Requests</div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {["Invoice", "Requested By", "Status", "Reason", "Created", ""].map((head) => (
                <th key={head} className="text-left text-xs font-medium text-gray-500 uppercase px-4 py-3">{head}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {requests.map((item) => (
              <tr key={item.id}>
                <td className="px-4 py-3 font-mono text-xs">{item.invoice_id}</td>
                <td className="px-4 py-3 font-mono text-xs">{item.requested_by}</td>
                <td className="px-4 py-3">{item.status}</td>
                <td className="px-4 py-3">{item.reason || "--"}</td>
                <td className="px-4 py-3 text-gray-500">{item.created_at}</td>
                <td className="px-4 py-3">
                  {item.status === "Pending" && (
                    <div className="flex justify-end gap-2">
                      <button onClick={() => decide(item.id, true)} className="text-green-600 hover:text-green-700" title="Approve">
                        <CheckCircle size={18} />
                      </button>
                      <button onClick={() => decide(item.id, false)} className="text-red-600 hover:text-red-700" title="Reject">
                        <XCircle size={18} />
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {requests.length === 0 && (
              <tr><td colSpan={6} className="text-center py-12 text-gray-400">No delete requests.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 font-semibold">Account Deletion Requests</div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {["Target User", "Requested By", "Status", "Reason", "Created", ""].map((head) => (
                <th key={head} className="text-left text-xs font-medium text-gray-500 uppercase px-4 py-3">{head}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {userRequests.map((item) => (
              <tr key={item.id}>
                <td className="px-4 py-3 font-mono text-xs">{item.target_user}</td>
                <td className="px-4 py-3 font-mono text-xs">{item.requested_by}</td>
                <td className="px-4 py-3">{item.status}</td>
                <td className="px-4 py-3">{item.reason || "--"}</td>
                <td className="px-4 py-3 text-gray-500">{item.created_at}</td>
                <td className="px-4 py-3">
                  {item.status === "Pending" && (
                    <div className="flex justify-end gap-2">
                      <button onClick={() => decideUser(item.id, true)} className="text-green-600 hover:text-green-700" title="Approve">
                        <CheckCircle size={18} />
                      </button>
                      <button onClick={() => decideUser(item.id, false)} className="text-red-600 hover:text-red-700" title="Reject">
                        <XCircle size={18} />
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {userRequests.length === 0 && (
              <tr><td colSpan={6} className="text-center py-12 text-gray-400">No account delete requests.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
