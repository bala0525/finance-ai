import apiClient from "./apiClient";


export async function getCurrentUser() {
  return apiClient("/users/me");
}

export async function getAdminUsers() {
  return apiClient("/users/admin/users");
}

// NEW: Same-tenant active Finance Users used by invoice upload assignment.
export async function getFinanceUsers() {
  return apiClient("/users/finance-users");
}

export async function getAdminRoles() {
  return apiClient("/users/admin/roles");
}

export async function createAdminUser(payload) {
  return apiClient("/users/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function archiveAdminUser(userId) {
  return apiClient(`/users/admin/users/${userId}`, {
    method: "DELETE",
  });
}

export async function updateAdminUserStatus(userId, isActive) {
  return apiClient(`/users/admin/users/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}
