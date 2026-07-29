import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw, ExternalLink, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { listUsers, requestUserDelete } from "../services/api";

const formatBytes = (value = 0) => {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
};

export default function ManageUsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await listUsers();
      setUsers(res.data);
    } catch {
      toast.error("Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleDeleteRequest = async (user) => {
    const reason = window.prompt(`Reason for deleting ${user.username}?`);
    if (reason === null) return;
    try {
      await requestUserDelete(user.id, reason);
      toast.success("Account deletion request sent");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Request failed");
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Manage Users</h1>
          <p className="text-sm text-gray-400">Select a user before loading their workspace.</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {["Name", "Email", "Role", "Status", "Invoices", "Storage", "Last Login", ""].map((head) => (
                <th key={head} className="text-left text-xs font-medium text-gray-500 uppercase px-4 py-3">{head}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {users.map((user) => (
              <tr key={user.id} className="hover:bg-blue-900/30">
                <td className="px-4 py-3 font-medium text-gray-100">{user.full_name || user.username}</td>
                <td className="px-4 py-3 text-gray-300">{user.email}</td>
                <td className="px-4 py-3 capitalize text-gray-200">{user.role}</td>
                <td className="px-4 py-3 text-gray-200">{user.status}</td>
                <td className="px-4 py-3 text-gray-200">{user.invoice_count || 0}</td>
                <td className="px-4 py-3 text-gray-200">{formatBytes(user.storage_bytes)}</td>
                <td className="px-4 py-3 text-gray-400">{user.last_login || "--"}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <Link to={`/users/${user.id}`} className="btn-secondary flex items-center gap-2">
                      <ExternalLink size={14} /> Open
                    </Link>
                    {user.role !== "admin" && (
                      <button onClick={() => handleDeleteRequest(user)} className="btn-secondary text-red-400 flex items-center gap-2">
                        <Trash2 size={14} /> Request
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!loading && users.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center py-12 text-gray-400">No users found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
