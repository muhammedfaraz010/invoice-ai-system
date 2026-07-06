const FORMATTERS = {
  INR: new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }),
  USD: new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }),
  AED: new Intl.NumberFormat("en-AE", {
    style: "currency",
    currency: "AED",
    maximumFractionDigits: 2,
  }),
};

export const formatCurrency = (amount, currency = "INR", compact = false) => {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) {
    return "--";
  }

  const code = (currency || "INR").toUpperCase();
  const value = Number(amount);

  if (compact && code === "INR" && Math.abs(value) >= 100000) {
    return `Rs ${(value / 100000).toFixed(1)}L`;
  }

  if (FORMATTERS[code]) {
    return FORMATTERS[code].format(value);
  }

  return `${code} ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};
