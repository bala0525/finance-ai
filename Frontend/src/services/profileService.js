import apiClient from "./apiClient";

/*
 * Profile service - backed by the /users/me/profile API.
 *   GET    /users/me/profile          read
 *   PUT    /users/me/profile          create / update (empty string clears)
 *   DELETE /users/me/profile/{field}  delete one optional detail
 *
 * The page expects { personal, organization, account }; it is built here from
 * the flat API response.
 */

export const DELETABLE_FIELDS = ["phone", "department", "jobTitle", "location", "bio"];

const API_FIELD = {
  phone: "phone",
  department: "department",
  jobTitle: "job_title",
  location: "location",
  bio: "bio",
};

function toProfileShape(p) {
  return {
    personal: {
      name: p.fullName || "",
      email: p.email || "",
      role: p.roleName || "Finance User",
      department: p.department || "",
      phone: p.phone || "",
      jobTitle: p.jobTitle || "",
      location: p.location || "",
      bio: p.bio || "",
    },
    organization: {
      company: "Azentmart",
      workspace: "Finance Intelligence Platform",
      timezone: p.timezone || "Asia/Kolkata",
      currency: "INR (₹)",
    },
    account: {
      status: p.isActive ? "ACTIVE" : "INACTIVE",
      memberSince: p.createdAt
        ? new Date(p.createdAt).toLocaleDateString("en-GB", { month: "long", year: "numeric" })
        : "—",
      lastLogin: "Current session",
      authentication: "Password",
    },
  };
}

export async function getProfile() {
  return toProfileShape(await apiClient("/users/me/profile"));
}

export async function updateProfile(profile) {
  const personal = profile.personal || {};
  const body = {
    full_name: (personal.name || "").trim(),
    phone: (personal.phone || "").trim(),
    department: (personal.department || "").trim(),
    job_title: (personal.jobTitle || "").trim(),
    location: (personal.location || "").trim(),
    bio: (personal.bio || "").trim(),
  };
  if (profile.organization?.timezone) {
    body.timezone = profile.organization.timezone;
  }
  const result = await apiClient("/users/me/profile", {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return toProfileShape(result);
}

export async function deleteProfileField(field) {
  const result = await apiClient(`/users/me/profile/${API_FIELD[field]}`, {
    method: "DELETE",
  });
  return toProfileShape(result);
}
