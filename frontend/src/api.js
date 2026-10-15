// 127.0.0.1 rather than "localhost": on Windows `localhost` resolves to IPv6 (::1)
// first, while Django's runserver binds IPv4 -- so another local service on :8000
// can silently answer instead of the API.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const STORAGE_KEY = "nhwz-auth";

export function getStoredTokens() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function saveTokens(tokens) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
}

export function clearTokens() {
  localStorage.removeItem(STORAGE_KEY);
}

export function getAccessToken() {
  return getStoredTokens()?.access || null;
}

export function getRefreshToken() {
  return getStoredTokens()?.refresh || null;
}

async function parseResponse(response) {
  const payload = await response.json().catch(() => null);
  if (response.ok) {
    return payload;
  }
  const error = new Error(payload?.detail || "Request failed.");
  error.status = response.status;
  error.payload = payload;
  throw error;
}

let refreshInFlight = null;

// Concurrent callers (several 401s, or WebSockets reconnecting together) share
// one refresh call. With refresh-token rotation a second call would present an
// already-used token and log the user out.
function refreshAccessToken() {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const refresh = getRefreshToken();
      if (!refresh) {
        throw new Error("No refresh token available.");
      }
      const response = await fetch(`${BASE_URL}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
      const data = await parseResponse(response);
      saveTokens({ access: data.access, refresh: data.refresh || refresh });
      return data.access;
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

/**
 * Authenticated request that returns the raw Response (after one token refresh
 * on 401). JSON is the default body type; FormData is passed through untouched
 * so the browser can set the multipart boundary itself.
 */
async function authRequest(path, options = {}) {
  const tokens = getStoredTokens();
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers = {
    ...(isForm ? {} : { "Content-Type": "application/json" }),
    ...(options.headers || {}),
  };

  if (tokens?.access) {
    headers.Authorization = `Bearer ${tokens.access}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (response.status === 401 && tokens?.refresh) {
    try {
      const access = await refreshAccessToken();
      headers.Authorization = `Bearer ${access}`;
      return await fetch(`${BASE_URL}${path}`, { ...options, headers });
    } catch (error) {
      clearTokens();
      throw error;
    }
  }
  return response;
}

export async function authFetch(path, options = {}) {
  return parseResponse(await authRequest(path, options));
}

/** Obtain a fresh access token (used when a WebSocket is rejected with 4001). */
export { refreshAccessToken };

export async function login(email, password) {
  const response = await fetch(`${BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await parseResponse(response);
  saveTokens(data.tokens);
  return data.user;
}

export async function register(payload) {
  const response = await fetch(`${BASE_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await parseResponse(response);
  saveTokens(data.tokens);
  return { user: data.user, otp: data.otp };
}

export async function verifyOtp(identifier, purpose, code) {
  const response = await fetch(`${BASE_URL}/api/auth/verify-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier, purpose, code }),
  });
  return parseResponse(response);
}

export async function requestOtp(identifier, purpose, channel = "sms") {
  const response = await fetch(`${BASE_URL}/api/auth/request-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier, purpose, channel }),
  });
  return parseResponse(response);
}

export async function fetchIncidents(params = {}) {
  const qs = new URLSearchParams({ page: 1, ...params }).toString();
  return authFetch(`/api/incidents/?${qs}`);
}

export async function fetchIncident(id) {
  return authFetch(`/api/incidents/${id}/`);
}

