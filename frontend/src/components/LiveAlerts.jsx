import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, Siren, Volume2, X } from 'lucide-react';
import { openNotificationSocket, reportMyLocation } from '../api';
import useWebSocket from '../hooks/useWebSocket';
import { getCurrentPosition } from '../lib/incidents';
import { armSiren, startSiren, stopSiren } from '../lib/siren';

const LOCATION_EVERY_MS = 60000;

/**
 * App-wide live channel for a signed-in user. It:
 *  - keeps the server told where this device is, so "nearby" means nearby now;
 *  - sounds a siren and shows a banner when someone close by triggers an SOS;
 *  - hands freshly reported nearby incidents to the map (via window events).
 */
export default function LiveAlerts({ user }) {
  const navigate = useNavigate();
  const [alarms, setAlarms] = useState([]); // newest first
  const [needsTap, setNeedsTap] = useState(false);

  useEffect(() => armSiren(), []);

  // Location reporting. Failure (permission denied, no GPS) is fine: the server
  // falls back to the home address.
  useEffect(() => {
    let cancelled = false;
    const report = async () => {
      try {
        const pos = await getCurrentPosition({ enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
        if (!cancelled) await reportMyLocation(pos);
      } catch { /* optional */ }
    };
    report();
    const timer = setInterval(report, LOCATION_EVERY_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, [user?.id]);

  // Siren follows the alarm list: on while any alarm is open, off when empty.
  const alarmCount = alarms.length;
  useEffect(() => {
    if (alarmCount === 0) {
      stopSiren();
      setNeedsTap(false);
      return undefined;
    }
    let cancelled = false;
    startSiren().then((playing) => { if (!cancelled) setNeedsTap(!playing); });
    navigator.vibrate?.([400, 200, 400, 200, 400]);
    return () => { cancelled = true; };
  }, [alarmCount]);

  useEffect(() => () => stopSiren(), []);

  const factory = useCallback(() => openNotificationSocket(), []);
  const onMessage = useCallback((event) => {
    let msg;
    try { msg = JSON.parse(event.data); } catch { return; }

    if (msg.type === 'notification_created' && msg.notification?.payload?.kind === 'sos_alert') {
      const n = msg.notification;
      const alarm = {
        id: n.payload.sos_alert_id || n.id,
        title: n.title,
        body: n.body,
        lat: Number(n.payload.latitude),
        lng: Number(n.payload.longitude),
      };
      setAlarms((list) => [alarm, ...list.filter((a) => a.id !== alarm.id)]);
    } else if (msg.type === 'sos_ended') {
      setAlarms((list) => list.filter((a) => a.id !== msg.sos_alert_id));
    } else if (msg.type === 'incident_nearby') {
      window.dispatchEvent(new CustomEvent('nhwz:incident-nearby', { detail: msg.incident }));
    }
  }, []);
  useWebSocket(factory, onMessage, { enabled: !!user });

  const showOnMap = (alarm) => {
    const params = Number.isFinite(alarm.lat) && Number.isFinite(alarm.lng)
      ? `?sos=${alarm.id}&lat=${alarm.lat}&lng=${alarm.lng}` : '';
    navigate(`/map${params}`);
  };

  if (alarmCount === 0) return null;
  const alarm = alarms[0];

  return (
    <div role="alertdialog" aria-live="assertive" aria-label="SOS alert nearby" className="fixed inset-x-0 top-0 z-[2000] p-3 sm:p-4 pointer-events-none">
      <div className="pointer-events-auto mx-auto max-w-2xl rounded-2xl border border-red-300/60 bg-red-700/95 text-white shadow-2xl backdrop-blur p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <Siren className="w-8 h-8 flex-shrink-0 animate-pulse" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-lg font-bold leading-tight">{alarm.title}</p>
            <p className="text-sm text-red-50 mt-1">{alarm.body}</p>
            {alarmCount > 1 && <p className="text-xs text-red-100 mt-1">+{alarmCount - 1} more active SOS alert{alarmCount > 2 ? 's' : ''}</p>}
            <p className="text-xs text-red-100 mt-2">If you can help safely, go. Otherwise call 995.</p>
          </div>
          <button type="button" onClick={() => setAlarms((list) => list.filter((a) => a.id !== alarm.id))} aria-label="Silence and dismiss" className="p-1 rounded-lg hover:bg-white/15"><X className="w-5 h-5" /></button>
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          <button type="button" onClick={() => showOnMap(alarm)} className="inline-flex items-center gap-2 rounded-xl bg-white text-red-800 font-semibold px-4 py-2 text-sm"><MapPin className="w-4 h-4" /> Show on map</button>
          <button type="button" onClick={() => setAlarms([])} className="inline-flex items-center gap-2 rounded-xl border border-white/50 px-4 py-2 text-sm font-medium hover:bg-white/10">Silence</button>
          {needsTap && (
            <button type="button" onClick={() => startSiren().then((ok) => setNeedsTap(!ok))} className="inline-flex items-center gap-2 rounded-xl bg-yellow-300 text-red-900 font-semibold px-4 py-2 text-sm"><Volume2 className="w-4 h-4" /> Tap to enable sound</button>
          )}
        </div>
      </div>
    </div>
  );
}
