import React from "react";
import {
  AlertTriangle,
  CheckCircle,
  Info,
  XCircle,
} from "lucide-react";

export const STATUS_META = {
  verified: {
    label: "Verified",
    badge: "badge-green",
    icon: CheckCircle,
    tooltip: "All invoice information extracted successfully.",
  },
  complete: {
    label: "Complete",
    badge: "badge-blue",
    icon: Info,
    tooltip: "Invoice processed successfully. Some optional information was not present.",
  },
  needs_review: {
    label: "Needs Review",
    badge: "badge-yellow",
    icon: AlertTriangle,
    tooltip: "Required invoice information is missing.",
  },
  failed: {
    label: "Failed",
    badge: "badge-red",
    icon: XCircle,
    tooltip: "Invoice could not be processed.",
  },
  pending: {
    label: "Pending",
    badge: "badge-gray",
    icon: Info,
    tooltip: "Invoice processing is still pending.",
  },
  success: {
    label: "Success",
    badge: "badge-green",
    icon: CheckCircle,
    tooltip: "Processing completed successfully.",
  },
};

const normalizeStatus = (status) => {
  if (status === "valid") return "verified";
  if (status === "invalid") return "needs_review";
  return status || "pending";
};

export const getStatusMeta = (status) => (
  STATUS_META[normalizeStatus(status)] || {
    label: String(status || "Unknown"),
    badge: "badge-gray",
    icon: Info,
    tooltip: "Status unavailable.",
  }
);

export const StatusBadge = ({ status, showIcon = true }) => {
  const meta = getStatusMeta(status);
  const Icon = meta.icon;
  return (
    <span className={`${meta.badge} gap-1`} title={meta.tooltip}>
      {showIcon && <Icon size={13} />}
      {meta.label}
    </span>
  );
};

export const requiredFields = [
  "Invoice Number",
  "Vendor",
  "Invoice Date",
  "Amount",
  "Currency",
];

export const optionalFields = [
  "GSTIN",
  "Buyer",
  "Due Date",
  "Tax",
  "Payment Terms",
  "Line Items",
];
