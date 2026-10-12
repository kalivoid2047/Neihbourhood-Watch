import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ExternalLink, FileAudio, FileVideo, Image as ImageIcon, Paperclip, Trash2, Upload } from 'lucide-react';
import { deleteIncidentMedia, resolveMediaUrl, uploadIncidentMedia } from '../api';
import { firstError } from '../lib/incidents';
import { Alert, Button, Card, Spinner } from './ui';

const MAX_BYTES = 100 * 1024 * 1024; // matches the backend limit
const ICONS = { image: ImageIcon, video: FileVideo, audio: FileAudio };

const formatSize = (bytes) => {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

/** Image preview fetched with the Bearer token (a plain <img src> can't send it). */
function Thumb({ media }) {
  const [src, setSrc] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (media.media_type !== 'image') return undefined;
    let cancelled = false;
    let revoke = () => {};
    resolveMediaUrl(media.file)
      .then((r) => {
        revoke = r.revoke;
        if (cancelled) r.revoke();
        else setSrc(r.url);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => { cancelled = true; revoke(); };
  }, [media.file, media.media_type]);

  const Icon = ICONS[media.media_type] || Paperclip;
  if (src) return <img src={src} alt={media.original_filename} className="w-full h-full object-cover" />;
  return (
    <div className="w-full h-full flex items-center justify-center text-slate-400">
      {media.media_type === 'image' && !failed ? <Spinner className="w-5 h-5" /> : <Icon className="w-7 h-7" />}
    </div>
  );
}

export default function EvidenceSection({ incident, user, canUpload, canManage, onChanged }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const media = incident.media || [];

  if (!canUpload && media.length === 0) return null;

  const handleFiles = async (e) => {
    const files = [...(e.target.files || [])];
    e.target.value = ''; // allow re-selecting the same file
    if (files.length === 0) return;
    setError(null);
    const tooBig = files.find((f) => f.size > MAX_BYTES);
    if (tooBig) {
      setError(`${tooBig.name} is larger than 100 MB.`);
      return;
    }
    setUploading(true);
    try {
      for (const file of files) {
        // eslint-disable-next-line no-await-in-loop
        await uploadIncidentMedia(incident.id, file);
      }
    } catch (err) {
      setError(err.payload?.detail || firstError(err.payload?.file) || firstError(err.payload?.media_type) || err.message || 'Upload failed.');
    } finally {
      setUploading(false);
      onChanged?.(); // refresh even after a partial success
    }
  };

  const open = async (m) => {
    setError(null);
    setBusyId(m.id);
    try {
      const { url, revoke } = await resolveMediaUrl(m.file);
      window.open(url, '_blank', 'noopener');
      setTimeout(revoke, 60_000); // give the new tab time to load it
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (m) => {
    if (!window.confirm(`Delete ${m.original_filename}?`)) return;
    setError(null);
    setBusyId(m.id);
    try {
      await deleteIncidentMedia(m.id);
      onChanged?.();
    } catch (err) {
      setError(err.payload?.detail || err.message || 'Could not delete this file.');
    } finally {
      setBusyId(null);
    }
  };

  const mayDelete = (m) => canManage || (m.uploaded_by && String(m.uploaded_by) === String(user?.id));

  return (
    <Card>
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <h2 className="text-lg flex items-center gap-2"><Paperclip className="w-5 h-5 text-cyan-300" /> Evidence</h2>
        {canUpload && (
          <>
            <input ref={inputRef} type="file" multiple accept="image/*,video/*,audio/*" className="hidden" onChange={handleFiles} aria-label="Attach evidence files" />
            <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()} disabled={uploading}>
              {uploading ? <><Spinner className="w-4 h-4" /> Uploading…</> : <><Upload className="w-4 h-4" /> Add files</>}
            </Button>
          </>
        )}
      </div>

      {error && <Alert variant="danger" icon={AlertCircle} message={String(error)} onClose={() => setError(null)} className="mb-4" />}

      {media.length === 0 ? (
        <p className="text-sm text-slate-400">No files attached yet. Photos, video and audio up to 100 MB are supported.</p>
      ) : (
        <ul className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {media.map((m) => (
            <li key={m.id} className="glass !rounded-xl overflow-hidden flex flex-col">
              <div className="aspect-video bg-ink-900/60"><Thumb media={m} /></div>
              <div className="p-3 flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate" title={m.original_filename}>{m.original_filename}</p>
                <p className="text-xs text-slate-400">{m.media_type_display} · {formatSize(m.size_bytes)}</p>
              </div>
              <div className="flex border-t border-white/10">
                <button type="button" onClick={() => open(m)} disabled={busyId === m.id} className="flex-1 py-2 text-xs font-semibold text-cyan-200 hover:bg-white/10 flex items-center justify-center gap-1.5 disabled:opacity-50">
                  {busyId === m.id ? <Spinner className="w-3.5 h-3.5" /> : <ExternalLink className="w-3.5 h-3.5" />} Open
                </button>
                {mayDelete(m) && (
                  <button type="button" onClick={() => remove(m)} disabled={busyId === m.id} aria-label={`Delete ${m.original_filename}`} className="px-3 text-red-300 hover:bg-red-400/10 border-l border-white/10 disabled:opacity-50">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
