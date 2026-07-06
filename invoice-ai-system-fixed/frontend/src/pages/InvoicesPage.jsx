import React, { useState, useEffect } from "react";
import { listInvoices, deleteInvoice, validateInvoice } from "../services/api";
import { formatCurrency } from "../utils/currency";
import { StatusBadge, optionalFields, requiredFields } from "../utils/invoiceStatus";
import {
  Search, Trash2, RefreshCw, ChevronLeft, ChevronRight, CheckCircle, AlertTriangle, Info,
} from "lucide-react";
import toast from "react-hot-toast";

const getTaxFields = (invoice) => {
  const currency = (invoice?.currency || "").toUpperCase();
  if (currency === "INR") {
    return [["Vendor GSTIN", invoice.vendor_gstin]];
  }
  if (currency === "AED") {
    return [["Vendor VAT/TRN", invoice.vendor_vat]];
  }
  return [];
};

const normalize = (value) => String(value || "").trim().toLowerCase();
const hasValue = (value) => {
  if (Array.isArray(value)) return value.length > 0;
  return value !== null && value !== undefined && String(value).trim() !== "";
};

const fieldAvailable = (invoice, label) => {
  const map = {
    "Invoice Number": invoice.invoice_number,
    Vendor: invoice.vendor_name,
    "Invoice Date": invoice.invoice_date,
    Amount: invoice.total_amount,
    Currency: invoice.currency,
    GSTIN: invoice.vendor_gstin || invoice.vendor_vat || invoice.buyer_gstin,
    Buyer: invoice.buyer_name,
    "Due Date": invoice.due_date,
    Tax: invoice.tax_amount,
    "Payment Terms": invoice.payment_method,
    "Line Items": invoice.line_items,
  };
  return hasValue(map[label]);
};

const summary = (invoice) => invoice.validation_summary || {};
const missingOptional = (invoice) => summary(invoice).missing_optional || invoice.missing_optional_fields || [];

