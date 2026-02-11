import React from "react";

interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: React.ReactNode;
}

const NewspaperIcon = () => (
  <svg
    className="w-16 h-16 text-gray-300 dark:text-gray-600"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1}
  >
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M7 7h4v4H7zM13 7h4M13 11h4M7 15h10" />
  </svg>
);

export default function EmptyState({
  title = "Nothing here",
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <NewspaperIcon />
      <h3 className="mt-4 text-xl font-semibold text-gray-700 dark:text-gray-300">{title}</h3>
      {description && (
        <p className="mt-2 text-gray-500 dark:text-gray-400 text-center max-w-sm">{description}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
