import { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, AlertCircle, MapPin, Clock, Map as MapIcon, List, Search, Flame, LocateFixed, ChevronRight, X } from 'lucide-react';
import { fetchIncidents, fetchHeatmap, fetchNearbyIncidents } from '../api';
import { CATEGORY_OPTIONS, SEVERITY_OPTIONS, STATUS_OPTIONS, formatDate, getCurrentPosition, severityColor, severityVariant, statusVariant } from '../lib/incidents';
import LazyMap from '../components/LazyMap';
import ReportIncidentModal from '../components/ReportIncidentModal';
import { PageHeader, PageContent } from '../components/layout';
import { Card, Spinner, Button, Badge, Alert, EmptyState, Select, Input } from '../components/ui';

const MAX_MAP_PAGES = 10; // 10 × 50 = 500 incidents on the map

const RADIUS_OPTIONS = [
  { value: 1000, label: '1 km' },
  { value: 2000, label: '2 km' },
  { value: 5000, label: '5 km' },
  { value: 10000, label: '10 km' },
];

function IncidentRow({ incident, distance, onClick }) {
  return (
    <button
      type="button"
      onClick={() => onClick(incident.id)}
      className="group w-full text-left px-5 py-4 hover:bg-white/[0.06] transition-colors border-b border-white/10 last:border-0 flex items-center gap-4"
    >
      <span className="w-1.5 self-stretch rounded-full flex-shrink-0" style={{ background: severityColor(incident.severity), boxShadow: `0 0 12px ${severityColor(incident.severity)}` }} />
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-white truncate">{incident.title}</p>
        <div className="flex items-center gap-x-3 gap-y-1 mt-1 text-xs text-slate-400 flex-wrap">
          <span>{incident.category_display}</span>
          {incident.address && (
            <span className="flex items-center gap-1 min-w-0"><MapPin className="w-3 h-3 flex-shrink-0" /><span className="truncate max-w-[220px]">{incident.address}</span></span>
          )}
          <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatDate(incident.occurred_at)}</span>
          {distance != null && <span className="text-cyan-300 font-medium">{distance >= 1000 ? `${(distance / 1000).toFixed(1)} km` : `${Math.round(distance)} m`} away</span>}
        </div>
      </div>
      <div className="hidden sm:flex gap-2 flex-shrink-0">
        <Badge variant={severityVariant(incident.severity)}>{incident.severity_display}</Badge>
        <Badge variant={statusVariant(incident.status)}>{incident.status_display}</Badge>
      </div>
      <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-300 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
    </button>
  );
}

