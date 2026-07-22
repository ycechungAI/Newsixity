import { useDocumentTitle } from "@/lib/utils/useDocumentTitle";
import FinanceDashboard from "@/components/finance/FinanceDashboard";

export default function FinancePage() {
  useDocumentTitle("Finance - Newsixity");

  return (
    <div className="p-6">
      <FinanceDashboard />
    </div>
  );
}
