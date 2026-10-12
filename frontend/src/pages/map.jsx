import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, Flame, Home, LogIn, LogOut, MapPin, Plus, RefreshCw, Siren, Users } from 'lucide-react';
import { fetchActiveSosAlerts, fetchHeatmap, fetchIncidents, fetchNearbyIncidents, fetchNeighborhoods, fetchRiskSummary, joinNeighborhood, leaveNeighborhood } from '../api';
import { SEVERITY_COLORS, SEVERITY_OPTIONS, firstError, formatDate, getCurrentPosition, hasValidCoords, severityColor } from '../lib/incidents';
import LazyMap from '../components/LazyMap';
import ReportIncidentModal from '../components/ReportIncidentModal';
import { PageHeader, PageContent } from '../components/layout';
import { Alert, Badge, Button, Card, Spinner } from '../components/ui';

const MAX_PAGES = 10;
const HEAT_DAYS = 30;

function Toggle({ active, onClick, icon: Icon, children }) {
  return (
    <Button variant={active ? 'primary' : 'secondary'} size="sm" onClick={onClick} aria-pressed={active}>
      <Icon className="w-4 h-4" /> {children}
    </Button>
  );
}

function RiskSummary({ summary }) {
  if (!summary) return null;
  const total = summary.total_incidents || 0;
  return (
    <div className="mt-3 pt-3 border-t border-white/10">
      <p className="text-xs text-slate-400 mb-2">Last {summary.days} days · <span className="text-white font-semibold">{total}</span> incident{total === 1 ? '' : 's'}</p>
      <div className="flex h-2 rounded-full overflow-hidden bg-white/10">
        {SEVERITY_OPTIONS.slice().reverse().map((s) => {
          const n = summary.by_severity?.[s.value] || 0;
          return n && total ? <span key={s.value} title={`${s.label}: ${n}`} style={{ width: `${(n / total) * 100}%`, background: SEVERITY_COLORS[s.value] }} /> : null;
        })}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-[11px] text-slate-400">
        {SEVERITY_OPTIONS.slice().reverse().map((s) => (
          <span key={s.value} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ background: SEVERITY_COLORS[s.value] }} />{s.label} {summary.by_severity?.[s.value] || 0}
          </span>
        ))}
      </div>
    </div>
  );
}

// Newest data wins when the same incident arrives from several sources.
function mergeIncidents(...lists) {
  const byId = new Map();
  lists.flat().forEach((i) => { if (i?.id) byId.set(i.id, { ...byId.get(i.id), ...i }); });
  return [...byId.values()];
}

