import { useEffect, useState } from 'react';
import { AlertCircle, MapPin, Crosshair } from 'lucide-react';
import { createIncident, extractErrors, fetchNeighborhoods } from '../api';
import { CATEGORY_OPTIONS, SEVERITY_OPTIONS, fromLocalInput, getCurrentPosition, toLocalInput } from '../lib/incidents';
import { Alert, Button, FormField, Input, Modal, Select, Spinner, Textarea } from './ui';
import LazyMap from './LazyMap';

const EMPTY = () => ({
  title: '',
  description: '',
  category: '',
  severity: 'green',
  address: '',
  latitude: '',
  longitude: '',
  neighborhood: '',
  occurred_at: toLocalInput(),
});

export default function ReportIncidentModal({ isOpen, onClose, onCreated, initialPosition = null }) {
  const [formData, setFormData] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [locating, setLocating] = useState(false);
  const [neighborhoods, setNeighborhoods] = useState([]);

  // Reset each time the dialog opens; seed the pin if the caller has one.
  useEffect(() => {
    if (!isOpen) return;
    setFormData({
      ...EMPTY(),
      ...(initialPosition ? { latitude: initialPosition.lat.toFixed(6), longitude: initialPosition.lng.toFixed(6) } : {}),
    });
    setErrors({});
    setServerError(null);
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isOpen || neighborhoods.length) return;
    fetchNeighborhoods().then(setNeighborhoods).catch(() => {});
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (patch) => setFormData((f) => ({ ...f, ...patch }));

  const handleChange = (e) => {
    set({ [e.target.name]: e.target.value });
    if (errors[e.target.name]) setErrors((er) => ({ ...er, [e.target.name]: undefined }));
  };

  const lat = parseFloat(formData.latitude);
  const lng = parseFloat(formData.longitude);
  const hasPin = Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180;

  const handlePick = ({ lat: la, lng: lo }) => {
    set({ latitude: la.toFixed(6), longitude: lo.toFixed(6) });
    setErrors((er) => ({ ...er, latitude: undefined, longitude: undefined }));
  };

  const handleLocate = async () => {
    setLocating(true);
    try {
      const pos = await getCurrentPosition();
      handlePick({ lat: pos.latitude, lng: pos.longitude });
    } catch (err) {
      setServerError(err.message);
    } finally {
      setLocating(false);
    }
  };

  const handleSubmit = async (e) => {
    e?.preventDefault();
    setErrors({});
    setServerError(null);

    const local = {};
    if (!formData.title.trim()) local.title = 'Please add a short title.';
    if (!formData.description.trim()) local.description = 'Please describe what happened.';
    if (!formData.category) local.category = 'Please select a category.';
    if (!hasPin) local.latitude = 'Pick a location on the map or enter valid coordinates.';
    if (!formData.occurred_at) local.occurred_at = 'When did it happen?';
    if (Object.keys(local).length) {
      setErrors(local);
      return;
    }

    const payload = {
      title: formData.title.trim(),
      description: formData.description.trim(),
      category: formData.category,
      severity: formData.severity,
      address: formData.address.trim(),
      latitude: lat.toFixed(6),
      longitude: lng.toFixed(6),
      occurred_at: fromLocalInput(formData.occurred_at),
      ...(formData.neighborhood ? { neighborhood: formData.neighborhood } : {}),
    };

    setLoading(true);
    try {
      const incident = await createIncident(payload);
      onClose();
      onCreated?.(incident);
    } catch (err) {
      const fieldErrors = extractErrors(err.payload);
      if (Object.keys(fieldErrors).length > 0) setErrors(fieldErrors);
      else setServerError(err.payload?.detail || 'Failed to create incident. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      title="Report an incident"
      onClose={loading ? undefined : onClose}
      size="2xl"
      actions={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? <><Spinner className="w-4 h-4" /> Submitting…</> : 'Submit report'}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {serverError && <Alert variant="danger" icon={AlertCircle} message={serverError} onClose={() => setServerError(null)} />}

        <FormField label="Title" error={errors.title} required>
          <Input name="title" value={formData.title} onChange={handleChange} placeholder="Brief description" error={errors.title} maxLength={220} />
        </FormField>

        <FormField label="Description" error={errors.description} required>
          <Textarea name="description" value={formData.description} onChange={handleChange} placeholder="What happened?" rows={3} error={errors.description} />
        </FormField>

        <div className="grid sm:grid-cols-2 gap-4">
          <FormField label="Category" error={errors.category} required>
            <Select name="category" value={formData.category} onChange={handleChange} error={errors.category} options={[{ value: '', label: 'Select category…' }, ...CATEGORY_OPTIONS]} />
          </FormField>
          <FormField label="Severity" error={errors.severity}>
            <Select name="severity" value={formData.severity} onChange={handleChange} options={SEVERITY_OPTIONS} error={errors.severity} />
          </FormField>
        </div>

        <FormField label="Location" error={errors.latitude || errors.longitude} required hint="Click the map (or drag the pin) to set the exact spot.">
          <LazyMap
            height={260}
            pickMode
            picked={hasPin ? { lat, lng } : null}
            onPick={handlePick}
            autoFit={false}
            showLegend={false}
            focus={hasPin ? { lat, lng, zoom: 15, key: `${lat.toFixed(4)},${lng.toFixed(4)}` } : null}
          />
        </FormField>

        <div className="grid grid-cols-2 sm:grid-cols-[1fr_1fr_auto] gap-3 items-end">
          <FormField label="Latitude">
            <Input name="latitude" value={formData.latitude} onChange={handleChange} placeholder="-17.829" inputMode="decimal" error={errors.latitude} />
          </FormField>
          <FormField label="Longitude">
            <Input name="longitude" value={formData.longitude} onChange={handleChange} placeholder="31.053" inputMode="decimal" error={errors.longitude} />
          </FormField>
          <Button variant="outline" onClick={handleLocate} disabled={locating} className="col-span-2 sm:col-span-1">
            {locating ? <><Spinner className="w-4 h-4" /> Locating…</> : <><Crosshair className="w-4 h-4" /> Use my location</>}
          </Button>
        </div>

        <FormField label="Address" error={errors.address}>
          <div className="relative">
            <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <Input name="address" value={formData.address} onChange={handleChange} placeholder="Street address (optional)" error={errors.address} className="pl-10" />
          </div>
        </FormField>

        <div className="grid sm:grid-cols-2 gap-4">
          <FormField label="Date & time" error={errors.occurred_at} required>
            <Input name="occurred_at" type="datetime-local" value={formData.occurred_at} onChange={handleChange} max={toLocalInput()} error={errors.occurred_at} />
          </FormField>
          <FormField label="Neighbourhood" error={errors.neighborhood} hint="Shares the report with that neighbourhood.">
            <Select
              name="neighborhood"
              value={formData.neighborhood}
              onChange={handleChange}
              error={errors.neighborhood}
              options={[{ value: '', label: 'None' }, ...neighborhoods.map((n) => ({ value: n.id, label: `${n.name} — ${n.city}` }))]}
            />
          </FormField>
        </div>
        <button type="submit" className="hidden" aria-hidden="true" tabIndex={-1} />
      </form>
    </Modal>
  );
}
