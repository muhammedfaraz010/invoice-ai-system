import React, { useState, useEffect } from "react";
import { listInvoices, deleteInvoice, validateInvoice } from "../services/api";
import {
  Search, Trash2, RefreshCw, ChevronLeft, ChevronRight, CheckCircle, AlertTriangle,
} from "lucide-react";
import toast from "react-hot-toast";

const statusBadge = (s) => {
  const map = {
    valid: "badge-green",
    invalid: "badge-red",
    pending: "badge-yellow",
    success: "badge-green",
    failed: "badge-red",
  };
  return <span className={map[s] || "badge-gray"}>{s}</span>;
};

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await listInvoices({
        page,
        size: 15,
        vendor: search || undefined,
        status: statusFilter || undefined,
      });
      setInvoices(res.data.invoices);
      setTotal(res.data.total);
    } catch {
      toast.error("Failed to load invoices");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [page, statusFilter]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    load();
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this invoice?")) {
      return;
    }
    try {
      await deleteInvoice(id);
      toast.success("Invoice deleted");
      if (selected?.id === id) {
        setSelected(null);
      }
      load();
    } catch {
      toast.error("Delete failed");
    }
  };

  const handleValidate = async (id) => {
    try {
      const res = await validateInvoice(id);
      toast.success(`Validation: ${res.data.is_valid ? "Valid" : "Invalid"}`);
      load();
    } catch {
      toast.error("Validation failed");
    }
  };

  const totalPages = Math.ceil(total / 15);
  const fmt = (n) => (n ? `Rs ${Number(n).toLocaleString("en-IN")}` : "--");

  return (
    <div className="p-6 flex gap-6 h-full">
      <div className={`flex-1 space-y-4 ${selected ? "min-w-0" : ""}`}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Invoices</h1>
            <p className="text-sm text-gray-500">{total} total invoices</p>
          </div>
          <button onClick={load} className="btn-secondary flex items-center gap-2">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        <div className="flex gap-3">
          <form onSubmit={handleSearch} className="flex gap-2 flex-1">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-2.5 text-gray-400" size={15} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search vendor..."
                className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button type="submit" className="btn-primary">Search</button>
          </form>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Status</option>
            <option value="valid">Valid</option>
            <option value="invalid">Invalid</option>
            <option value="pending">Pending</option>
          </select>
        </div>

        <div className="card p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {["Invoice #", "Vendor", "Date", "Amount", "Validation", "Extraction", ""].map((h) => (
                    <th key={h} className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-gray-400">
                      <RefreshCw className="animate-spin mx-auto mb-2" size={24} />
                      Loading...
                    </td>
                  </tr>
                ) : invoices.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-gray-400">
                      No invoices found. Upload some to get started.
                    </td>
                  </tr>
                ) : invoices.map((inv) => (
                  <tr
                    key={inv.id}
                    onClick={() => setSelected(inv)}
                    className={`cursor-pointer hover:bg-blue-50 transition-colors ${selected?.id === inv.id ? "bg-blue-50" : ""}`}
                  >
                    <td className="px-4 py-3 font-medium text-gray-800">{inv.invoice_number || "--"}</td>
                    <td className="px-4 py-3 text-gray-600 max-w-32 truncate">{inv.vendor_name || "--"}</td>
                    <td className="px-4 py-3 text-gray-500">{inv.invoice_date || "--"}</td>
                    <td className="px-4 py-3 font-medium">{fmt(inv.total_amount)}</td>
                    <td className="px-4 py-3">{statusBadge(inv.validation_status)}</td>
                    <td className="px-4 py-3">{statusBadge(inv.extraction_status)}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                        {inv.is_duplicate && (
                          <AlertTriangle className="text-yellow-500" size={15} title="Duplicate" />
                        )}
                        <button onClick={() => handleValidate(inv.id)} title="Re-validate" className="text-blue-500 hover:text-blue-700">
                          <CheckCircle size={15} />
                        </button>
                        <button onClick={() => handleDelete(inv.id)} title="Delete" className="text-red-400 hover:text-red-600">
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
              <p className="text-xs text-gray-500">Page {page} of {totalPages}</p>
              <div className="flex gap-2">
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary p-1.5 disabled:opacity-40">
                  <ChevronLeft size={14} />
                </button>
                <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn-secondary p-1.5 disabled:opacity-40">
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {selected && (
        <div className="w-80 shrink-0 space-y-4">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-800">Invoice Details</h2>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
            </div>
            <div className="space-y-3 text-sm">
              {[
                ["Invoice #", selected.invoice_number],
                ["Vendor", selected.vendor_name],
                ["Vendor GSTIN", selected.vendor_gstin],
                ["Buyer", selected.buyer_name],
                ["Date", selected.invoice_date],
                ["Due Date", selected.due_date],
                ["Amount", fmt(selected.total_amount)],
                ["Tax", fmt(selected.tax_amount)],
                ["Currency", selected.currency],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-gray-50 pb-2">
                  <span className="text-gray-500">{k}</span>
                  <span className="font-medium text-gray-800 text-right max-w-40 break-all">{v || "--"}</span>
                </div>
              ))}
              <div className="flex justify-between">
                <span className="text-gray-500">Validation</span>
                {statusBadge(selected.validation_status)}
              </div>
              {selected.is_duplicate && (
                <div className="flex items-center gap-2 text-yellow-600 bg-yellow-50 p-2 rounded-lg text-xs">
                  <AlertTriangle size={13} /> Duplicate invoice
                </div>
              )}
              {selected.validation_errors?.length > 0 && (
                <div className="bg-red-50 rounded-lg p-3">
                  <p className="text-xs font-medium text-red-700 mb-1">Issues:</p>
                  {selected.validation_errors.map((e, i) => (
                    <p key={i} className="text-xs text-red-600">- {e}</p>
                  ))}
                </div>
              )}
              {selected.processing_time_ms && (
                <p className="text-xs text-gray-400">Processed in {selected.processing_time_ms}ms</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
