import { useState } from 'react';
import { CheckCircle, Clock, AlertCircle, XCircle } from 'lucide-react';
import { createVerificationRequest } from '../api';
import { firstError } from '../lib/incidents';
import { PageHeader, PageContent } from '../components/layout';
import { Card, Button, Textarea, FormField, Alert, Spinner, Badge } from '../components/ui';

function statusConfig(status) {
  switch (status) {
    case 'approved': return { icon: CheckCircle, variant: 'success', label: 'Verified' };
    case 'pending': return { icon: Clock, variant: 'warning', label: 'Under review' };
    case 'rejected': return { icon: XCircle, variant: 'danger', label: 'Rejected' };
    default: return { icon: AlertCircle, variant: 'gray', label: 'Unverified' };
  }
}

export default function VerificationPage({ user, onUpdate }) {
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [serverError, setServerError] = useState(null);

  const verificationStatus = user?.verification_status || 'resident';
  const cfg = statusConfig(verificationStatus);
  const StatusIcon = cfg.icon;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError(null);
    setLoading(true);
    try {
      await createVerificationRequest(notes);
      setSubmitted(true);
      onUpdate?.({ ...user, verification_status: 'pending' });
    } catch (err) {
      setServerError(err.payload?.detail || firstError(err.payload?.notes) || 'Failed to submit request. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (verificationStatus === 'approved') {
    return (
      <>
        <PageHeader eyebrow="Trust" title="Verification" description="Your account verification status." />
        <PageContent>
          <div className="max-w-2xl">
            <Card tilt>
              <div className="text-center py-8">
                <div className="mx-auto mb-5 w-20 h-20 rounded-3xl bg-emerald-400/15 border border-emerald-300/30 flex items-center justify-center" style={{ transform: 'translateZ(30px)', boxShadow: '0 12px 30px -6px rgba(52,211,153,.45)' }}>
                  <CheckCircle className="w-10 h-10 text-emerald-300" />
                </div>
                <h2 className="text-xl mb-2">Your account is verified</h2>
                <p className="text-slate-400">You have full access to all neighbourhood watch features.</p>
                <div className="mt-4"><Badge variant="success">Verified member</Badge></div>
              </div>
            </Card>
          </div>
        </PageContent>
      </>
    );
  }

  const isPending = verificationStatus === 'pending' || submitted;

  return (
    <>
      <PageHeader eyebrow="Trust" title="Request verification" description="Submit a request to become a verified member." />
      <PageContent>
        <div className="max-w-2xl">
          <Card>
            <div className="flex items-center gap-3 mb-6 pb-6 border-b border-white/10">
              <StatusIcon className="w-8 h-8 flex-shrink-0 text-slate-300" />
              <div>
                <p className="text-xs uppercase tracking-wider text-slate-500 mb-1">Current status</p>
                <Badge variant={isPending ? 'warning' : cfg.variant}>{isPending ? 'Under review' : cfg.label}</Badge>
              </div>
            </div>

            {isPending ? (
              <div className="text-center py-6">
                <Clock className="w-12 h-12 mx-auto mb-4 text-amber-300" />
                <h2 className="text-lg mb-2">Request under review</h2>
                <p className="text-slate-400">Your verification request has been submitted. A coordinator will review it shortly.</p>
              </div>
            ) : (
              <>
                {verificationStatus === 'rejected' && (
                  <Alert variant="warning" icon={AlertCircle} title="Previous request rejected" message="Your previous request was not approved. You may submit a new request below." className="mb-6" />
                )}
                {serverError && <Alert variant="danger" icon={AlertCircle} message={serverError} className="mb-6" />}

                <p className="text-slate-300 mb-6">To become a verified member of the neighbourhood watch, submit a request below. A coordinator will review your account details.</p>

                <form onSubmit={handleSubmit} className="space-y-4">
                  <FormField label="Additional notes (optional)">
                    <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Any additional information for the coordinator…" rows={3} disabled={loading} />
                  </FormField>
                  <Button type="submit" className="w-full" size="lg" disabled={loading}>
                    {loading ? <><Spinner className="w-4 h-4" /> Submitting…</> : 'Submit verification request'}
                  </Button>
                </form>
              </>
            )}
          </Card>
        </div>
      </PageContent>
    </>
  );
}
