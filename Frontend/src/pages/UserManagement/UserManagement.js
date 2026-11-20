import React, { useEffect, useMemo, useState } from "react";
import { archiveAdminUser, createAdminUser, getAdminRoles, getAdminUsers, getCurrentUser, updateAdminUserStatus } from "../../services/userService";
import { SkeletonBlock } from "../../components/common/Loader";
import "./UserManagement.css";

const initialForm = { full_name: "", email: "", password: "", role_id: "", department: "" };

function UserManagement() {
  const [users, setUsers] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [deletingUserId, setDeletingUserId] = useState(null);
  const [roles, setRoles] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const [userRows, roleRows, me] = await Promise.all([
        getAdminUsers(),
        getAdminRoles(),
        getCurrentUser().catch(() => null),
      ]);
      setCurrentUser(me);
      setUsers(Array.isArray(userRows) ? userRows : []);
      setRoles(Array.isArray(roleRows) ? roleRows : []);
      setForm((current) => ({ ...current, role_id: current.role_id || String(roleRows?.[0]?.id || "") }));
    } catch (err) {
      setError(err.message || "Unable to load user management data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, []);

  const filteredUsers = useMemo(() => {
    const term = search.trim().toLowerCase();
    return users.filter((user) => {
      const roleName = user.role_name || user.role?.name || "";
      const matchesText = !term || [user.full_name, user.email, user.department, roleName].some((value) => String(value || "").toLowerCase().includes(term));
      return matchesText && (roleFilter === "ALL" || String(user.role_id) === roleFilter);
    });
  }, [users, search, roleFilter]);

  async function handleCreate(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setSaving(true);
    try {
      await createAdminUser({ ...form, role_id: Number(form.role_id), department: form.department.trim() || null });
      setNotice("User created successfully.");
      setForm({ ...initialForm, role_id: String(roles[0]?.id || "") });
      setShowPassword(false);
      await loadData();
    } catch (err) {
      setError(err.message || "Unable to create user.");
    } finally {
      setSaving(false);
    }
  }

  async function handleStatus(user) {
    const nextStatus = !user.is_active;
    const confirmed = window.confirm(`${nextStatus ? "Activate" : "Deactivate"} ${user.full_name}?`);
    if (!confirmed) return;
    setError("");
    setNotice("");
    try {
      await updateAdminUserStatus(user.id, nextStatus);
      setNotice(`User ${nextStatus ? "activated" : "deactivated"} successfully.`);
      await loadData();
    } catch (err) {
      setError(err.message || "Unable to update user status.");
    }
  }

  async function handleArchive(user) {
    const confirmed = window.confirm(
      `Archive ${user.full_name}? They will lose access, but their finance records and audit history will be preserved.`
    );
    if (!confirmed) return;

    setError("");
    setNotice("");
    setDeletingUserId(user.id);

    try {
      await archiveAdminUser(user.id);
      setNotice(`${user.full_name} archived successfully. Financial records were preserved.`);
      await loadData();
    } catch (err) {
      setError(err.message || "Unable to archive user.");
    } finally {
      setDeletingUserId(null);
    }
  }

  return (
    <div className="user-management-page">
      <header className="um-header">
        <div><span className="um-eyebrow">ADMINISTRATION</span><h1>User Management</h1><p>Create accounts, assign finance roles and manage account access.</p></div>
        <div className="um-total"><strong>{users.length}</strong><span>Total users</span></div>
      </header>

      {error && <div className="um-alert um-error" role="alert">{error}</div>}
      {notice && <div className="um-alert um-success" role="status">{notice}</div>}

      <section className="um-panel">
        <div className="um-panel-heading"><div><h2>Create user</h2><p>New accounts created here are verified and active.</p></div></div>
        <form className="um-form" onSubmit={handleCreate}>
          <label>Full name<input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} minLength="2" maxLength="150" required placeholder="Enter full name" /></label>
          <label>Work email<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required placeholder="name@company.com" /></label>
          <label className="um-password-label">Temporary password
            <div className="um-password-wrapper">
              <input type={showPassword ? "text" : "password"} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required placeholder="Enter temporary password" autoComplete="new-password" />
              <button
                type="button"
                className="um-password-toggle"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                title={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8" />
                    <path d="M9.9 5.2A10.8 10.8 0 0112 5c5.5 0 9 7 9 7a14 14 0 01-3.1 3.9M6.2 6.2C3.9 7.8 3 12 3 12s3.5 7 9 7a9.8 9.8 0 003-.5" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </label>
          <label>Role<select value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })} required><option value="" disabled>Select role</option>{roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
          <label>Department<input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} maxLength="100" required placeholder="e.g. Finance" /></label>
          <div className="um-form-action"><button type="submit" disabled={saving || loading || !roles.length || !form.full_name.trim() || !form.email.trim() || !form.password || !form.role_id || !form.department.trim()}>{saving ? "Creating..." : "Create user"}</button></div>
        </form>
      </section>

      <section className="um-panel">
        <div className="um-panel-heading"><div><h2>Users</h2><p>Search accounts and manage active status.</p></div><span className="um-count">{filteredUsers.length} shown</span></div>
        <div className="um-toolbar"><input aria-label="Search users" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, email, department..." /><select aria-label="Filter by role" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}><option value="ALL">All roles</option>{roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></div>
        {loading ? (
          <div className="um-skeleton-table" role="status" aria-label="Loading users">
            <div className="um-skeleton-table-head">
              {["User", "Role", "Department", "Status", "Created", "Action"].map((label) => (
                <span key={label}>{label}</span>
              ))}
            </div>
            {Array.from({ length: 5 }).map((_, row) => (
              <div className="um-skeleton-table-row" key={row}>
                <div className="um-skeleton-user">
                  <SkeletonBlock style={{ width: "72%", height: 12 }} />
                  <SkeletonBlock style={{ width: "55%", height: 9, marginTop: 8 }} />
                </div>
                <SkeletonBlock style={{ width: "65%", height: 11 }} />
                <SkeletonBlock style={{ width: "60%", height: 11 }} />
                <SkeletonBlock style={{ width: 55, height: 20, borderRadius: 20 }} />
                <SkeletonBlock style={{ width: "65%", height: 11 }} />
                <SkeletonBlock style={{ width: 75, height: 27, borderRadius: 5 }} />
              </div>
            ))}
          </div>
        ) : filteredUsers.length === 0 ? <div className="um-empty">No users match your search.</div> : (
          <div className="um-table-wrap"><table className="um-table"><thead><tr><th>User</th><th>Role</th><th>Department</th><th>Status</th><th>Created</th><th>Action</th></tr></thead><tbody>
            {filteredUsers.map((user) => <tr key={user.id}><td><strong>{user.full_name}</strong><small>{user.email}</small></td><td>{user.role_name || user.role?.name || "—"}</td><td>{user.department || "—"}</td><td><span className={`um-status ${user.is_active ? "active" : "inactive"}`}>{user.is_active ? "Active" : "Inactive"}</span></td><td>{user.created_at ? new Date(user.created_at).toLocaleDateString("en-IN") : "—"}</td><td>
        {(() => {
          const isAdmin = (user.role_name || user.role?.name || "").trim().toLowerCase() === "administrator";
          const isSelf = currentUser && String(currentUser.id) === String(user.id);
          return (
            <div className="um-row-actions">
              {isAdmin ? (
                <span className="um-protected-label">Protected</span>
              ) : (
                <>
                  <button
                    className={`um-status-button ${user.is_active ? "deactivate" : "activate"}`}
                    type="button"
                    onClick={() => handleStatus(user)}
                  >
                    {user.is_active ? "Deactivate" : "Activate"}
                  </button>
                  {!isSelf && (
                    <button
                      className="um-delete-button"
                      type="button"
                      onClick={() => handleArchive(user)}
                      disabled={deletingUserId === user.id}
                      aria-label={`Archive ${user.full_name}`}
                      title={deletingUserId === user.id ? "Archiving..." : "Archive user"}
                    >
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M3 6h18M8 6V4h8v2m-9 0 1 14h8l1-14M10 10v6m4-6v6" />
                      </svg>
                    </button>
                  )}
                </>
              )}
            </div>
          );
        })()}
      </td></tr>)}
          </tbody></table></div>
        )}
      </section>
    </div>
  );
}

export default UserManagement;
