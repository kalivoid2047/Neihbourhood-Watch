/**
 * Interactive Leaflet map for incidents, heat cells, SOS alerts and
 * neighbourhood zones.
 *
 * Leaflet owns its DOM, so the map instance is created once and every data
 * layer is synchronised from props in its own effect. (The previous version
 * rebuilt the whole map whenever the incident array changed, raced its own
 * async import against cleanup, and never loaded leaflet.css.)
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Crosshair, Layers, LocateFixed, Maximize2, Minimize2, Scan } from 'lucide-react';
import { DEFAULT_CENTER, SEVERITY_COLORS, escapeHtml, hasValidCoords, severityColor } from '../lib/incidents';

// Tiles. Default: OpenStreetMap (no API key; fine for development, not for heavy
// production traffic). Configure a provider with:
//   VITE_MAP_TILE_URL        day tiles  (or the only style)
//   VITE_MAP_TILE_URL_NIGHT  optional native dark style. When set, night mode swaps
//                            to it; otherwise night darkens the day tiles with a CSS
//                            filter (see .map-night in globals.css).
//   VITE_MAP_TILE_ATTRIBUTION  wording the provider requires
const TILE_DAY = import.meta.env.VITE_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const TILE_NIGHT = import.meta.env.VITE_MAP_TILE_URL_NIGHT || null;
const TILE_ATTRIBUTION = import.meta.env.VITE_MAP_TILE_ATTRIBUTION
  || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function pinIcon(color, pulse) {
  const html = `
    <div class="map-pin">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 34 44" width="34" height="44">
        <defs>
          <linearGradient id="g${color.slice(1)}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset=".5" stop-color="${color}"/><stop offset="1" stop-color="${color}"/>
          </linearGradient>
        </defs>
        <path d="M17 1C8.7 1 2 7.6 2 15.8 2 27 17 43 17 43s15-16 15-27.2C32 7.6 25.3 1 17 1z" fill="url(#g${color.slice(1)})" stroke="rgba(255,255,255,.9)" stroke-width="1.6"/>
        <circle cx="17" cy="16" r="6" fill="#0a1128" fill-opacity=".85"/><circle cx="17" cy="16" r="2.6" fill="#fff"/>
      </svg>
      ${pulse ? `<span class="map-pulse" style="position:absolute;left:6px;top:5px;width:22px;height:22px;color:${color};opacity:.7"><span class="ring"></span></span>` : ''}
    </div>`;
  return L.divIcon({ html, className: '', iconSize: [34, 44], iconAnchor: [17, 43], popupAnchor: [0, -40] });
}

const sosIcon = () =>
  L.divIcon({
    html: '<div class="map-pulse" style="color:#ef4444"><span class="ring"></span><span class="core"></span></div>',
    className: '', iconSize: [22, 22], iconAnchor: [11, 11], popupAnchor: [0, -12],
  });

const userIcon = () =>
  L.divIcon({
    html: '<div class="map-pulse" style="color:#22d3ee"><span class="ring"></span><span class="core"></span></div>',
    className: '', iconSize: [22, 22], iconAnchor: [11, 11],
  });

const pickIcon = () => pinIcon('#22d3ee', true);

function incidentPopup(i) {
  const color = severityColor(i.severity);
  return `
    <div class="map-popup" style="min-width:200px;max-width:260px">
      <div style="font-weight:700;font-size:14px;margin-bottom:4px">${escapeHtml(i.title)}</div>
      <div style="font-size:12px;margin-bottom:4px">
        <span style="color:${color};font-weight:700">&#9679; ${escapeHtml(i.severity_display || i.severity)}</span>
        &nbsp;&bull;&nbsp; ${escapeHtml(i.status_display || i.status)}
        ${i.category_display ? `&nbsp;&bull;&nbsp; ${escapeHtml(i.category_display)}` : ''}
      </div>
      ${i.address ? `<div style="font-size:12px;color:#a5b0d6;margin-bottom:6px">${escapeHtml(i.address)}</div>` : ''}
      <a href="#" data-incident-id="${escapeHtml(i.id)}">View details &rarr;</a>
    </div>`;
}

export default function IncidentMap({
  incidents = [],
  heatCells = null,
  sosAlerts = [],
  neighborhoods = [],
  focus = null,            // { lat, lng, zoom?, key } — fly here when `key` changes
  pickMode = false,
  picked = null,           // { lat, lng }
  onPick,                  // ({ lat, lng }) => void
  onViewChange,            // ({ bounds: [minLat, minLon, maxLat, maxLon], zoom }) => void
  onOpenIncident,          // (id) => void
  onOpenNeighborhood,      // (neighborhood) => void
  autoFit = true,
  showLegend = true,
  showControls = true,
  className = '',
  height = 420,
}) {
  const shellRef = useRef(null);
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layersRef = useRef({});
  const tileRef = useRef(null);
  const userMarkerRef = useRef(null);
  const pickedMarkerRef = useRef(null);

  // Latest callbacks, so map listeners created once never go stale.
  const cb = useRef({});
  cb.current = { onPick, onViewChange, onOpenIncident, onOpenNeighborhood, pickMode };

  const [night, setNight] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [locating, setLocating] = useState(false);
  const [notice, setNotice] = useState(null);

  const validIncidents = useMemo(() => incidents.filter((i) => hasValidCoords(i)), [incidents]);
  const idsKey = useMemo(() => validIncidents.map((i) => i.id).join('|'), [validIncidents]);

  /* Create the map once. */
  useEffect(() => {
    const map = L.map(containerRef.current, {
      zoomControl: false,
      attributionControl: true,
      worldCopyJump: true,
      minZoom: 3,
    }).setView(DEFAULT_CENTER, 12);
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    map.createPane('heat');
    const heatPane = map.getPane('heat');
    heatPane.style.zIndex = 350;
    heatPane.style.filter = 'blur(9px)';
    heatPane.style.mixBlendMode = 'screen';
    heatPane.style.pointerEvents = 'none';

    layersRef.current = {
      hoods: L.layerGroup().addTo(map),
      heat: L.layerGroup().addTo(map),
      incidents: L.layerGroup().addTo(map),
      sos: L.layerGroup().addTo(map),
    };

    map.on('click', (e) => {
      if (cb.current.pickMode) cb.current.onPick?.({ lat: e.latlng.lat, lng: e.latlng.lng });
    });
    map.on('popupopen', (e) => {
      const el = e.popup.getElement();
      const link = el?.querySelector('[data-incident-id]');
      if (link) {
        link.addEventListener('click', (ev) => {
          ev.preventDefault();
          cb.current.onOpenIncident?.(link.getAttribute('data-incident-id'));
        });
      }
      const hood = el?.querySelector('[data-hood-id]');
      if (hood) {
        hood.addEventListener('click', (ev) => {
          ev.preventDefault();
          cb.current.onOpenNeighborhood?.(hood.getAttribute('data-hood-id'));
        });
      }
    });

    let timer;
    let disposed = false;
    const emitView = () => {
      // map.remove()/stop() can fire `moveend`; never schedule work for a dead map.
      if (disposed) return;
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (disposed) return;
        const b = map.getBounds();
        cb.current.onViewChange?.({
          bounds: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()],
          zoom: map.getZoom(),
        });
      }, 350);
    };
    map.on('moveend', emitView);
    map.whenReady(emitView);

    mapRef.current = map;
    // The container may still be laying out (modals, tabs, fonts).
    const sizeTimer = setTimeout(() => map.invalidateSize(), 120);
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => map.invalidateSize()) : null;
    ro?.observe(containerRef.current);

    return () => {
      disposed = true;
      map.off('moveend', emitView);
      clearTimeout(timer);
      clearTimeout(sizeTimer);
      ro?.disconnect();
      // Cancel any in-flight flyTo/pan animation; its next frame would otherwise
      // touch the removed map pane ("_leaflet_pos" of undefined).
      map.stop();
      map.remove();
      mapRef.current = null;
      layersRef.current = {};
      tileRef.current = null;
      userMarkerRef.current = null;
      pickedMarkerRef.current = null;
    };
  }, []);

  /* Base tiles. With a native night style the layer is swapped; otherwise night is a CSS filter. */
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return undefined;
    const url = night && TILE_NIGHT ? TILE_NIGHT : TILE_DAY;
    const layer = L.tileLayer(url, { attribution: TILE_ATTRIBUTION, maxZoom: 19, crossOrigin: true }).addTo(map);
    layer.bringToBack();
    return () => { layer.remove(); };
  }, [night]);

  /* Incident markers. */
  useEffect(() => {
    const map = mapRef.current;
    const group = layersRef.current.incidents;
    if (!map || !group) return;
    group.clearLayers();
    validIncidents.forEach((i) => {
      const critical = i.severity === 'red' && i.status !== 'resolved' && i.status !== 'closed';
      L.marker([Number(i.latitude), Number(i.longitude)], {
        icon: pinIcon(severityColor(i.severity), critical),
        title: i.title,
        riseOnHover: true,
      })
        .bindPopup(incidentPopup(i))
        .addTo(group);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [validIncidents]);

  /* Fit to data when the *set* of incidents changes. */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !autoFit || validIncidents.length === 0 || focus) return;
    const bounds = L.latLngBounds(validIncidents.map((i) => [Number(i.latitude), Number(i.longitude)]));
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.25), { maxZoom: 15, animate: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsKey, autoFit]);

  /* Heat cells (server-side grid → glowing discs). */
  useEffect(() => {
    const group = layersRef.current.heat;
    if (!group) return;
    group.clearLayers();
    if (!heatCells || heatCells.length === 0) return;
    const max = Math.max(...heatCells.map((c) => c.count), 1);
    heatCells.forEach((cell) => {
      const w = cell.count / max;
      const sev = cell.severity_counts || {};
      const dominant = ['red', 'yellow', 'blue', 'green'].find((s) => sev[s]) || 'yellow';
      const color = w > 0.66 ? '#ef4444' : w > 0.33 ? '#f59e0b' : SEVERITY_COLORS[dominant];
      const center = [cell.latitude, cell.longitude];
      L.circle(center, { pane: 'heat', radius: 850, stroke: false, fillColor: color, fillOpacity: 0.16 + w * 0.14, interactive: false }).addTo(group);
      L.circle(center, { pane: 'heat', radius: 480, stroke: false, fillColor: color, fillOpacity: 0.28 + w * 0.32, interactive: false }).addTo(group);
      L.circle(center, { pane: 'heat', radius: 200, stroke: false, fillColor: '#fff', fillOpacity: 0.18 + w * 0.3, interactive: false }).addTo(group);
    });
  }, [heatCells]);

  /* Neighbourhood zones. */
  useEffect(() => {
    const group = layersRef.current.hoods;
    if (!group) return;
    group.clearLayers();
    neighborhoods.filter((n) => hasValidCoords(n, 'centroid_latitude', 'centroid_longitude')).forEach((n) => {
      const c = [Number(n.centroid_latitude), Number(n.centroid_longitude)];
      L.circle(c, {
        radius: n.alert_radius_m || 1000,
        color: '#a78bfa', weight: 1.5, dashArray: '6 8', fillColor: '#8b5cf6', fillOpacity: 0.07,
      })
        .bindPopup(
          `<div class="map-popup"><div style="font-weight:700">${escapeHtml(n.name)}</div>
           <div style="font-size:12px;color:#a5b0d6;margin:2px 0 6px">${escapeHtml(n.city)}, ${escapeHtml(n.province)}</div>
           <a href="#" data-hood-id="${escapeHtml(n.id)}">Manage membership &rarr;</a></div>`,
        )
        .addTo(group);
    });
  }, [neighborhoods]);

  /* Active SOS alerts. */
  useEffect(() => {
    const group = layersRef.current.sos;
    if (!group) return;
    group.clearLayers();
    sosAlerts.filter((a) => hasValidCoords(a, 'current_latitude', 'current_longitude')).forEach((a) => {
      L.marker([Number(a.current_latitude), Number(a.current_longitude)], { icon: sosIcon(), zIndexOffset: 1000 })
        .bindPopup(
          `<div class="map-popup"><div style="font-weight:700;color:#fca5a5">SOS &middot; ${escapeHtml(a.status)}</div>
           ${a.address ? `<div style="font-size:12px;color:#a5b0d6">${escapeHtml(a.address)}</div>` : ''}
           <div style="font-size:12px;color:#a5b0d6">Started ${escapeHtml(new Date(a.started_at).toLocaleString())}</div></div>`,
        )
        .addTo(group);
    });
  }, [sosAlerts]);

  /* Location picker marker. */
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (pickedMarkerRef.current) {
      map.removeLayer(pickedMarkerRef.current);
      pickedMarkerRef.current = null;
    }
    if (!picked || !Number.isFinite(picked.lat) || !Number.isFinite(picked.lng)) return;
    const marker = L.marker([picked.lat, picked.lng], { icon: pickIcon(), draggable: pickMode, zIndexOffset: 2000 }).addTo(map);
    marker.on('dragend', () => {
      const p = marker.getLatLng();
      cb.current.onPick?.({ lat: p.lat, lng: p.lng });
    });
    pickedMarkerRef.current = marker;
  }, [picked?.lat, picked?.lng, pickMode]); // eslint-disable-line react-hooks/exhaustive-deps

  /* Programmatic focus. */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus || !Number.isFinite(focus.lat) || !Number.isFinite(focus.lng)) return;
    map.flyTo([focus.lat, focus.lng], focus.zoom ?? 15, { duration: 0.9 });
  }, [focus?.key]); // eslint-disable-line react-hooks/exhaustive-deps

  /* Fullscreen: resize the map and allow Escape to leave. */
  useEffect(() => {
    const t = setTimeout(() => mapRef.current?.invalidateSize(), 60);
    if (!fullscreen) return () => clearTimeout(t);
    const onKey = (e) => e.key === 'Escape' && setFullscreen(false);
    document.addEventListener('keydown', onKey);
    return () => { clearTimeout(t); document.removeEventListener('keydown', onKey); };
  }, [fullscreen]);

  useEffect(() => {
    if (!notice) return undefined;
    const t = setTimeout(() => setNotice(null), 4000);
    return () => clearTimeout(t);
  }, [notice]);

  const locateMe = useCallback(() => {
    const map = mapRef.current;
    if (!navigator.geolocation) {
      setNotice('Geolocation is not supported by this browser.');
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        if (!mapRef.current) return;
        const ll = [pos.coords.latitude, pos.coords.longitude];
        if (userMarkerRef.current) userMarkerRef.current.remove();
        userMarkerRef.current = L.marker(ll, { icon: userIcon(), interactive: false, zIndexOffset: 900 }).addTo(map);
        map.flyTo(ll, Math.max(map.getZoom(), 15), { duration: 0.9 });
      },
      (err) => {
        setLocating(false);
        setNotice(err.code === 1 ? 'Location permission was denied.' : 'Could not determine your location.');
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 },
    );
  }, []);

  const fitAll = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    if (validIncidents.length === 0) {
      map.flyTo(DEFAULT_CENTER, 12);
      return;
    }
    const b = L.latLngBounds(validIncidents.map((i) => [Number(i.latitude), Number(i.longitude)]));
    map.fitBounds(b.pad(0.25), { maxZoom: 15 });
  }, [validIncidents]);

  const compact = typeof height === 'number' && height < 340; // small pickers: fewer controls
  const btn = 'w-9 h-9 rounded-xl flex items-center justify-center text-slate-100 bg-ink-800/75 border border-white/15 backdrop-blur-md hover:bg-cyan-400/25 transition-colors disabled:opacity-60';

  return (
    <div
      ref={shellRef}
      className={`map-shell ${night && !TILE_NIGHT ? 'map-night' : ''} ${pickMode ? 'map-crosshair' : ''} ${fullscreen ? 'fixed inset-0 z-[900] !rounded-none' : 'glass !p-0'} ${className}`}
      style={fullscreen ? undefined : { height }}
      data-testid="incident-map"
    >
      <div ref={containerRef} className="absolute inset-0" />

      {showControls && (
        <div className="absolute top-3 right-3 z-[500] flex flex-col gap-1.5">
          <button type="button" className={btn} onClick={() => setNight((n) => !n)} title={`Switch to ${night ? 'day' : 'night'} map`} aria-label="Switch base map">
            <Layers className="w-4 h-4" />
          </button>
          <button type="button" className={btn} onClick={locateMe} disabled={locating} title="Show my location" aria-label="Show my location">
            <LocateFixed className={`w-4 h-4 ${locating ? 'animate-pulse text-cyan-300' : ''}`} />
          </button>
          {!compact && (
            <>
              <button type="button" className={btn} onClick={fitAll} title="Fit all incidents" aria-label="Fit all incidents">
                <Scan className="w-4 h-4" />
              </button>
              <button type="button" className={btn} onClick={() => setFullscreen((f) => !f)} title={fullscreen ? 'Exit full screen' : 'Full screen'} aria-label="Toggle full screen">
                {fullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </button>
            </>
          )}
        </div>
      )}

      {pickMode && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[500] px-3.5 py-1.5 rounded-full text-xs font-semibold text-cyan-100 bg-ink-800/80 border border-cyan-300/40 backdrop-blur-md flex items-center gap-2 pointer-events-none">
          <Crosshair className="w-3.5 h-3.5" /> Click the map to set the location
        </div>
      )}

      {notice && (
        <div role="status" className="absolute bottom-3 left-1/2 -translate-x-1/2 z-[500] px-3.5 py-2 rounded-xl text-xs font-medium text-amber-100 bg-ink-800/85 border border-amber-300/40 backdrop-blur-md">
          {notice}
        </div>
      )}

      {showLegend && (
        <div className="absolute bottom-3 left-3 z-[500] px-3 py-2 rounded-xl bg-ink-800/75 border border-white/15 backdrop-blur-md text-[11px] text-slate-200 space-y-1">
          {[['red', 'Critical'], ['yellow', 'Important'], ['blue', 'Average'], ['green', 'Normal']].map(([k, label]) => (
            <div key={k} className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: SEVERITY_COLORS[k], boxShadow: `0 0 8px ${SEVERITY_COLORS[k]}` }} />
              {label}
            </div>
          ))}
        </div>
      )}

      {!pickMode && (
        <div className="absolute top-3 left-3 z-[500] px-3 py-1.5 rounded-full text-xs font-semibold text-slate-100 bg-ink-800/75 border border-white/15 backdrop-blur-md pointer-events-none">
          {validIncidents.length} incident{validIncidents.length === 1 ? '' : 's'} on map
        </div>
      )}
    </div>
  );
}
