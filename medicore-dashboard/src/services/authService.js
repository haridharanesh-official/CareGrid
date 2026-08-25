const SESSION_KEY = "caregrid_demo_session";
const allowedRoles = ["ambulance", "nurse", "doctor"];

export async function login({ name, role }) {
  if (!allowedRoles.includes(role)) throw new Error("Select a valid CareGrid role");
  const session = { id:`demo-${role}`, name:name || role[0].toUpperCase()+role.slice(1), role, issuedAt:Date.now() };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}
export async function logout() { sessionStorage.removeItem(SESSION_KEY); }
export function getSession() { try { return JSON.parse(sessionStorage.getItem(SESSION_KEY)); } catch { return null; } }
