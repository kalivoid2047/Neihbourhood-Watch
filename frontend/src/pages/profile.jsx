import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Edit2, Check, X, AlertCircle, BadgeCheck, Shield } from 'lucide-react';
import { updateProfile, applyForBlockCaptain, extractErrors } from '../api';
import { PageHeader, PageContent } from '../components/layout';
import { Card, Badge, Button, FormField, Input, Alert, Spinner, Detail, Tilt } from '../components/ui';

function statusVariant(status) {
  if (status === 'approved') return 'success';
  if (status === 'rejected') return 'danger';
  return 'warning';
}

const initials = (name = '') => name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('') || '?';

export default function ProfilePage({ user, onUpdate }) {
  const seed = () => ({ full_name: user.full_name || '', phone_number: user.phone_number || '', address: user.address || '' });
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState(seed);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState(null);
  const isResident = (user.role?.code || 'resident') === 'resident';

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    if (errors[e.target.name]) setErrors({ ...errors, [e.target.name]: undefined });
  };

  const handleSave = async () => {
    setErrors({});
    setServerError(null);
    setLoading(true);
    try {
      onUpdate(await updateProfile(formData));
      setEditing(false);
    } catch (err) {
      const fieldErrors = extractErrors(err.payload);
      if (Object.keys(fieldErrors).length > 0) setErrors(fieldErrors);
      else setServerError(err.payload?.detail || 'Failed to save changes.');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    setApplyError(null);
    setApplying(true);
    try {
      onUpdate(await applyForBlockCaptain());
    } catch (err) {
      setApplyError(err.payload?.detail || 'Could not submit your application. Please try again.');
    } finally {
      setApplying(false);
    }
  };

  const handleCancel = () => {
    setFormData(seed());
    setErrors({});
    setServerError(null);
    setEditing(false);
  };

  return (
    <>
      <PageHeader eyebrow="Account" title="Your profile" description="Manage your account and verification status." />
      <PageContent>
        <div className="grid lg:grid-cols-[320px_1fr] gap-6 max-w-5xl">
          <Tilt max={6} className="glass glass-strong p-8 text-center self-start">
            <div
              className="mx-auto w-24 h-24 rounded-3xl bg-gradient-to-br from-cyan-300 via-cyan-500 to-violet-500 flex items-center justify-center text-3xl font-extrabold font-display text-ink-950"
              style={{ transform: 'translateZ(40px)', boxShadow: '0 8px 0 #0e7490, 0 24px 40px -8px rgba(34,211,238,.55), inset 0 1px 0 rgba(255,255,255,.6)' }}
            >
              {initials(user.full_name)}
            </div>
            <h2 className="mt-7 text-xl break-words" style={{ transform: 'translateZ(20px)' }}>{user.full_name}</h2>
            <p className="text-sm text-slate-400 break-all">{user.email}</p>
            <div className="mt-4 flex justify-center gap-2 flex-wrap">
              <Badge variant="accent">{user.role?.name || user.role?.code || 'Resident'}</Badge>
              <Badge variant={statusVariant(user.verification_status)}>{user.verification_status}</Badge>
            </div>
            {user.verification_status !== 'approved' && (
              <Link to="/verify" className="btn btn-outline mt-6 w-full py-2.5 text-sm gap-2"><BadgeCheck className="w-4 h-4" /> Get verified</Link>
            )}
          </Tilt>

          <Card>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg">Account details</h2>
              {!editing && <Button variant="outline" size="sm" onClick={() => setEditing(true)}><Edit2 className="w-4 h-4" /> Edit profile</Button>}
            </div>

            {serverError && <Alert variant="danger" icon={AlertCircle} message={serverError} className="mb-6" />}

            {editing ? (
              <div className="space-y-4">
                <FormField label="Full name" error={errors.full_name} required>
                  <Input name="full_name" value={formData.full_name} onChange={handleChange} error={errors.full_name} disabled={loading} required />
                </FormField>
                <FormField label="Phone number" error={errors.phone_number}>
                  <Input name="phone_number" value={formData.phone_number} onChange={handleChange} error={errors.phone_number} placeholder="+263771234567" disabled={loading} />
                </FormField>
                <FormField label="Address" error={errors.address}>
                  <Input name="address" value={formData.address} onChange={handleChange} error={errors.address} placeholder="Street address" disabled={loading} />
                </FormField>
                <div className="flex gap-3 pt-2">
                  <Button onClick={handleSave} disabled={loading}>
                    {loading ? <><Spinner className="w-4 h-4" /> Saving…</> : <><Check className="w-4 h-4" /> Save changes</>}
                  </Button>
                  <Button variant="secondary" onClick={handleCancel} disabled={loading}><X className="w-4 h-4" /> Cancel</Button>
                </div>
              </div>
            ) : (
              <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-6">
                <Detail label="Full name">{user.full_name}</Detail>
                <Detail label="Email">{user.email}</Detail>
                <Detail label="Phone number">{user.phone_number || '—'}</Detail>
                <Detail label="Address">{user.address || '—'}</Detail>
                <Detail label="Role">{user.role?.name || user.role?.code || '—'}</Detail>
                <Detail label="Verification"><Badge variant={statusVariant(user.verification_status)}>{user.verification_status}</Badge></Detail>
              </dl>
            )}
          </Card>

          {isResident && (
            <Card className="lg:col-start-2">
              <h2 className="text-lg flex items-center gap-2"><Shield className="w-5 h-5" /> Become a block captain</h2>
              <p className="text-sm text-slate-400 mt-2">
                Block captains help look after their neighbourhood. Apply and an administrator will review your account.
              </p>
              {applyError && <Alert variant="danger" icon={AlertCircle} message={applyError} className="mt-4" />}
              {user.block_captain_applied_at ? (
                <p className="mt-4"><Badge variant="warning">Application pending review</Badge></p>
              ) : (
                <Button className="mt-4" onClick={handleApply} disabled={applying}>
                  {applying ? <><Spinner className="w-4 h-4" /> Submitting…</> : 'Apply to be a block captain'}
                </Button>
              )}
            </Card>
          )}
        </div>
      </PageContent>
    </>
  );
}
