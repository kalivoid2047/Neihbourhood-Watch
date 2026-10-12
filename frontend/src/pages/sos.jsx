import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Clock, MapPin, Phone, Siren, X } from 'lucide-react';
import { cancelSosAlert, createSosAlert, fetchActiveSosAlerts, fetchSosAlerts, pingSosAlert, resolveSosAlert } from '../api';
import { formatDate, getCurrentPosition } from '../lib/incidents';
import LazyMap from '../components/LazyMap';
import { PageHeader, PageContent } from '../components/layout';
import { Alert, Badge, Button, Card, Spinner } from '../components/ui';

const COUNTDOWN_SECONDS = 3;
const PING_EVERY_MS = 20000;
const isLive = (a) => a && (a.status === 'active' || a.status === 'escalated');

export default function SosPage({ user }) {
  const role = user?.role?.code;
  const isResponder = role === 'coordinator' || role === 'police_officer' || role === 'system_admin';

  const [alerts, setAlerts] = useState([]);
  const [responderAlerts, setResponderAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [countdown, setCountdown] = useState(null); // null | seconds remaining
  const [lastPing, setLastPing] = useState(null);
  const pingFailures = useRef(0);

  const activeAlert = useMemo(() => alerts.find(isLive) || null, [alerts]);
  const history = useMemo(() => alerts.filter((a) => !isLive(a)).slice(0, 5), [alerts]);

  const load = useCallback(async () => {
    try {
      const mine = (await fetchSosAlerts()).filter((a) => String(a.user) === String(user.id));
      setAlerts(mine);
      if (isResponder) setResponderAlerts(await fetchActiveSosAlerts());
      setError(null);
    } catch (err) {
      setError(err.payload?.detail || err.message || 'Could not load SOS alerts.');
    } finally {
      setLoading(false);
    }
  }, [isResponder, user.id]);

  useEffect(() => { load(); }, [load]);

  const send = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const pos = await getCurrentPosition();
      const alert = await createSosAlert({ latitude: pos.latitude.toFixed(6), longitude: pos.longitude.toFixed(6) });
      setAlerts((a) => [alert, ...a]);
      setInfo('SOS sent. Your emergency contacts and coordinators have been notified. If you are in immediate danger, call 995.');
    } catch (err) {
      setError(err.payload?.detail || err.payload?.current_latitude || err.message || 'Could not send SOS.');
    } finally {
      setBusy(false);
    }
  }, []);

  // Countdown gives a few seconds to back out of an accidental press.
  useEffect(() => {
    if (countdown === null) return undefined;
    if (countdown <= 0) {
      setCountdown(null);
      send();
      return undefined;
    }
    const t = setTimeout(() => setCountdown((c) => (c === null ? null : c - 1)), 1000);
    return () => clearTimeout(t);
  }, [countdown, send]);

  // While an alert is live, keep sharing the position.
  useEffect(() => {
    if (!activeAlert) return undefined;
    let cancelled = false;
    const ping = async () => {
      try {
        const pos = await getCurrentPosition();
        const saved = await pingSosAlert(activeAlert.id, { latitude: pos.latitude.toFixed(6), longitude: pos.longitude.toFixed(6), accuracy: pos.accuracy });
        if (cancelled) return;
        pingFailures.current = 0;
        setLastPing(new Date());
        setAlerts((list) => list.map((a) => (a.id === activeAlert.id ? { ...a, current_latitude: saved.latitude, current_longitude: saved.longitude } : a)));
      } catch (err) {
        pingFailures.current += 1;
        if (!cancelled && pingFailures.current === 3) setError(`Live location updates are failing: ${err.payload?.detail || err.message}`);
      }
    };
    ping();
    const timer = setInterval(ping, PING_EVERY_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, [activeAlert?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const finish = async (kind) => {
    if (!activeAlert) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await (kind === 'resolve' ? resolveSosAlert(activeAlert.id) : cancelSosAlert(activeAlert.id));
      setAlerts((list) => list.map((a) => (a.id === updated.id ? { ...a, ...updated } : a)));
      setInfo(kind === 'resolve' ? 'Glad you are safe. The alert has been resolved.' : 'The alert was cancelled.');
      if (isResponder) setResponderAlerts(await fetchActiveSosAlerts().catch(() => []));
    } catch (err) {
      setError(err.payload?.detail || err.message || 'Could not update the alert.');
    } finally {
      setBusy(false);
    }
  };

  const mapAlerts = isResponder ? responderAlerts : activeAlert ? [activeAlert] : [];
  const focusPoint = activeAlert && Number.isFinite(Number(activeAlert.current_latitude))
    ? { lat: Number(activeAlert.current_latitude), lng: Number(activeAlert.current_longitude), zoom: 16, key: `sos-${activeAlert.id}` }
    : null;

  return (
    <>
      <PageHeader eyebrow="Emergency" title="SOS" description="Share your live location with your emergency contacts and neighbourhood coordinators." />
      <PageContent>
        {error && <Alert variant="danger" icon={AlertCircle} message={String(error)} onClose={() => setError(null)} className="mb-5" />}
        {info && <Alert variant="success" icon={CheckCircle2} message={info} onClose={() => setInfo(null)} className="mb-5" />}

        <div className="grid lg:grid-cols-2 gap-6">
          <Card strong className="flex flex-col items-center text-center !py-10 overflow-hidden relative">
            <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-[460px] h-[300px] rounded-full bg-red-500/20 blur-3xl pointer-events-none" aria-hidden="true" />
            {loading ? (
              <Spinner className="w-10 h-10 text-cyan-300 my-24" />
            ) : activeAlert ? (
              <>
                <Badge variant="danger" className="relative mb-4"><span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" /> SOS {activeAlert.status}</Badge>
                <div className="relative w-40 h-40 my-4">
                  <span className="sos-halo" />
                  <span className="sos-halo" style={{ animationDelay: '-1s' }} />
                  <div className="relative w-full h-full rounded-full flex items-center justify-center bg-gradient-to-b from-red-400 to-red-700 border border-white/30" style={{ boxShadow: '0 10px 0 #7f1d1d, 0 24px 46px -8px rgba(239,68,68,.6)' }}>
                    <Siren className="w-16 h-16 text-white" />
                  </div>
                </div>
                <h2 className="relative text-2xl mb-1">Help is being alerted</h2>
                <p className="relative text-sm text-slate-300 max-w-sm mb-2">Your location is shared every {PING_EVERY_MS / 1000} seconds while this alert is open.</p>
                <p className="relative text-xs text-slate-400 mb-6 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" /> Started {formatDate(activeAlert.started_at, true)}
                  {lastPing && <> · last update {lastPing.toLocaleTimeString()}</>}
                </p>
                <div className="relative flex flex-wrap gap-3 justify-center">
                  <Button variant="success" size="lg" onClick={() => finish('resolve')} disabled={busy}><CheckCircle2 className="w-5 h-5" /> I&apos;m safe</Button>
                  <Button variant="secondary" size="lg" onClick={() => finish('cancel')} disabled={busy}>Cancel alert</Button>
                </div>
              </>
            ) : countdown !== null ? (
              <>
                <p className="relative text-sm font-semibold uppercase tracking-widest text-red-300 mb-4">Sending SOS in</p>
                <div className="relative w-44 h-44 rounded-full flex items-center justify-center text-7xl font-extrabold font-display text-white bg-red-600/30 border-2 border-red-400" style={{ boxShadow: '0 0 60px rgba(239,68,68,.5)' }} aria-live="assertive">
                  {countdown}
                </div>
                <Button variant="secondary" size="lg" className="relative mt-8" onClick={() => setCountdown(null)}><X className="w-5 h-5" /> Cancel</Button>
              </>
            ) : (
              <>
                <div className="relative my-6">
                  <span className="sos-halo" />
                  <button type="button" className="sos-btn" onClick={() => { setInfo(null); setCountdown(COUNTDOWN_SECONDS); }} disabled={busy} aria-label="Send SOS alert">
                    {busy ? <Spinner className="w-12 h-12 mx-auto" /> : 'SOS'}
                  </button>
                </div>
                <p className="relative text-slate-300 max-w-sm mt-6 mb-1">Press to alert your emergency contacts and coordinators. You&apos;ll have {COUNTDOWN_SECONDS} seconds to cancel.</p>
                <p className="relative text-xs text-slate-400 flex items-center gap-1.5"><MapPin className="w-3.5 h-3.5" /> Your browser will ask to share your location.</p>
              </>
            )}
          </Card>

          <div className="space-y-6">
            <LazyMap
              height={340}
              sosAlerts={mapAlerts}
              focus={focusPoint}
              autoFit={false}
              showLegend={false}
            />

            <Card className="!p-5">
              <h2 className="text-base mb-3 flex items-center gap-2"><Phone className="w-4 h-4 text-red-300" /> Emergency numbers</h2>
              <ul className="text-sm text-slate-300 space-y-1.5">
                <li className="flex justify-between"><span>Police (ZRP)</span><strong className="text-white">995</strong></li>
                <li className="flex justify-between"><span>Ambulance</span><strong className="text-white">994</strong></li>
                <li className="flex justify-between"><span>Fire</span><strong className="text-white">993</strong></li>
              </ul>
            </Card>

            {isResponder && (
              <Card className="!p-5">
                <h2 className="text-base mb-3">Active alerts ({responderAlerts.length})</h2>
                {responderAlerts.length === 0 ? (
                  <p className="text-sm text-slate-400">No active alerts right now.</p>
                ) : (
                  <ul className="space-y-2">
                    {responderAlerts.map((a) => (
                      <li key={a.id} className="rounded-xl bg-red-400/10 border border-red-300/20 px-3 py-2 text-sm">
                        <p className="font-semibold text-red-100">{Number(a.current_latitude).toFixed(4)}, {Number(a.current_longitude).toFixed(4)}</p>
                        <p className="text-xs text-slate-400">{a.address || 'No address'} · started {formatDate(a.started_at, true)}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            )}

            {history.length > 0 && (
              <Card className="!p-5">
                <h2 className="text-base mb-3">Your recent alerts</h2>
                <ul className="space-y-2">
                  {history.map((a) => (
                    <li key={a.id} className="flex items-center justify-between text-sm">
                      <span className="text-slate-300">{formatDate(a.started_at, true)}</span>
                      <Badge variant={a.status === 'resolved' ? 'success' : 'gray'}>{a.status}</Badge>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        </div>
      </PageContent>
    </>
  );
}