export default function MapPage({ user }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const role = user?.role?.code;
  const canSeeSos = role === 'coordinator' || role === 'police_officer' || role === 'system_admin';

  const [incidents, setIncidents] = useState([]);
  const [neighborhoods, setNeighborhoods] = useState([]);
  const [sosAlerts, setSosAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [showHeat, setShowHeat] = useState(false);
  const [showZones, setShowZones] = useState(true);
  const [showSos, setShowSos] = useState(true);
  const [viewport, setViewport] = useState(null);
  const [heatCells, setHeatCells] = useState(null);

  const [focus, setFocus] = useState(null);
  const [selectedHood, setSelectedHood] = useState(null);
  const [risk, setRisk] = useState(null);
  const [joined, setJoined] = useState({}); // id -> boolean, learned from join/leave responses
  const [busyHood, setBusyHood] = useState(null);
  const [hoodMessage, setHoodMessage] = useState(null);

  const [reportAt, setReportAt] = useState(null); // opens the modal when set
  const [showReport, setShowReport] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const all = [];
      for (let p = 1; p <= MAX_PAGES; p += 1) {
        // eslint-disable-next-line no-await-in-loop
        const data = await fetchIncidents({ page: p });
        all.push(...data.results);
        if (!data.next) break;
      }
      // Also pull anything reported close to where this device is, even in a
      // neighbourhood the user has not joined. Optional: no location, no extras.
      const near = await getCurrentPosition({ enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 })
        .then((pos) => fetchNearbyIncidents({ latitude: pos.latitude.toFixed(6), longitude: pos.longitude.toFixed(6), radiusM: 5000 }))
        .catch(() => []);
      setIncidents(mergeIncidents(all, near));
      const [hoods, sos] = await Promise.all([
        fetchNeighborhoods().catch(() => []),
        canSeeSos ? fetchActiveSosAlerts().catch(() => []) : Promise.resolve([]),
      ]);
      setNeighborhoods(hoods);
      setSosAlerts(sos);
    } catch (err) {
      setError(err.payload?.detail || err.message || 'Failed to load map data.');
    } finally {
      setLoading(false);
    }
  }, [canSeeSos]);

  useEffect(() => { load(); }, [load]);

  // Someone close by just reported an incident: drop it on the map live.
  useEffect(() => {
    const onNearby = (event) => setIncidents((list) => mergeIncidents(list, [event.detail]));
    window.addEventListener('nhwz:incident-nearby', onNearby);
    return () => window.removeEventListener('nhwz:incident-nearby', onNearby);
  }, []);

  // Arriving from an SOS banner: centre on the alarm and mark it.
  const sosLat = Number(searchParams.get('lat'));
  const sosLng = Number(searchParams.get('lng'));
  const sosId = searchParams.get('sos');
  const alarmMarker = useMemo(
    () => (sosId && Number.isFinite(sosLat) && Number.isFinite(sosLng) && searchParams.get('lat') !== null
      ? [{ id: sosId, status: 'active', current_latitude: sosLat, current_longitude: sosLng }] : []),
    [sosId, sosLat, sosLng, searchParams],
  );
  const mapSos = useMemo(() => mergeIncidents(showSos ? sosAlerts : [], alarmMarker), [showSos, sosAlerts, alarmMarker]);
  useEffect(() => {
    if (alarmMarker.length) setFocus({ lat: sosLat, lng: sosLng, zoom: 16, key: `sos-${sosId}` });
  }, [alarmMarker, sosLat, sosLng, sosId]);

  useEffect(() => {
    if (!showHeat || !viewport) {
      if (!showHeat) setHeatCells(null);
      return undefined;
    }
    let cancelled = false;
    fetchHeatmap({ bounds: viewport.bounds, days: HEAT_DAYS })
      .then((cells) => !cancelled && setHeatCells(cells))
      .catch((err) => !cancelled && setError(firstError(err.payload?.bounds) || err.payload?.detail || 'Heatmap unavailable.'));
    return () => { cancelled = true; };
  }, [showHeat, viewport]);

  const selectHood = useCallback(async (hood) => {
    setSelectedHood(hood.id);
    setHoodMessage(null);
    setRisk(null);
    if (hasValidCoords(hood, 'centroid_latitude', 'centroid_longitude')) {
      setFocus({ lat: Number(hood.centroid_latitude), lng: Number(hood.centroid_longitude), zoom: 13, key: `hood-${hood.id}-${Date.now()}` });
    }
    try {
      setRisk(await fetchRiskSummary(hood.id, HEAT_DAYS));
    } catch { /* risk summary is optional */ }
  }, []);

  const membership = async (hood, action) => {
    setBusyHood(hood.id);
    setHoodMessage(null);
    try {
      if (action === 'join') {
        await joinNeighborhood(hood.id);
        setJoined((j) => ({ ...j, [hood.id]: true }));
        setHoodMessage({ variant: 'success', text: `You joined ${hood.name}. Its incidents are now visible to you.` });
      } else {
        await leaveNeighborhood(hood.id);
        setJoined((j) => ({ ...j, [hood.id]: false }));
        setHoodMessage({ variant: 'info', text: `You left ${hood.name}.` });
      }
      load();
    } catch (err) {
      const msg = err.payload?.detail || firstError(err.payload) || err.message;
      if (/already a member/i.test(msg)) setJoined((j) => ({ ...j, [hood.id]: true }));
      if (/not a member/i.test(msg)) setJoined((j) => ({ ...j, [hood.id]: false }));
      setHoodMessage({ variant: 'warning', text: msg });
    } finally {
      setBusyHood(null);
    }
  };

  const openHoodFromMap = useCallback((id) => {
    const hood = neighborhoods.find((n) => String(n.id) === String(id));
    if (hood) selectHood(hood);
  }, [neighborhoods, selectHood]);

  const recent = useMemo(
    () => [...incidents].filter((i) => hasValidCoords(i)).sort((a, b) => new Date(b.occurred_at) - new Date(a.occurred_at)).slice(0, 8),
    [incidents],
  );

  return (
    <>
      <PageHeader
        eyebrow="Situational awareness"
        title="Live map"
        description="Every incident you can see, neighbourhood zones, heat clusters and active emergencies in one view."
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={load} disabled={loading} aria-label="Refresh"><RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /></Button>
            <Button onClick={() => { setReportAt(null); setShowReport(true); }}><Plus className="w-4 h-4" /> Report</Button>
          </div>
        }
      />
      <PageContent>
        {error && <Alert variant="danger" icon={AlertCircle} message={String(error)} onClose={() => setError(null)} className="mb-4" />}

        <div className="flex flex-wrap gap-2 mb-4">
          <Toggle active={showHeat} onClick={() => setShowHeat((v) => !v)} icon={Flame}>Heatmap</Toggle>
          <Toggle active={showZones} onClick={() => setShowZones((v) => !v)} icon={Home}>Zones</Toggle>
          {canSeeSos && <Toggle active={showSos} onClick={() => setShowSos((v) => !v)} icon={Siren}>SOS{sosAlerts.length ? ` (${sosAlerts.length})` : ''}</Toggle>}
          {loading && <span className="flex items-center gap-2 text-sm text-slate-400 ml-2"><Spinner className="w-4 h-4" /> Loading…</span>}
        </div>

        <div className="grid lg:grid-cols-[1fr_340px] gap-5">
          <LazyMap
            height="clamp(460px, 68vh, 760px)"
            incidents={incidents}
            heatCells={showHeat ? heatCells : null}
            neighborhoods={showZones ? neighborhoods : []}
            sosAlerts={mapSos}
            focus={focus}
            onViewChange={setViewport}
            onOpenIncident={(id) => navigate(`/incidents/${id}`)}
            onOpenNeighborhood={openHoodFromMap}
          />

          <div className="space-y-5 lg:max-h-[clamp(460px,68vh,760px)] lg:overflow-y-auto lg:pr-1">
            <Card className="!p-5">
              <h2 className="text-base mb-3 flex items-center gap-2"><Users className="w-4 h-4 text-cyan-300" /> Neighbourhoods</h2>
              {hoodMessage && <Alert variant={hoodMessage.variant} message={hoodMessage.text} onClose={() => setHoodMessage(null)} className="mb-3 !p-3" />}
              {neighborhoods.length === 0 ? (
                <p className="text-sm text-slate-400">{loading ? 'Loading…' : 'No neighbourhoods have been set up yet.'}</p>
              ) : (
                <ul className="space-y-2">
                  {neighborhoods.map((n) => (
                    <li key={n.id} className={`rounded-xl border p-3 transition-colors ${selectedHood === n.id ? 'border-cyan-300/50 bg-cyan-400/10' : 'border-white/10 bg-white/[0.03]'}`}>
                      <div className="flex items-start justify-between gap-2">
                        <button type="button" onClick={() => selectHood(n)} className="text-left min-w-0">
                          <p className="font-semibold text-sm text-white truncate">{n.name}</p>
                          <p className="text-xs text-slate-400 truncate">{n.city}, {n.province}</p>
                        </button>
                        {joined[n.id] ? (
                          <Button variant="secondary" size="sm" onClick={() => membership(n, 'leave')} disabled={busyHood === n.id}>
                            {busyHood === n.id ? <Spinner className="w-3.5 h-3.5" /> : <LogOut className="w-3.5 h-3.5" />} Leave
                          </Button>
                        ) : (
                          <Button size="sm" onClick={() => membership(n, 'join')} disabled={busyHood === n.id}>
                            {busyHood === n.id ? <Spinner className="w-3.5 h-3.5" /> : <LogIn className="w-3.5 h-3.5" />} Join
                          </Button>
                        )}
                      </div>
                      {selectedHood === n.id && <RiskSummary summary={risk} />}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card className="!p-5">
              <h2 className="text-base mb-3 flex items-center gap-2"><MapPin className="w-4 h-4 text-cyan-300" /> Recent on map</h2>
              {recent.length === 0 ? (
                <p className="text-sm text-slate-400">{loading ? 'Loading…' : 'No incidents with a location yet.'}</p>
              ) : (
                <ul className="space-y-1">
                  {recent.map((i) => (
                    <li key={i.id}>
                      <button
                        type="button"
                        onClick={() => setFocus({ lat: Number(i.latitude), lng: Number(i.longitude), zoom: 16, key: `inc-${i.id}-${Date.now()}` })}
                        className="w-full text-left flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-white/10 transition-colors"
                      >
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: severityColor(i.severity), boxShadow: `0 0 8px ${severityColor(i.severity)}` }} />
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm text-white truncate">{i.title}</span>
                          <span className="block text-[11px] text-slate-400">{formatDate(i.occurred_at)} · {i.status_display}</span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <Badge variant="gray" className="mt-3">{incidents.length} total</Badge>
            </Card>
          </div>
        </div>

        <ReportIncidentModal
          isOpen={showReport}
          onClose={() => setShowReport(false)}
          initialPosition={reportAt}
          onCreated={(incident) => navigate(`/incidents/${incident.id}`)}
        />
      </PageContent>
    </>
  );
}
