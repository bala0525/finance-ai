import React, { useCallback, useEffect, useRef } from "react";
import "./Modal.css";

/**
 * Reusable accessible modal component.
 *
 * Props:
 *   open       – boolean, whether the modal is visible
 *   onClose    – called when the user closes (Escape, backdrop, close button)
 *   title      – optional header text
 *   children   – body content
 *   footer     – optional ReactNode rendered in the footer area
 *   className  – extra CSS class on the panel
 *   size       – "sm" | "md" (default "sm")
 */
function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  className = "",
  size = "sm",
}) {
  const panelRef = useRef(null);

  // Close on Escape
  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose?.();
      }
    },
    [onClose]
  );

  useEffect(() => {
    if (!open) return;

    document.addEventListener("keydown", handleKeyDown);

    // Prevent body scroll while modal is open
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Focus the panel for keyboard users
    panelRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = prev;
    };
  }, [open, handleKeyDown]);

  if (!open) return null;

  return (
    <div
      className="modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
      role="presentation"
    >
      <div
        ref={panelRef}
        className={`modal-panel modal-${size} ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? "modal-title" : undefined}
        tabIndex={-1}
      >
        {title && (
          <div className="modal-header">
            <h2 id="modal-title" className="modal-title">
              {title}
            </h2>
            <button
              type="button"
              className="modal-close"
              onClick={onClose}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
        )}

        <div className="modal-body">{children}</div>

        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}

export default Modal;
