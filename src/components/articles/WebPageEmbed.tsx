"use client";

interface WebPageEmbedProps {
  url: string;
  title?: string;
  className?: string;
}

export default function WebPageEmbed({ url, title, className = "" }: WebPageEmbedProps) {
  return (
    <div className={`relative w-full overflow-hidden rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 ${className}`}>
      {/* Container with 16:9 aspect ratio for consistent sizing */}
      <div style={{ paddingBottom: "56.25%" }} className="relative">
        <iframe
          src={url}
          title={title}
          className="absolute top-0 left-0 w-full h-full border-0"
          sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
          loading="lazy"
        />
      </div>
      <div className="p-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
          <a href={url} target="_blank" rel="noopener noreferrer" className="hover:text-gray-700 dark:hover:text-gray-300">
            {url}
          </a>
        </p>
      </div>
    </div>
  );
}
