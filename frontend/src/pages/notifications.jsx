import { useCallback, useEffect, useState } from 'react';
import { Bell, Check, Trash2, AlertCircle } from 'lucide-react';
import { fetchNotifications, markNotificationRead, deleteNotification } from '../api';
import { PageHeader, PageContent } from '../components/layout';
import { Card, Spinner, Button, Badge, Alert, EmptyState } from '../components/ui';

const isUnread = (n) => n.status === 'queued' || n.status === 'sent';
const priorityVariant = (p) => ({ critical: 'danger', high: 'warning', normal: 'primary', low: 'gray' }[p] || 'gray');

function NotificationItem({ notification, onRead, onDelete }) {
  const unread = isUnread(notification);
  return (
    <div className={`px-5 py-4 border-b border-white/10 last:border-0 flex items-start gap-4 ${unread ? 'bg-cyan-400/[0.07]' : ''}`}>
      <span className={`mt-2 w-2 h-2 rounded-full flex-shrink-0 ${unread ? 'bg-cyan-300 shadow-[0_0_10px_#22d3ee]' : 'bg-transparent'}`} aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <p className={`text-white truncate ${unread ? 'font-semibold' : 'font-medium'}`}>{notification.title}</p>
          <Badge variant={priorityVariant(notification.priority)}>{notification.priority}</Badge>
        </div>
        <p className="text-sm text-slate-300 line-clamp-2">{notification.body}</p>
        <p className="text-xs text-slate-500 mt-1">{new Date(notification.created_at).toLocaleString()}</p>
      </div>
      <div className="flex gap-2 flex-shrink-0">
        {unread && (
          <Button variant="outline" size="sm" onClick={() => onRead(notification.id)} title="Mark as read" aria-label="Mark as read"><Check className="w-4 h-4" /></Button>
        )}
        <Button variant="secondary" size="sm" onClick={() => onDelete(notification.id)} title="Delete" aria-label="Delete notification"><Trash2 className="w-4 h-4 text-red-300" /></Button>
      </div>
    </div>
  );
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchNotifications();
      setNotifications(data.results || data);
    } catch (err) {
      setError(err.payload?.detail || 'Failed to load notifications.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRead = async (id) => {
    setActionError(null);
    try {
      const updated = await markNotificationRead(id);
      setNotifications((ns) => ns.map((n) => (n.id === id ? { ...n, ...updated } : n)));
    } catch (err) {
      setActionError(err.payload?.detail || 'Could not mark as read.');
    }
  };

  const handleDelete = async (id) => {
    setActionError(null);
    try {
      await deleteNotification(id);
      setNotifications((ns) => ns.filter((n) => n.id !== id));
    } catch (err) {
      setActionError(err.payload?.detail || 'Could not delete notification.');
    }
  };

  const unreadCount = notifications.filter(isUnread).length;

  // Keep the header bell in step with what this page shows.
  useEffect(() => {
    if (loading || error) return;
    window.dispatchEvent(new CustomEvent('nhwz:unread', { detail: unreadCount }));
  }, [unreadCount, loading, error]);

  return (
    <>
      <PageHeader eyebrow="Inbox" title="Notifications" description={unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'} />
      <PageContent>
        {actionError && <Alert variant="danger" icon={AlertCircle} message={actionError} onClose={() => setActionError(null)} className="mb-4" />}
        <Card className="!p-0 overflow-hidden">
          {loading ? (
            <div className="text-center py-16"><Spinner className="w-10 h-10 mx-auto text-cyan-300" /></div>
          ) : error ? (
            <div className="p-6"><Alert variant="danger" icon={AlertCircle} message={error} /></div>
          ) : notifications.length === 0 ? (
            <EmptyState icon={Bell} title="No notifications yet" description="Alerts about incidents near you will appear here." />
          ) : (
            notifications.map((n) => <NotificationItem key={n.id} notification={n} onRead={handleRead} onDelete={handleDelete} />)
          )}
        </Card>
      </PageContent>
    </>
  );
}
