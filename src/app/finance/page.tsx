import type { Metadata } from "next";
import FinanceDashboard from "@/components/finance/FinanceDashboard";

export const metadata: Metadata = {
  title: "Finance - Newsixity",
  description: "Stock market dashboard with quotes and charts",
};

export default function FinancePage() {
  return (
    <div className="p-6">
      <FinanceDashboard />
    </div>
  );
}