export default function IncidentsPage() {
  const navigate = useNavigate();
  const [incidents, setIncidents] = useState([]);
  const [pagination, setPagination] = useState({ count: 0, next: null, previous: null });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [view, setView] = useState('list'); // 'list' | 'map'

  // Filters (applied client-side to whatever is loaded)
  const [query, setQuery] = useState('');
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const [category, setCategory] = useState('');

  // Map-only state
  const [mapIncidents, setMapIncidents] = useState(null); // null = not loaded
  const [mapLoading, setMapLoading] = useState(false);
  const [showHeat, setShowHeat] = useState(false);
  const [heatCells, setHeatCells] = useState(null);
  const [viewport, setViewport] = useState(null);
  const [nearby, setNearby] = useState(null); // { latitude, longitude, radiusM, distances }
  const [radiusM, setRadiusM] = useState(2000);
  const [nearbyLoading, setNearbyLoading] = useState(false);
  const [mapNotice, setMapNotice] = useState(null);
  const [focus, setFocus] = useState(null);

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchIncidents({ page: p });
      setIncidents(data.results);
      setPagination({ count: data.count, next: data.next, previous: data.previous });
    } catch (err) {
      setError(err.payload?.detail || err.message || 'Failed to load incidents.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(page); }, [load, page]);

  // The map should show every incident, not just the current list page.
  const loadMapIncidents = useCallback(async () => {
    setMapLoading(true);
    try {
      const all = [];
      for (let p = 1; p <= MAX_MAP_PAGES; p += 1) {
        // eslint-disable-next-line no-await-in-loop
        const data = await fetchIncidents({ page: p });
        all.push(...data.results);
        if (!data.next) break;
      }
      setMapIncidents(all);
    } catch (err) {
      setMapNotice(err.payload?.detail || err.message || 'Could not load map data.');
    } finally {
      setMapLoading(false);
    }
  }, []);

  useEffect(() => {
    if (view === 'map' && mapIncidents === null && !mapLoading) loadMapIncidents();
  }, [view, mapIncidents, mapLoading, loadMapIncidents]);

  // Heat cells follow the viewport while enabled.
  useEffect(() => {
    if (!showHeat || !viewport) {
      if (!showHeat) setHeatCells(null);
      return undefined;
    }
    let cancelled = false;
    fetchHeatmap({ bounds: viewport.bounds, days: 30 })
      .then((cells) => !cancelled && setHeatCells(cells))
      .catch((err) => { if (!cancelled) setMapNotice(err.payload?.detail || err.payload?.bounds || 'Heatmap unavailable.'); });
    return () => { cancelled = true; };
  }, [showHeat, viewport]);

  const applyFilters = useCallback((list) => {
    const q = query.trim().toLowerCase();
    return list.filter((i) =>
      (!severity || i.severity === severity) &&
      (!status || i.status === status) &&
      (!category || i.category === category) &&
      (!q || `${i.title} ${i.address || ''} ${i.category_display || ''}`.toLowerCase().includes(q)),
    );
  }, [query, severity, status, category]);

  const filteredList = useMemo(() => applyFilters(incidents), [applyFilters, incidents]);

  const mapSource = nearby ? nearby.items : mapIncidents || [];
  const filteredMap = useMemo(() => applyFilters(mapSource), [applyFilters, mapSource]);

  const toggleNearby = async () => {
    if (nearby) {
      setNearby(null);
      return;
    }
    setNearbyLoading(true);
    setMapNotice(null);
    try {
      const pos = await getCurrentPosition();
      const items = await fetchNearbyIncidents({ latitude: pos.latitude.toFixed(6), longitude: pos.longitude.toFixed(6), radiusM });
      setNearby({ latitude: pos.latitude, longitude: pos.longitude, radiusM, items: Array.isArray(items) ? items : items.results ?? [] });
      setFocus({ lat: pos.latitude, lng: pos.longitude, zoom: radiusM > 5000 ? 12 : 14, key: `near-${Date.now()}` });
    } catch (err) {
      setMapNotice(err.payload?.detail || err.message);
    } finally {
      setNearbyLoading(false);
    }
  };

  // Re-run the nearby search when the radius changes while active.
  const changeRadius = async (value) => {
    const r = Number(value);
    setRadiusM(r);
    if (!nearby) return;
    setNearbyLoading(true);
    try {
      const items = await fetchNearbyIncidents({ latitude: nearby.latitude.toFixed(6), longitude: nearby.longitude.toFixed(6), radiusM: r });
      setNearby({ ...nearby, radiusM: r, items: Array.isArray(items) ? items : items.results ?? [] });
    } catch (err) {
      setMapNotice(err.payload?.detail || err.message);
    } finally {
      setNearbyLoading(false);
    }
  };

  const filtersActive = query || severity || status || category;
  const clearFilters = () => { setQuery(''); setSeverity(''); setStatus(''); setCategory(''); };

  const distances = nearby ? Object.fromEntries(nearby.items.map((i) => [i.id, i.distance_m])) : null;

  return (
    <>
      <PageHeader
        eyebrow="Community reports"
        title="Incidents"
        description="View, filter and report incidents in your neighbourhood."
        action={<Button onClick={() => setShowCreate(true)}><Plus className="w-4 h-4" /> Report incident</Button>}
      />
      <PageContent>
        {/* Toolbar */}
        <div className="glass !rounded-2xl p-3 mb-5 flex flex-col lg:flex-row gap-3 lg:items-center">
          <div className="flex rounded-xl overflow-hidden border border-white/15 bg-ink-900/50 flex-shrink-0" role="tablist" aria-label="View">
            {[['list', List, 'List'], ['map', MapIcon, 'Map']].map(([key, Icon, label]) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={view === key}
                onClick={() => setView(key)}
                className={`px-4 py-2 text-sm font-semibold flex items-center gap-2 transition-all ${view === key ? 'bg-gradient-to-b from-cyan-300 to-cyan-500 text-ink-950' : 'text-slate-300 hover:bg-white/10'}`}
              >
                <Icon className="w-4 h-4" /> {label}
              </button>
            ))}
          </div>

          <div className="relative flex-1 min-w-0">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search title or address…" className="pl-10 !py-2" aria-label="Search incidents" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 lg:w-[480px]">
            <Select value={severity} onChange={(e) => setSeverity(e.target.value)} className="!py-2" aria-label="Severity" options={[{ value: '', label: 'Any severity' }, ...SEVERITY_OPTIONS]} />
            <Select value={status} onChange={(e) => setStatus(e.target.value)} className="!py-2" aria-label="Status" options={[{ value: '', label: 'Any status' }, ...STATUS_OPTIONS]} />
            <Select value={category} onChange={(e) => setCategory(e.target.value)} className="!py-2" aria-label="Category" options={[{ value: '', label: 'Any category' }, ...CATEGORY_OPTIONS]} />
          </div>
          {filtersActive && (
            <Button variant="ghost" size="sm" onClick={clearFilters}><X className="w-4 h-4" /> Clear</Button>
          )}
        </div>

        {view === 'map' && (
          <div className="mb-5 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button variant={showHeat ? 'primary' : 'secondary'} size="sm" onClick={() => setShowHeat((h) => !h)} aria-pressed={showHeat}>
                <Flame className="w-4 h-4" /> Heatmap
              </Button>
              <Button variant={nearby ? 'primary' : 'secondary'} size="sm" onClick={toggleNearby} disabled={nearbyLoading} aria-pressed={!!nearby}>
                {nearbyLoading ? <Spinner className="w-4 h-4" /> : <LocateFixed className="w-4 h-4" />} Near me
              </Button>
              <Select value={radiusM} onChange={(e) => changeRadius(e.target.value)} options={RADIUS_OPTIONS} className="!py-1.5 !w-auto text-sm" aria-label="Search radius" />
              {mapLoading && <span className="flex items-center gap-2 text-sm text-slate-400"><Spinner className="w-4 h-4" /> Loading incidents…</span>}
              {nearby && <span className="text-sm text-cyan-300">{nearby.items.length} within {nearby.radiusM / 1000} km of you</span>}
            </div>
            {mapNotice && <Alert variant="warning" icon={AlertCircle} message={String(mapNotice)} onClose={() => setMapNotice(null)} />}
            <LazyMap
              height={520}
              incidents={filteredMap}
              heatCells={showHeat ? heatCells : null}
              focus={focus}
              autoFit={!nearby}
              onViewChange={setViewport}
              onOpenIncident={(id) => navigate(`/incidents/${id}`)}
            />
          </div>
        )}

        <Card className="!p-0 overflow-hidden">
          {loading ? (
            <div className="text-center py-16"><Spinner className="w-10 h-10 mx-auto text-cyan-300" /></div>
          ) : error ? (
            <div className="p-6"><Alert variant="danger" icon={AlertCircle} message={error} /></div>
          ) : incidents.length === 0 ? (
            <EmptyState
              icon={AlertCircle}
              title="No incidents reported yet"
              description="Be the first to report something in your neighbourhood."
              action={<Button onClick={() => setShowCreate(true)}><Plus className="w-4 h-4" /> Report the first incident</Button>}
            />
          ) : filteredList.length === 0 ? (
            <EmptyState icon={Search} title="No matches" description="Nothing on this page matches your filters." action={<Button variant="secondary" onClick={clearFilters}>Clear filters</Button>} />
          ) : (
            <>
              {(nearby && view === 'map' ? [...filteredList].sort((a, b) => (distances[a.id] ?? Infinity) - (distances[b.id] ?? Infinity)) : filteredList).map((incident) => (
                <IncidentRow key={incident.id} incident={incident} distance={view === 'map' && distances ? distances[incident.id] : null} onClick={(id) => navigate(`/incidents/${id}`)} />
              ))}

              {(pagination.next || pagination.previous) && (
                <div className="flex items-center justify-between p-4 border-t border-white/10">
                  <Button variant="secondary" size="sm" disabled={!pagination.previous} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                  <span className="text-sm text-slate-400">Page {page} · {pagination.count} total</span>
                  <Button variant="secondary" size="sm" disabled={!pagination.next} onClick={() => setPage((p) => p + 1)}>Next</Button>
                </div>
              )}
            </>
          )}
        </Card>

        <ReportIncidentModal
          isOpen={showCreate}
          onClose={() => setShowCreate(false)}
          onCreated={(incident) => navigate(`/incidents/${incident.id}`)}
        />
      </PageContent>
    </>
  );
}