const sameInvoiceGroup = (invoice, key) => {
  if (!invoice || !key) {
    return false;
  }
  const sameNumber = normalize(invoice.invoice_number) === normalize(key.invoice_number);
  const sameVendor = normalize(invoice.vendor_name || invoice.vendor) === normalize(key.vendor);
  const sameAmount = Number(invoice.total_amount ?? invoice.amount) === Number(key.amount);
  return sameNumber && sameVendor && sameAmount;
};

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [duplicateGroup, setDuplicateGroup] = useState([]);

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

  useEffect(() => {
    const stored = localStorage.getItem("selectedInvoiceKey");
    if (!stored || invoices.length === 0) {
      return;
    }

    try {
      const selectedKey = JSON.parse(stored);
      const matches = invoices.filter((inv) => sameInvoiceGroup(inv, selectedKey));

      if (matches.length > 0) {
        setSelected(matches[0]);
        setDuplicateGroup(matches);
      } else {
        setSelected(null);
        setDuplicateGroup([]);
      }
    } catch {
      // Ignore malformed saved selections.
    } finally {
      localStorage.removeItem("selectedInvoiceKey");
    }
  }, [invoices]);

  useEffect(() => {
    if (duplicateGroup.length > 0) {
      const first = duplicateGroup[0];
      document.getElementById(first.invoice_number)?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [duplicateGroup]);

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
      toast.success(`Validation: ${res.data.status || "updated"}`);
      load();
    } catch {
      toast.error("Validation failed");
    }
  };

  const totalPages = Math.ceil(total / 15);
  const fmt = (n, currency) => formatCurrency(n, currency);

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
            <option value="verified">Verified</option>
            <option value="complete">Complete</option>
            <option value="needs_review">Needs Review</option>
            <option value="failed">Failed</option>
            <option value="pending">Pending</option>
          </select>
        </div>

        {duplicateGroup.length > 1 && (
          <div className="text-yellow-600 font-medium mb-2">
            Warning: {duplicateGroup.length} duplicate invoices found
          </div>
        )}

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
                    id={inv.invoice_number || `invoice-${inv.id}`}
                    key={inv.id}
                    onClick={() => {
                      setSelected(inv);
                      setDuplicateGroup([]);
                    }}
                    className={`cursor-pointer hover:bg-blue-50 transition-colors ${
                      duplicateGroup.some((d) => d.id === inv.id) || selected?.id === inv.id
                        ? "bg-blue-100"
                        : ""
                    }`}
                  >
                    <td className="px-4 py-3 font-medium text-gray-800">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span>{inv.invoice_number || "--"}</span>
                        {inv.is_duplicate && (
                          <span className="badge-yellow">Duplicate</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-32 truncate">{inv.vendor_name || "--"}</td>
                    <td className="px-4 py-3 text-gray-500">{inv.invoice_date || "--"}</td>
                    <td className="px-4 py-3 font-medium">{fmt(inv.total_amount, inv.currency)}</td>
                    <td className="px-4 py-3"><StatusBadge status={inv.validation_status} /></td>
                    <td className="px-4 py-3"><StatusBadge status={inv.extraction_status} /></td>
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
              {duplicateGroup.length > 1 && (
                <div className="text-yellow-600 font-medium mb-2">
                  Warning: {duplicateGroup.length} duplicate invoices found
                </div>
              )}
              {[
                ["Invoice #", selected.invoice_number],
                ["Vendor", selected.vendor_name],
                ...getTaxFields(selected),
                ["Buyer", selected.buyer_name],
                ["Date", selected.invoice_date],
                ["Due Date", selected.due_date],
                ["Amount", fmt(selected.total_amount, selected.currency)],
                ["Tax", fmt(selected.tax_amount, selected.currency)],
                ["Payment Terms", selected.payment_method],
                ["Currency", selected.currency],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-gray-50 pb-2">
                  <span className="text-gray-500">{k}</span>
                  <span className="font-medium text-gray-800 text-right max-w-40 break-all">{v || "--"}</span>
                </div>
              ))}
              <div className="rounded-lg border border-gray-100 p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">Invoice Status</span>
                  <StatusBadge status={selected.validation_status} />
                </div>
                {selected.validation_status === "complete" && (
                  <div className="bg-blue-50 rounded-lg p-3 text-xs text-blue-700 space-y-1">
                    <div className="flex items-center gap-1.5 font-semibold">
                      <Info size={13} /> Information
                    </div>
                    <p>Invoice processed successfully.</p>
                    <p>Some optional information was not available in the source document.</p>
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-gray-100 p-3">
                <p className="text-xs font-semibold text-gray-700 mb-2">Extraction Summary</p>
                <div className="space-y-3">
                  <div>
                    <p className="text-xs font-medium text-gray-500 mb-1">Required Fields</p>
                    <div className="space-y-1">
                      {requiredFields.map((label) => (
                        <div key={label} className="flex items-center gap-2 text-xs">
                          <CheckCircle size={13} className={fieldAvailable(selected, label) ? "text-green-500" : "text-orange-500"} />
                          <span>{label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-gray-500 mb-1">Optional Information</p>
                    <div className="space-y-1">
                      {optionalFields.map((label) => (
                        <div key={label} className="flex items-center gap-2 text-xs">
                          <span className={fieldAvailable(selected, label) ? "text-green-600" : "text-gray-400"}>
                            {fieldAvailable(selected, label) ? "✔" : "○"}
                          </span>
                          <span>{label}</span>
                        </div>
                      ))}
                    </div>
                    <p className="text-[11px] text-gray-400 mt-2">Legend: ✔ Available · ○ Not Available</p>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-gray-100 p-3 space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-500">Required</span>
                  <span className="font-semibold">{selected.required_score ?? summary(selected).required_score ?? 0}%</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-500">Optional</span>
                  <span className="font-semibold">{selected.optional_score ?? summary(selected).optional_score ?? 0}%</span>
                </div>
                <div className="flex justify-between text-sm border-t border-gray-100 pt-2">
                  <span className="text-gray-600 font-medium">Extraction Quality</span>
                  <span className="font-bold text-gray-900">{selected.extraction_score ?? summary(selected).extraction_score ?? 0}%</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 font-medium">AI Confidence</span>
                  <span className="font-bold text-gray-900">{selected.ai_confidence ?? summary(selected).ai_confidence ?? 0}%</span>
                </div>
              </div>

              {missingOptional(selected).length > 0 && (
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs font-medium text-gray-700 mb-2">Missing Optional Information</p>
                  <div className="space-y-1">
                    {missingOptional(selected).map((item) => (
                      <p key={item} className="flex items-center gap-2 text-xs text-gray-600">
                        <Info size={13} className="text-gray-400" /> {item}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {selected.is_duplicate && (
                <div className="flex items-center gap-2 text-yellow-600 bg-yellow-50 p-2 rounded-lg text-xs">
                  <AlertTriangle size={13} /> Duplicate invoice
                </div>
              )}
              {selected.validation_errors?.length > 0 && (
                <div className={`rounded-lg p-3 ${
                  selected.validation_status === "failed"
                    ? "bg-red-50"
                    : selected.validation_status === "needs_review"
                      ? "bg-orange-50"
                      : "bg-gray-50"
                }`}>
                  <p className={`text-xs font-medium mb-1 ${
                    selected.validation_status === "failed"
                      ? "text-red-700"
                      : selected.validation_status === "needs_review"
                        ? "text-orange-700"
                        : "text-gray-700"
                  }`}>
                    {selected.validation_status === "failed" ? "Processing Failed:" : selected.validation_status === "needs_review" ? "Required Review:" : "Notes:"}
                  </p>
                  {selected.validation_errors.map((e, i) => (
                    <p key={i} className={`text-xs ${
                      selected.validation_status === "failed"
                        ? "text-red-600"
                        : selected.validation_status === "needs_review"
                          ? "text-orange-600"
                          : "text-gray-600"
                    }`}>- {e}</p>
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
