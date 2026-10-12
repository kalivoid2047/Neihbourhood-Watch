import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Edit2, Check, X, Wifi, WifiOff, BadgeCheck, FileText, Navigation } from 'lucide-react';
import { fetchIncident, updateIncident, transitionIncidentStatus, verifyIncident, extractErrors, openIncidentSocket } from '../api';
import useWebSocket from '../hooks/useWebSocket';
import { CATEGORY_OPTIONS, SEVERITY_OPTIONS, STATUS_OPTIONS, fromLocalInput, isCoordinatorRole, severityColor, severityVariant, statusVariant, toLocalInput, firstError, formatDate } from '../lib/incidents';
import LazyMap from '../components/LazyMap';
import EvidenceSection from '../components/EvidenceSection';
import { PageHeader, PageContent } from '../components/layout';
import { Card, Spinner, Button, Badge, Alert, FormField, Input, Textarea, Select, Detail } from '../components/ui';

export default function IncidentDetailPage({ user }) {
  const { id } = useParams();
  const navigate = useNavigate();

  const [incident, setIncident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [editErrors, setEditErrors] = useState({});
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState(null);

  const [transitioning, setTransitioning] = useState(false);
  const [newStatus, setNewStatus] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchIncident(id);
        if (cancelled) return;
        setIncident(data);
        setNewStatus(data.status);
      } catch (err) {
        if (!cancelled) setError(err.payload?.detail || err.message || 'Failed to load incident.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [id]);

  // Live updates via WebSocket
  const wsFactory = useCallback(() => (id ? openIncidentSocket(id) : null), [id]);
  const handleWsMessage = useCallback((event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'incident_updated' && msg.incident) {
        setIncident((prev) => ({ ...prev, ...msg.incident }));
        setNewStatus(msg.incident.status);
      }
    } catch { /* ignore malformed frames */ }
  }, []);
  const { connected: wsConnected } = useWebSocket(wsFactory, handleWsMessage, { enabled: !loading && !!incident });

  const reloadIncident = useCallback(async () => {
    try {
      setIncident(await fetchIncident(id));
    } catch { /* keep showing what we have */ }
  }, [id]);

  const startEdit = () => {
    setEditData({
      title: incident.title,
      description: incident.description,
      category: incident.category,
      severity: incident.severity,
      address: incident.address || '',
      latitude: String(incident.latitude),
      longitude: String(incident.longitude),
      occurred_at: toLocalInput(incident.occurred_at),
    });
    setEditErrors({});
    setEditError(null);
    setEditing(true);
  };

  const handleEditChange = (e) => {
    setEditData({ ...editData, [e.target.name]: e.target.value });
    if (editErrors[e.target.name]) setEditErrors({ ...editErrors, [e.target.name]: undefined });
  };

  const handleEditSave = async () => {
    const la = parseFloat(editData.latitude);
    const lo = parseFloat(editData.longitude);
    if (!Number.isFinite(la) || !Number.isFinite(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180) {
      setEditErrors({ latitude: 'Enter valid coordinates or click the map.' });
      return;
    }
    setEditLoading(true);
    setEditError(null);
    try {
      const updated = await updateIncident(id, {
        ...editData,
        latitude: la.toFixed(6),
        longitude: lo.toFixed(6),
        occurred_at: fromLocalInput(editData.occurred_at),
      });
      // PATCH returns the update serializer's subset; keep server-computed fields.
      setIncident((prev) => ({ ...prev, ...updated }));
      setEditing(false);
    } catch (err) {
      const fieldErrors = extractErrors(err.payload);
      if (Object.keys(fieldErrors).length > 0) setEditErrors(fieldErrors);
      else setEditError(err.payload?.detail || 'Failed to save changes.');
    } finally {
      setEditLoading(false);
    }
  };

  const handleTransition = async () => {
    if (newStatus === incident.status) return;
    setTransitioning(true);
    setActionError(null);
    try {
      setIncident(await transitionIncidentStatus(id, newStatus));
    } catch (err) {
      setActionError(err.payload?.detail || firstError(err.payload?.new_status) || err.message || 'Transition failed.');
    } finally {
      setTransitioning(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    setActionError(null);
    try {
      const updated = await verifyIncident(id);
      setIncident(updated);
      setNewStatus(updated.status);
    } catch (err) {
      setActionError(err.payload?.detail || firstError(err.payload?.new_status) || err.message || 'Verification failed.');
    } finally {
      setVerifying(false);
    }
  };

  const isCoordinator = isCoordinatorRole(user);
  const isReporter = incident && user && String(incident.reporter) === String(user.id);
  const canEdit = isReporter && incident?.status === 'pending';

  const mapPoint = useMemo(() => {
    if (!incident) return [];
    return [incident];
  }, [incident]);

  const editLat = parseFloat(editData.latitude);
  const editLng = parseFloat(editData.longitude);
  const editPin = Number.isFinite(editLat) && Number.isFinite(editLng) ? { lat: editLat, lng: editLng } : null;

  if (loading) {
    return (
      <>
        <PageHeader title="Incident details" />
        <PageContent><Card><div className="text-center py-12"><Spinner className="w-12 h-12 mx-auto text-cyan-300" /></div></Card></PageContent>
      </>
    );
  }

  if (error || !incident) {
    return (
      <>
        <PageHeader title="Incident details" />
        <PageContent>
          <Card className="space-y-4">
            <Alert variant="danger" icon={AlertCircle} message={error || 'Incident not found.'} />
            <Button variant="secondary" onClick={() => navigate('/incidents')}><ArrowLeft className="w-4 h-4" /> Back to incidents</Button>
          </Card>
        </PageContent>
      </>
    );
  }

  const directions = `https://www.google.com/maps/dir/?api=1&destination=${incident.latitude},${incident.longitude}`;

  return (
    <>
      <PageHeader
        eyebrow={incident.category_display}
        title={incident.title}
        action={<Button variant="secondary" size="sm" onClick={() => navigate('/incidents')}><ArrowLeft className="w-4 h-4" /> Back</Button>}
      />
      <PageContent>
        <div className="space-y-6">
          {actionError && <Alert variant="danger" icon={AlertCircle} message={actionError} onClose={() => setActionError(null)} />}

          <div className="flex gap-2 flex-wrap items-center">
            <Badge variant={severityVariant(incident.severity)}>
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: severityColor(incident.severity) }} />
              {incident.severity_display}
            </Badge>
            <Badge variant={statusVariant(incident.status)}>{incident.status_display}</Badge>
            <span className={`flex items-center gap-1.5 text-xs font-medium ml-1 ${wsConnected ? 'text-emerald-300' : 'text-slate-500'}`} title={wsConnected ? 'Live updates active' : 'Not connected'}>
              {wsConnected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
              {wsConnected ? 'Live' : 'Offline'}
            </span>
          </div>

          <div className="grid lg:grid-cols-5 gap-6">
            <Card className="lg:col-span-3">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg flex items-center gap-2"><FileText className="w-5 h-5 text-cyan-300" /> Details</h2>
                {canEdit && !editing && (
                  <Button variant="outline" size="sm" onClick={startEdit}><Edit2 className="w-4 h-4" /> Edit</Button>
                )}
              </div>

              {editing ? (
                <div className="space-y-4">
                  {editError && <Alert variant="danger" icon={AlertCircle} message={editError} />}
                  <FormField label="Title" error={editErrors.title} required>
                    <Input name="title" value={editData.title} onChange={handleEditChange} error={editErrors.title} />
                  </FormField>
                  <FormField label="Description" error={editErrors.description} required>
                    <Textarea name="description" value={editData.description} onChange={handleEditChange} rows={4} error={editErrors.description} />
                  </FormField>
                  <div className="grid sm:grid-cols-2 gap-4">
                    <FormField label="Category" error={editErrors.category}>
                      <Select name="category" value={editData.category} onChange={handleEditChange} options={CATEGORY_OPTIONS} error={editErrors.category} />
                    </FormField>
                    <FormField label="Severity" error={editErrors.severity}>
                      <Select name="severity" value={editData.severity} onChange={handleEditChange} options={SEVERITY_OPTIONS} error={editErrors.severity} />
                    </FormField>
                  </div>
                  <FormField label="Address" error={editErrors.address}>
                    <Input name="address" value={editData.address} onChange={handleEditChange} error={editErrors.address} />
                  </FormField>
                  <FormField label="Location" error={editErrors.latitude || editErrors.longitude} hint="Click the map or drag the pin to move the incident.">
                    <LazyMap
                      height={220}
                      pickMode
                      picked={editPin}
                      autoFit={false}
                      showLegend={false}
                      focus={editPin ? { ...editPin, zoom: 15, key: 'edit-focus' } : null}
                      onPick={({ lat, lng }) => setEditData((d) => ({ ...d, latitude: lat.toFixed(6), longitude: lng.toFixed(6) }))}
                    />
                  </FormField>
                  <FormField label="Date & time" error={editErrors.occurred_at} required>
                    <Input name="occurred_at" type="datetime-local" value={editData.occurred_at} onChange={handleEditChange} error={editErrors.occurred_at} />
                  </FormField>
                  <div className="flex gap-3">
                    <Button onClick={handleEditSave} disabled={editLoading}>
                      {editLoading ? <><Spinner className="w-4 h-4" /> Saving…</> : <><Check className="w-4 h-4" /> Save</>}
                    </Button>
                    <Button variant="secondary" onClick={() => setEditing(false)} disabled={editLoading}><X className="w-4 h-4" /> Cancel</Button>
                  </div>
                </div>
              ) : (
                <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-5">
                  <Detail label="Description" className="sm:col-span-2"><p className="whitespace-pre-wrap">{incident.description}</p></Detail>
                  <Detail label="Reporter">{incident.reporter_name}</Detail>
                  <Detail label="Occurred">{formatDate(incident.occurred_at, true)}</Detail>
                  <Detail label="Location">{incident.address || `${Number(incident.latitude).toFixed(5)}, ${Number(incident.longitude).toFixed(5)}`}</Detail>
                  <Detail label="Reported">{formatDate(incident.created_at, true)}</Detail>
                  {incident.verified_by_name && (
                    <Detail label="Verified by">{incident.verified_by_name}{incident.verified_at && ` · ${formatDate(incident.verified_at)}`}</Detail>
                  )}
                  {incident.assigned_to_name && <Detail label="Assigned to">{incident.assigned_to_name}</Detail>}
                  <Detail label="Last updated">{formatDate(incident.updated_at, true)}</Detail>
                </dl>
              )}
            </Card>

            <div className="lg:col-span-2 space-y-3">
              <LazyMap
                height={320}
                incidents={mapPoint}
                autoFit={false}
                showLegend={false}
                focus={{ lat: Number(incident.latitude), lng: Number(incident.longitude), zoom: 15, key: `${incident.id}` }}
              />
              <a href={directions} target="_blank" rel="noopener noreferrer" className="btn btn-secondary w-full py-2.5 text-sm gap-2">
                <Navigation className="w-4 h-4" /> Get directions
              </a>
            </div>
          </div>

          {isCoordinator && !editing && (
            <Card>
              <h2 className="text-lg mb-4 flex items-center gap-2"><BadgeCheck className="w-5 h-5 text-cyan-300" /> Coordinator actions</h2>
              <div className="flex flex-wrap gap-4 items-end">
                {incident.status === 'pending' && (
                  <Button variant="success" onClick={handleVerify} disabled={verifying}>
                    {verifying ? <><Spinner className="w-4 h-4" /> Verifying…</> : 'Verify incident'}
                  </Button>
                )}
                <div className="flex gap-2 items-end">
                  <FormField label="Transition status">
                    <Select value={newStatus} onChange={(e) => setNewStatus(e.target.value)} options={STATUS_OPTIONS} className="min-w-[170px]" />
                  </FormField>
                  <Button variant="outline" onClick={handleTransition} disabled={transitioning || newStatus === incident.status} className="h-[42px]">
                    {transitioning ? <Spinner className="w-4 h-4" /> : 'Apply'}
                  </Button>
                </div>
              </div>
            </Card>
          )}

          <EvidenceSection
            incident={incident}
            user={user}
            canUpload={!!(isReporter || isCoordinator)}
            canManage={isCoordinator}
            onChanged={reloadIncident}
          />
        </div>
      </PageContent>
    </>
  );
}
