"use client";

interface ErrorBannerProps {
  type: "warning" | "error";
  message: string;
  onDismiss?: () => void;
}

const CloseIcon = () => (
  <svg
    className="w-4 h-4"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={2}
  >
    <path d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const WarningIcon = () => (
  <svg
    className="w-5 h-5 flex-shrink-0"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path d="M12 9v4m0 4h.01M10.29 3.86l-8.58 14.87A1.98 1.98 0 0 0 3.43 21h17.14a1.98 1.98 0 0 0 1.72-2.27L13.71 3.86a2 2 0 0 0-3.42 0z" />
  </svg>
);

const ErrorIcon = () => (
  <svg
    className="w-5 h-5 flex-shrink-0"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <circle cx="12" cy="12" r="10" />
    <path d="M15 9l-6 6M9 9l6 6" />
  </svg>
);

export default function ErrorBanner({
  type,
  message,
  onDismiss,
}: ErrorBannerProps) {
  const styles =
    type === "warning"
      ? "bg-yellow-50 text-yellow-800 border-yellow-200"
      : "bg-red-50 text-red-800 border-red-200";

  const dismissStyles =
    type === "warning"
      ? "text-yellow-600 hover:text-yellow-800 hover:bg-yellow-100"
      : "text-red-600 hover:text-red-800 hover:bg-red-100";

  return (
    <div
      className={`border rounded-lg px-4 py-3 flex items-center gap-3 ${styles}`}
      role="alert"
    >
      {type === "warning" ? <WarningIcon /> : <ErrorIcon />}
      <p className="text-sm flex-1">{message}</p>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className={`p-1 rounded transition-colors ${dismissStyles}`}
          aria-label="Dismiss"
        >
          <CloseIcon />
        </button>
      )}
    </div>
  );
}
