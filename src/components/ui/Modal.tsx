"use client";

import { useEffect, useCallback } from "react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export default function Modal({ isOpen, onClose, title, children }: ModalProps) {
  const handleEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") onClose();
  }, [onClose]);

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "";
    };
  }, [isOpen, handleEscape]);

  if (!isOpen) return null;

  return (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}
      onClick={onClose}
    >
      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.5)", zIndex: 9998 }} />
      <div
        style={{ position: "relative", zIndex: 10000, background: "var(--surface)", border: "1px solid var(--border)", width: "100%", maxWidth: 560, maxHeight: "80vh", overflowY: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
          <span style={{ fontSize: 13, fontWeight: 700 }}>{title}</span>
          <button
            onClick={onClose}
            style={{ border: "1px solid var(--border)", background: "none", color: "var(--muted)", padding: "1px 7px", font: "inherit", fontSize: 11, cursor: "pointer" }}
          >✕</button>
        </div>
        <div style={{ padding: "10px 12px" }}>{children}</div>
      </div>
    </div>
  );
}
