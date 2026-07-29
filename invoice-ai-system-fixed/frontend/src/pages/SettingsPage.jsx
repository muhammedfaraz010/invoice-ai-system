import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { listUsers, updateUser, updateUserStatus } from "../services/api";

export default function SettingsPage({ user }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);

  const getErrorMessage = (err, fallback) => {
    const data = err.response?.data;
    return data?.detail || data?.error || data?.details || fallback;
  };

  const loadUsers = async () => {
    if (user?.role !== "admin") return;
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
    loadUsers();
  }, [user?.role]);

  const handleRole = async (target, role) => {
    try {
      await updateUser(target.id, { role });
      toast.success("User updated");
      loadUsers();
    } catch (err) {
      toast.error(getErrorMessage(err, "Update failed"));
    }
  };

  const handleDeactivate = async (target) => {
    if (!window.confirm(`Deactivate ${target.username}?`)) return;
    try {
      await updateUserStatus(target.id, "Inactive");
      toast.success("User deactivated successfully.");
      loadUsers();
    } catch (err) {
      toast.error(getErrorMessage(err, "Deactivate failed"));
    }
  };

  const handleActivate = async (target) => {
    try {
      await updateUserStatus(target.id, "Active");
      toast.success("User activated successfully.");
      loadUsers();
    } catch (err) {
      toast.error(getErrorMessage(err, "Activate failed"));
    }
  };

  const getUserStatus = (target) => target.status || (target.is_active ? "Active" : "Inactive");
  const activeAdminCount = users.filter((u) => u.role === "admin" && getUserStatus(u) === "Active").length;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-sm text-blue-300">Account, access, and application preferences</p>
      </div>

      <div className="card">
        <h2 className="text-base font-semibold text-blue-100 mb-2">Security</h2>
        <p className="text-sm text-blue-300">JWT access tokens expire automatically. Sign out from shared devices when finished.</p>
      </div>

      {user?.role === "admin" && (
        <div className="card p-0 overflow-hidden">
          <div className="px-6 py-4 border-b border-blue-900/40 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-blue-100">Users</h2>
              <p className="text-sm text-blue-300">Manage account access and roles</p>
            </div>
            <button onClick={loadUsers} className="btn-secondary">
              {loading ? "Loading..." : "Refresh"}
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {["Name", "Username", "Email", "Role", "Status", ""].map((h) => (
                    <th key={h} className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {users.map((u) => {
                  const userStatus = getUserStatus(u);
                  const isActive = userStatus === "Active";
                  const isSelf = u.id === user.id;
                  const isLastActiveAdmin = u.role === "admin" && isActive && activeAdminCount <= 1;
                  const disableDeactivate = isSelf || isLastActiveAdmin;
                  return (
                    <tr key={u.id}>
                      <td className="px-4 py-3 font-medium text-gray-100">{u.full_name}</td>
                      <td className="px-4 py-3 text-gray-300">{u.username}</td>
                      <td className="px-4 py-3 text-gray-300">{u.email}</td>
                      <td className="px-4 py-3">
                        <select
                          value={u.role}
                          onChange={(e) => handleRole(u, e.target.value)}
                          disabled={isSelf}
                          className="border border-blue-800/50 bg-blue-950/30 text-white rounded-lg px-2 py-1 text-sm capitalize disabled:bg-blue-950/10 disabled:text-blue-400"
                        >
                          <option value="user">User</option>
                          <option value="admin">Admin</option>
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        {isActive ? <span className="badge-green">Active</span> : <span className="badge-gray">Inactive</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {isActive ? (
                          <button
                            onClick={() => handleDeactivate(u)}
                            disabled={disableDeactivate}
                            title={isSelf ? "You cannot deactivate your own account" : isLastActiveAdmin ? "Cannot deactivate the last active admin" : ""}
                            className="rounded-md px-3 py-1.5 text-sm font-medium text-red-400 hover:bg-red-900/30 hover:text-red-300 disabled:text-gray-600 disabled:hover:bg-transparent"
                          >
                            Deactivate
                          </button>
                        ) : (
                          <button
                            onClick={() => handleActivate(u)}
                            className="rounded-md px-3 py-1.5 text-sm font-medium text-green-400 hover:bg-green-900/30 hover:text-green-300"
                          >
                            Activate
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
