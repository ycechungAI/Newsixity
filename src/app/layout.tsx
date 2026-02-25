import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import ThemeProvider from "@/components/ThemeProvider";
import { getCategories, getArticleCountByCategory } from "@/lib/db/queries";
import { ensureBackgroundServicesStarted } from "@/lib/server/background-services";

export const metadata: Metadata = {
  title: "Newsixity",
  description: "AI-powered news aggregator",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  ensureBackgroundServicesStarted();

  const categories = getCategories();
  const counts = getArticleCountByCategory();

  const categoriesWithCounts = categories.map((cat) => {
    const count = counts.find((c) => c.slug === cat.slug);
    return { ...cat, total: count?.total ?? 0, unread: count?.unread ?? 0 };
  });

  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <div className="layout">
            <Sidebar categories={categoriesWithCounts} />
            <div className="main">
              <TopBar />
              {children}
            </div>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
