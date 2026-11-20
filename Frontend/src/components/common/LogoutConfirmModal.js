import React, { useCallback, useState } from "react";
import Modal from "./Modal";

/**
 * Logout confirmation modal.
 *
 * Props:
 *   open     – boolean
 *   onCancel – close without logging out
 *   onLogout – perform logout
 */
function LogoutConfirmModal({ open, onCancel, onLogout }) {
  const [busy, setBusy] = useState(false);

  const handleLogout = useCallback(() => {
    if (busy) return;           // prevent duplicate clicks
    setBusy(true);
    onLogout?.();
    // No need to setBusy(false) — the component unmounts on redirect
  }, [busy, onLogout]);

  const handleCancel = useCallback(() => {
    if (busy) return;
    onCancel?.();
  }, [busy, onCancel]);

  return (
    <Modal
      open={open}
      onClose={handleCancel}
      title="Confirm Logout"
      footer={
        <>
          <button
            type="button"
            className="modal-btn modal-btn-ghost"
            onClick={handleCancel}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="modal-btn modal-btn-danger"
            onClick={handleLogout}
            disabled={busy}
          >
            {busy ? "Logging out…" : "Logout"}
          </button>
        </>
      }
    >
      <p style={{ margin: 0 }}>
        Are you sure you want to log out of your account?
      </p>
    </Modal>
  );
}

export default LogoutConfirmModal;
