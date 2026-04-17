import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import {
  Upload, FileText, CheckCircle, XCircle, Loader, AlertCircle,
} from "lucide-react";
import { uploadInvoice, getInvoice } from "../services/api";
import toast from "react-hot-toast";

const STATUS_ICONS = {
  uploading: <Loader className="animate-spin text-blue-500" size={16} />,
  processing: <Loader className="animate-spin text-yellow-500" size={16} />,
  success: <CheckCircle className="text-green-500" size={16} />,
  failed: <XCircle className="text-red-500" size={16} />,
};

export default function UploadPage() {
  const [uploads, setUploads] = useState([]);

  const updateUpload = (id, patch) => (
    setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, ...patch } : u)))
  );

  const pollStatus = async (uploadId, invoiceId) => {
    let attempts = 0;
    const maxAttempts = 30;
    const poll = setInterval(async () => {
      attempts += 1;
      try {
        const res = await getInvoice(invoiceId);
        const inv = res.data;
        if (inv.extraction_status === "success" || inv.extraction_status === "failed") {
          clearInterval(poll);
          updateUpload(uploadId, {
            status: inv.extraction_status === "success" ? "success" : "failed",
            invoice: inv,
          });
          if (inv.extraction_status === "success") {
            toast.success(`Invoice processed: ${inv.vendor_name || inv.filename}`);
          } else {
            toast.error("Invoice processing failed.");
          }
        }
      } catch {
        // Ignore polling errors while the backend is still processing.
      }
      if (attempts >= maxAttempts) {
        clearInterval(poll);
        updateUpload(uploadId, { status: "failed" });
      }
    }, 2000);
  };

  const processFile = async (file) => {
    const uploadId = `${Date.now()}-${Math.random()}`;
    setUploads((prev) => [{
      id: uploadId,
      name: file.name,
      size: file.size,
      status: "uploading",
      progress: 0,
      invoice: null,
    }, ...prev]);

    try {
      const res = await uploadInvoice(file, (p) => updateUpload(uploadId, { progress: p }));
      const invoiceId = res.data.invoice_id;
      updateUpload(uploadId, { status: "processing", invoiceId, progress: 100 });
      pollStatus(uploadId, invoiceId);
    } catch (err) {
      updateUpload(uploadId, { status: "failed" });
      toast.error(err.response?.data?.detail || "Upload failed");
    }
  };

  const onDrop = useCallback((accepted) => {
    accepted.forEach(processFile);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [], "image/*": [".png", ".jpg", ".jpeg"] },
    maxSize: 20 * 1024 * 1024,
    multiple: true,
  });

  const fmtSize = (bytes) => (bytes > 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${(bytes / 1024).toFixed(0)} KB`);

  return (
    <div className="p-6 space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Invoices</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Drag &amp; drop PDF or image files. AI will extract and validate automatically.
        </p>
      </div>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          isDragActive
            ? "border-blue-400 bg-blue-50"
            : "border-gray-300 hover:border-blue-400 hover:bg-gray-50"
        }`}
      >
        <input {...getInputProps()} />
        <Upload className={`mx-auto mb-4 ${isDragActive ? "text-blue-500" : "text-gray-400"}`} size={40} />
        <p className="text-base font-medium text-gray-700">
          {isDragActive ? "Drop files here..." : "Drag & drop invoices here"}
        </p>
        <p className="text-sm text-gray-400 mt-1">or click to browse files</p>
        <p className="text-xs text-gray-400 mt-3">PDF, PNG, JPG supported. Max 20MB per file.</p>
      </div>

      {uploads.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Processing Queue
          </h2>
          {uploads.map((u) => (
            <div key={u.id} className="card p-4">
              <div className="flex items-start gap-3">
                <FileText className="text-gray-400 mt-0.5 shrink-0" size={20} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-gray-800 truncate">{u.name}</p>
                    <div className="flex items-center gap-2 shrink-0">
                      {STATUS_ICONS[u.status]}
                      <span className="text-xs capitalize text-gray-500">{u.status}</span>
                    </div>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">{fmtSize(u.size)}</p>

                  {(u.status === "uploading" || u.status === "processing") && (
                    <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          u.status === "processing"
                            ? "bg-yellow-400 w-3/4 animate-pulse"
                            : "bg-blue-500"
                        }`}
                        style={u.status === "uploading" ? { width: `${u.progress}%` } : {}}
                      />
                    </div>
                  )}

                  {u.status === "success" && u.invoice && (
                    <div className="mt-3 bg-green-50 rounded-lg p-3 text-xs space-y-1">
                      <div className="flex items-center gap-1.5 text-green-700 font-medium mb-2">
                        <CheckCircle size={13} /> Extracted Successfully
                      </div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-gray-600">
                        <span>Invoice #: <strong>{u.invoice.invoice_number || "--"}</strong></span>
                        <span>Vendor: <strong>{u.invoice.vendor_name || "--"}</strong></span>
                        <span>Date: <strong>{u.invoice.invoice_date || "--"}</strong></span>
                        <span>Amount: <strong>{`Rs ${Number(u.invoice.total_amount || 0).toLocaleString("en-IN")}`}</strong></span>
                        <span>GSTIN: <strong>{u.invoice.vendor_gstin || "--"}</strong></span>
                        <span>
                          Status:
                          {" "}
                          <strong className={u.invoice.validation_status === "valid" ? "text-green-600" : "text-red-600"}>
                            {u.invoice.validation_status}
                          </strong>
                        </span>
                      </div>
                      {u.invoice.is_duplicate && (
                        <div className="mt-2 flex items-center gap-1.5 text-orange-600 font-medium">
                          <AlertCircle size={13} /> Duplicate invoice detected!
                        </div>
                      )}
                    </div>
                  )}

                  {u.status === "failed" && (
                    <div className="mt-2 flex items-center gap-1.5 text-red-600 text-xs">
                      <XCircle size={13} /> Processing failed. Check file quality and try again.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card bg-blue-50 border-blue-100">
        <h3 className="text-sm font-semibold text-blue-800 mb-2">Tips for best results</h3>
        <ul className="text-sm text-blue-700 space-y-1">
          <li>- Use clear, high-resolution scans (300 DPI or higher)</li>
          <li>- Ensure invoice text is not rotated or skewed</li>
          <li>- Indian GST invoices are supported with GSTIN validation</li>
          <li>- Supported: PDF, PNG, JPG formats</li>
        </ul>
      </div>
    </div>
  );
}