export async function createIncident(payload) {
  return authFetch("/api/incidents/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateIncident(id, payload) {
  return authFetch(`/api/incidents/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function transitionIncidentStatus(id, newStatus) {
  // DRF derives the route from the action name: `transition_status`.
  return authFetch(`/api/incidents/${id}/transition_status/`, {
    method: "POST",
    body: JSON.stringify({ new_status: newStatus }),
  });
}

export async function verifyIncident(id) {
  // The endpoint validates the body with the shared transition serializer.
  return authFetch(`/api/incidents/${id}/verify/`, {
    method: "POST",
    body: JSON.stringify({ new_status: "verified" }),
  });
}

// ── Geospatial ─────────────────────────────────────────────────────────────

/** Incidents within `radiusM` metres of a point, nearest first. */
export async function fetchNearbyIncidents({ latitude, longitude, radiusM = 5000, statuses = [] }) {
  const qs = new URLSearchParams({ latitude, longitude, radius_m: radiusM });
  statuses.forEach((s) => qs.append("status", s));
  return authFetch(`/api/incidents/nearby/?${qs.toString()}`);
}

/** Server-side grid aggregation. Provide `bounds` [minLat, minLon, maxLat, maxLon] or `neighborhoodId`. */
export async function fetchHeatmap({ bounds, neighborhoodId, days = 30 }) {
  const qs = new URLSearchParams({ days });
  if (neighborhoodId) qs.set("neighborhood_id", neighborhoodId);
  else if (bounds) qs.set("bounds", bounds.map((n) => Number(n).toFixed(6)).join(","));
  return authFetch(`/api/incidents/heatmap/?${qs.toString()}`);
}

// ── Neighbourhoods ─────────────────────────────────────────────────────────

export async function fetchNeighborhoods() {
  const data = await authFetch("/api/neighborhoods/");
  return Array.isArray(data) ? data : data.results ?? [];
}

export async function joinNeighborhood(id) {
  return authFetch(`/api/neighborhoods/${id}/join/`, { method: "POST" });
}

export async function leaveNeighborhood(id) {
  return authFetch(`/api/neighborhoods/${id}/leave/`, { method: "DELETE" });
}

export async function fetchRiskSummary(id, days = 30) {
  return authFetch(`/api/neighborhoods/${id}/risk_summary/?days=${days}`);
}

// ── SOS ────────────────────────────────────────────────────────────────────

export async function createSosAlert({ latitude, longitude, address = "" }) {
  return authFetch("/api/sos/", {
    method: "POST",
    body: JSON.stringify({ current_latitude: latitude, current_longitude: longitude, address }),
  });
}

export async function fetchSosAlerts() {
  const data = await authFetch("/api/sos/");
  return Array.isArray(data) ? data : data.results ?? [];
}

export async function fetchActiveSosAlerts() {
  const data = await authFetch("/api/sos/active/");
  return Array.isArray(data) ? data : data.results ?? [];
}

export async function pingSosAlert(id, { latitude, longitude, accuracy }) {
  return authFetch(`/api/sos/${id}/ping/`, {
    method: "POST",
    body: JSON.stringify({
      latitude,
      longitude,
      accuracy_m: accuracy == null ? null : Number(Number(accuracy).toFixed(2)), // DecimalField(8, 2)
      captured_at: new Date().toISOString(),
    }),
  });
}

export async function resolveSosAlert(id) {
  return authFetch(`/api/sos/${id}/resolve/`, { method: "POST" });
}

export async function cancelSosAlert(id) {
  return authFetch(`/api/sos/${id}/cancel/`, { method: "POST" });
}

// ── Incident media ─────────────────────────────────────────────────────────

export async function uploadIncidentMedia(incidentId, file) {
  const kind = (file.type || "").split("/")[0];
  const media_type = ["image", "video", "audio"].includes(kind) ? kind : null;
  if (!media_type) {
    const error = new Error("Only image, video or audio files can be attached.");
    error.payload = { file: ["Only image, video or audio files can be attached."] };
    throw error;
  }
  const form = new FormData();
  form.append("media_type", media_type);
  form.append("file", file);
  return authFetch(`/api/incidents/${incidentId}/upload_media/`, { method: "POST", body: form });
}

export async function deleteIncidentMedia(mediaId) {
  return authFetch(`/api/media/${mediaId}/`, { method: "DELETE" });
}

/**
 * Evidence files are served by an endpoint that needs the Bearer token, which a
 * plain <a href> cannot send. Fetch them with auth and hand back a blob URL.
 * Absolute URLs on another host (e.g. pre-signed object-storage links) are
 * already self-authorising and are returned unchanged.
 */
export async function resolveMediaUrl(fileUrl) {
  if (!fileUrl) throw new Error("This file has no URL.");
  const url = new URL(fileUrl, window.location.origin);
  const match = url.pathname.match(/^\/(?:api\/)?media\/(.+)$/);
  if (!match) return { url: url.toString(), revoke: () => {} };
  const response = await authRequest(`/api/media/${match[1]}`);
  if (!response.ok) {
    const error = new Error(response.status === 404 ? "File not found." : "Could not load this file.");
    error.status = response.status;
    throw error;
  }
  const objectUrl = URL.createObjectURL(await response.blob());
  return { url: objectUrl, revoke: () => URL.revokeObjectURL(objectUrl) };
}

export function extractErrors(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return {};
  // eslint-disable-next-line no-unused-vars
  const { detail, ...fieldErrors } = payload;
  return fieldErrors;
}

export async function fetchProfile() {
  return authFetch("/api/users/me");
}

export async function updateProfile(payload) {
  return authFetch("/api/users/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function logout(refresh) {
  return authFetch("/api/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh }),
  });
}

/** Flag the signed-in resident's account for an admin to consider as a block captain. */
export async function applyForBlockCaptain() {
  return authFetch("/api/users/me/apply-block-captain", { method: "POST" });
}

export async function createVerificationRequest(notes) {
  return authFetch("/api/verification-requests", {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
}

export async function fetchPendingVerificationRequests() {
  return authFetch("/api/coordinator/verification-requests");
}

export async function decideVerificationRequest(id, decision, reason) {
  return authFetch(`/api/coordinator/verification-requests/${id}/${decision}`, {
    method: "POST",
    body: JSON.stringify({ decision_reason: reason }),
  });
}

// ── Notifications ──────────────────────────────────────────────────────────

export async function fetchNotifications(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return authFetch(`/api/me/notifications/${qs ? `?${qs}` : ''}`);
}

export async function markNotificationRead(id) {
  return authFetch(`/api/notifications/${id}/read/`, { method: "PATCH" });
}

export async function deleteNotification(id) {
  return authFetch(`/api/notifications/${id}/`, { method: "DELETE" });
}

export async function fetchNotificationPreferences() {
  return authFetch("/api/me/notification-preferences/");
}

export async function updateNotificationPreferences(payload) {
  return authFetch("/api/me/notification-preferences/", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// ── WebSocket helpers ──────────────────────────────────────────────────────

const WS_BASE_URL = (import.meta.env.VITE_WS_BASE_URL || BASE_URL)
  .replace(/^http/, "ws");

/**
 * Open a WebSocket to ``path`` authenticated with the stored JWT.
 * Returns the WebSocket instance.  Callers are responsible for attaching
 * onmessage / onerror / onclose handlers.
 *
 * The token is sent as a ``?token=`` query-string param because the
 * WebSocket upgrade request does not carry Authorization headers.
 */
export function openWebSocket(path) {
  const token = getAccessToken();
  const url = `${WS_BASE_URL}${path}${token ? `?token=${token}` : ''}`;
  return new WebSocket(url);
}

export function openIncidentSocket(incidentId) {
  return openWebSocket(`/ws/incidents/${incidentId}/`);
}

export function openNotificationSocket() {
  return openWebSocket("/ws/notifications/");
}

// ── Live location ──────────────────────────────────────────────────────────

/** Tell the server where this device is, so nearby incidents and SOS alarms reach it. */
export async function reportMyLocation({ latitude, longitude }) {
  return authFetch("/api/me/location", {
    method: "POST",
    body: JSON.stringify({ latitude: Number(latitude).toFixed(6), longitude: Number(longitude).toFixed(6) }),
  });
}
