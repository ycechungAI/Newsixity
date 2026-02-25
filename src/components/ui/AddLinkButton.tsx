"use client";

import { useState } from "react";
import AddManualLinkModal from "@/components/articles/AddManualLinkModal";

const PlusIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
  </svg>
);

export default function AddLinkButton() {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className="flex items-center gap-2 px-4 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors text-sm font-medium"
      >
        <PlusIcon />
        <span>Add Link</span>
      </button>
      <AddManualLinkModal isOpen={showModal} onClose={() => setShowModal(false)} />
    </>
  );
}
