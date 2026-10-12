// Shared incident vocabulary used by the list, detail and map views.

export const CATEGORY_OPTIONS = [
  { value: 'theft', label: 'Theft' },
  { value: 'burglary', label: 'Burglary' },
  { value: 'assault', label: 'Assault' },
  { value: 'suspicious_activity', label: 'Suspicious Activity' },
  { value: 'missing_person', label: 'Missing Person' },
  { value: 'vandalism', label: 'Vandalism' },
  { value: 'infrastructure_damage', label: 'Infrastructure Damage' },
];

export const SEVERITY_OPTIONS = [
  { value: 'green', label: 'Normal' },
  { value: 'blue', label: 'Average' },
  { value: 'yellow', label: 'Important' },
  { value: 'red', label: 'Critical' },
];

export const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pending' },
  { value: 'verified', label: 'Verified' },
  { value: 'investigating', label: 'Investigating' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
];

export const SEVERITY_COLORS = {
  red: '#ef4444',
  yellow: '#f59e0b',
  blue: '#38bdf8',
  green: '#22c55e',
};

// Harare — used whenever there is nothing better to centre on.
export const DEFAULT_CENTER = [-17.8292, 31.0522];

export function severityColor(severity) {
  return SEVERITY_COLORS[severity] || '#94a3b8';
}

export function severityVariant(severity) {
  return { red: 'danger', yellow: 'warning', blue: 'primary', green: 'success' }[severity] || 'gray';
}

export function statusVariant(status) {
  return {
    pending: 'warning',
    verified: 'success',
    investigating: 'primary',
    resolved: 'accent',
    closed: 'gray',
  }[status] || 'gray';
}

export function isCoordinatorRole(user) {
  const code = user?.role?.code;
  return code === 'coordinator' || code === 'system_admin';
}

export function hasValidCoords(item, latKey = 'latitude', lonKey = 'longitude') {
  const lat = Number(item?.[latKey]);
  const lon = Number(item?.[lonKey]);
  return (
    item?.[latKey] != null && item?.[lonKey] != null &&
    Number.isFinite(lat) && Number.isFinite(lon) &&
    Math.abs(lat) <= 90 && Math.abs(lon) <= 180
  );
}

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

export function formatDate(value, withTime = false) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return withTime ? d.toLocaleString() : d.toLocaleDateString();
}

/** Coerce a DRF error payload value ("msg" | ["msg"]) into a display string. */
export function firstError(value) {
  if (!value) return null;
  if (Array.isArray(value)) return String(value[0]);
  if (typeof value === 'object') return firstError(Object.values(value)[0]);
  return String(value);
}

/** ISO timestamp -> value for <input type="datetime-local"> in the browser's timezone. */
export function toLocalInput(value) {
  const d = value ? new Date(value) : new Date();
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** <input type="datetime-local"> value -> unambiguous ISO string. */
export function fromLocalInput(value) {
  if (!value) return value;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toISOString();
}

export function getCurrentPosition(options = { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation is not supported by this browser.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy }),
      (err) => reject(new Error(err.code === 1 ? 'Location permission was denied.' : 'Could not determine your location.')),
      options,
    );
  });
}
