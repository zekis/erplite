export type Row = Record<string, any>;
declare global {
  interface Window {
    workzBoot?: { user: string; csrf_token: string; office_contract?: number; routes?: Record<string, string> };
  }
}
export async function api(action: string, payload: Row = {}): Promise<any> {
  const response = await fetch("/api/method/erplite.workz.api.run", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Frappe-CSRF-Token": window.workzBoot?.csrf_token || "",
    },
    body: JSON.stringify({ action, payload }),
  });
  const result = await response.json();
  if (!response.ok || result.exc) {
    let message = result.message || "Could not save. Refresh and try again.";
    try {
      message = JSON.parse(JSON.parse(result._server_messages)[0]).message;
    } catch {}
    const error = new Error(String(message).replace(/<[^>]*>/g, ""));
    Object.assign(error, {status:response.status});
    throw error;
  }
  return result.message;
}
