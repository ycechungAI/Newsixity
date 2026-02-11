import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import ThemeProvider from "@/components/ThemeProvider";
import { getCategories, getArticleCountByCategory } from "@/lib/db/queries";
import { startScheduler } from "@/lib/rss/scheduler";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Newsixity",
  description: "AI-powered news aggregator",
};

// Start the background feed refresh scheduler at module level
startScheduler();

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const categories = getCategories();
  const counts = getArticleCountByCategory();

  // Merge categories with their article counts
  const categoriesWithCounts = categories.map((cat) => {
    const count = counts.find((c) => c.slug === cat.slug);
    return {
      ...cat,
      total: count?.total ?? 0,
      unread: count?.unread ?? 0,
    };
  });

  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans`}>
        <ThemeProvider>
          <div className="flex h-screen">
            <Sidebar categories={categoriesWithCounts} />
            <main className="flex-1 ml-64 overflow-y-auto bg-gray-50 dark:bg-gray-950">
              {children}
            </main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
