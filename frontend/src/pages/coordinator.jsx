import { useEffect, useState, useCallback } from 'react';
import { AlertCircle, CheckCircle, XCircle, ShieldOff } from 'lucide-react';
import { fetchPendingVerificationRequests, decideVerificationRequest } from '../api';
import { PageHeader, PageContent } from '../components/layout';
import { Card, Spinner, Button, Alert, Textarea, FormField, Badge, EmptyState } from '../components/ui';

function RequestCard({ request, onDecision }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(null); // 'approve' | 'reject' | null
  const [error, setError] = useState(null);

  const decide = async (decision) => {
    setBusy(decision);
    setError(null);
    try {
      await decideVerificationRequest(request.id, decision, reason);
      onDecision(request.id);
    } catch (err) {
      setError(err.payload?.detail || 'Action failed. Please try again.');
      setBusy(null);
    }
  };

  return (
    <div className="p-6 border-b border-white/10 last:border-0">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0">
          <p className="font-semibold text-white">{request.user.full_name}</p>
          <p className="text-sm text-slate-400 break-all">{request.user.email} · {request.user.phone_number}</p>
          <p className="text-xs text-slate-500 mt-1">Submitted {new Date(request.created_at).toLocaleDateString()}</p>
        </div>
        <Badge variant="warning">Pending</Badge>
      </div>

      {request.notes && (
        <blockquote className="text-sm text-slate-300 italic bg-white/5 rounded-xl p-3 mb-4 border-l-4 border-cyan-300/50">{request.notes}</blockquote>
      )}

      {error && <Alert variant="danger" icon={AlertCircle} message={error} className="mb-4" />}

      <FormField label="Rejection reason (optional)">
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Provide a reason if rejecting…" rows={2} disabled={!!busy} />
      </FormField>

      <div className="flex gap-3 mt-3">
        <Button variant="success" onClick={() => decide('approve')} disabled={!!busy}>
          {busy === 'approve' ? <Spinner className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />} Approve
        </Button>
        <Button variant="danger" onClick={() => decide('reject')} disabled={!!busy}>
          {busy === 'reject' ? <Spinner className="w-4 h-4" /> : <XCircle className="w-4 h-4" />} Reject
        </Button>
      </div>
    </div>
  );
}

export default function CoordinatorPage({ user }) {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const roleCode = user?.role?.code;
  const canAccess = roleCode === 'coordinator' || roleCode === 'block_captain' || roleCode === 'system_admin';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPendingVerificationRequests();
      setRequests(Array.isArray(data) ? data : data.results ?? []);
    } catch (err) {
      setError(err.payload?.detail || 'Failed to load verification requests.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canAccess) load();
    else setLoading(false);
  }, [canAccess, load]);

  const header = <PageHeader eyebrow="Moderation" title="Verification queue" description="Review and approve resident verification requests." />;

  if (!canAccess) {
    return (
      <>
        {header}
        <PageContent>
          <Card><EmptyState icon={ShieldOff} title="Access denied" description="This page is for coordinators and administrators only." /></Card>
        </PageContent>
      </>
    );
  }

  return (
    <>
      {header}
      <PageContent>
        <Card className="!p-0 overflow-hidden">
          {loading ? (
            <div className="text-center py-16"><Spinner className="w-10 h-10 mx-auto text-cyan-300" /></div>
          ) : error ? (
            <div className="p-6"><Alert variant="danger" icon={AlertCircle} message={error} /></div>
          ) : requests.length === 0 ? (
            <EmptyState icon={CheckCircle} title="No pending requests" description="All verification requests have been reviewed." />
          ) : (
            <>
              <div className="px-6 py-3 border-b border-white/10 bg-white/[0.03]">
                <p className="text-sm text-slate-300 font-medium">{requests.length} pending request{requests.length !== 1 ? 's' : ''}</p>
              </div>
              {requests.map((req) => (
                <RequestCard key={req.id} request={req} onDecision={(id) => setRequests((prev) => prev.filter((r) => r.id !== id))} />
              ))}
            </>
          )}
        </Card>
      </PageContent>
    </>
  );
}
