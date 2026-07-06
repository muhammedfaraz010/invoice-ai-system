import React, { useEffect, useState } from "react";
import { Bell, RefreshCw } from "lucide-react";
import toast from "react-hot-toast";
import { getNotifications } from "../services/api";

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getNotifications();
      setNotifications(res.data);
    } catch {
      toast.error("Failed to load notifications");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Notifications</h1>
          <p className="text-sm text-gray-500">Approval requests and workflow updates.</p>
        </div>
        <button onClick={load} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      <div className="space-y-3">
        {notifications.map((item) => (
          <div key={item.id} className="card flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
              <Bell size={16} />
            </div>
            <div className="flex-1">
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold text-gray-900">{item.title}</p>
                <span className="text-xs text-gray-400">{item.created_at}</span>
              </div>
              <p className="text-sm text-gray-600 mt-1">{item.message}</p>
              {item.reference_id && <p className="text-xs text-gray-400 mt-2">Reference: {item.reference_id}</p>}
            </div>
          </div>
        ))}
        {notifications.length === 0 && (
          <div className="card text-center py-12 text-gray-400">No notifications.</div>
        )}
      </div>
    </div>
  );
}
