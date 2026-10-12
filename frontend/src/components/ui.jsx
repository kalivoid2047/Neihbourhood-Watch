import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import '../styles/globals.css';

const cx = (...parts) => parts.filter(Boolean).join(' ');

/* ── Background ─────────────────────────────────────────────────────────── */

export function Aurora() {
  return (
    <div className="aurora" aria-hidden="true">
      <div className="orb" style={{ width: 460, height: 460, left: '-6%', top: '8%', background: 'rgba(34,211,238,0.5)' }} />
      <div className="orb" style={{ width: 520, height: 520, right: '-8%', top: '2%', background: 'rgba(139,92,246,0.5)', animationDelay: '-6s' }} />
      <div className="orb" style={{ width: 420, height: 420, left: '38%', bottom: '-12%', background: 'rgba(14,165,233,0.4)', animationDelay: '-12s' }} />
    </div>
  );
}

/* ── 3D tilt wrapper ────────────────────────────────────────────────────── */

const canTilt = () =>
  typeof window !== 'undefined' &&
  window.matchMedia &&
  !window.matchMedia('(hover: none)').matches &&
  !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * Pointer-driven 3D tilt. Writes the transform straight to the DOM node so
 * pointer movement never triggers a React re-render.
 */
export function Tilt({ max = 8, lift = 0, glare = true, className = '', children, ...props }) {
  const ref = useRef(null);

  const onMove = (e) => {
    const el = ref.current;
    if (!el || !canTilt()) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    el.style.transform = `perspective(1000px) rotateX(${((0.5 - py) * max).toFixed(2)}deg) rotateY(${((px - 0.5) * max).toFixed(2)}deg) translateZ(${lift}px)`;
    el.style.setProperty('--gx', `${(px * 100).toFixed(1)}%`);
    el.style.setProperty('--gy', `${(py * 100).toFixed(1)}%`);
  };
  const onLeave = () => {
    if (ref.current) ref.current.style.transform = '';
  };

  return (
    <div ref={ref} onPointerMove={onMove} onPointerLeave={onLeave} className={cx('tilt', className)} {...props}>
      {children}
      {glare && <span className="tilt-glare" aria-hidden="true" />}
    </div>
  );
}

/* ── Buttons ────────────────────────────────────────────────────────────── */

export function Button({ variant = 'primary', size = 'md', className = '', children, type = 'button', ...props }) {
  // Full class names must appear literally so Tailwind's content scan keeps them.
  const variants = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    danger: 'btn-danger',
    success: 'btn-success',
    outline: 'btn-outline',
    ghost: 'btn-ghost',
  };
  const sizes = {
    sm: 'px-3 py-1.5 text-sm gap-1.5',
    md: 'px-4 py-2.5 text-sm gap-2',
    lg: 'px-6 py-3.5 text-base gap-2',
  };
  return (
    <button type={type} className={cx('btn', variants[variant] || variants.primary, sizes[size], className)} {...props}>
      {children}
    </button>
  );
}

/* ── Surfaces ───────────────────────────────────────────────────────────── */

export function Card({ className = '', tilt = false, strong = false, children, ...props }) {
  const classes = cx('glass p-6', strong && 'glass-strong', className);
  if (tilt) {
    return (
      <Tilt className={classes} {...props}>
        {children}
      </Tilt>
    );
  }
  return (
    <div className={classes} {...props}>
      {children}
    </div>
  );
}

export function Badge({ variant = 'primary', className = '', children }) {
  const variants = {
    primary: 'bg-cyan-400/15 text-cyan-200 border-cyan-300/30',
    success: 'bg-emerald-400/15 text-emerald-200 border-emerald-300/30',
    warning: 'bg-amber-400/15 text-amber-200 border-amber-300/30',
    danger: 'bg-red-400/15 text-red-200 border-red-300/30',
    accent: 'bg-violet-400/15 text-violet-200 border-violet-300/30',
    gray: 'bg-white/10 text-slate-200 border-white/15',
  };
  return <span className={cx('badge', variants[variant] || variants.gray, className)}>{children}</span>;
}

export function Alert({ variant = 'info', icon: Icon, title, message, onClose, className = '' }) {
  const variants = {
    info: 'bg-cyan-400/10 border-cyan-300/30 text-cyan-100',
    success: 'bg-emerald-400/10 border-emerald-300/30 text-emerald-100',
    warning: 'bg-amber-400/10 border-amber-300/30 text-amber-100',
    danger: 'bg-red-400/10 border-red-300/30 text-red-100',
  };
  return (
    <div role="alert" className={cx('rounded-xl border p-4 flex gap-3 backdrop-blur-md', variants[variant], className)}>
      {Icon && <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />}
      <div className="flex-1 min-w-0">
        {title && <h3 className="font-semibold text-sm mb-0.5 !text-current font-sans">{title}</h3>}
        {message && <p className="text-sm break-words">{message}</p>}
      </div>
      {onClose && (
        <button type="button" onClick={onClose} aria-label="Dismiss" className="flex-shrink-0 opacity-70 hover:opacity-100">
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

export function Spinner({ className = '' }) {
  return (
    <span className={cx('inline-block animate-spin', className)} role="status" aria-label="Loading">
      <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
      </svg>
    </span>
  );
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="text-center py-16 px-6">
      {Icon && (
        <div className="mx-auto mb-5 w-16 h-16 rounded-2xl glass flex items-center justify-center">
          <Icon className="w-8 h-8 text-cyan-300" />
        </div>
      )}
      <p className="text-lg font-semibold text-white font-display">{title}</p>
      {description && <p className="text-sm text-slate-400 mt-1 max-w-sm mx-auto">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/* ── Modal ──────────────────────────────────────────────────────────────── */

export function Modal({ isOpen, title, children, onClose, actions, size = 'md' }) {
  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const sizes = { sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-lg', xl: 'max-w-xl', '2xl': 'max-w-3xl' };

  return createPortal(
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-ink-950/60 backdrop-blur-sm animate-rise"
      onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}
    >
      <div role="dialog" aria-modal="true" aria-label={title} className={cx('glass glass-strong w-full max-h-[92vh] flex flex-col', sizes[size])}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 overflow-y-auto">{children}</div>
        {actions && <div className="flex justify-end gap-3 px-6 py-4 border-t border-white/10">{actions}</div>}
      </div>
    </div>,
    document.body,
  );
}

/* ── Form controls ──────────────────────────────────────────────────────── */

export function FormField({ label, error, hint, required, children, className = '' }) {
  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-slate-300 mb-1.5">
          {label}
          {required && <span className="text-red-400 ml-1">*</span>}
        </label>
      )}
      {children}
      {hint && !error && <p className="text-xs text-slate-500 mt-1">{hint}</p>}
      {error && <p className="text-red-300 text-sm mt-1">{Array.isArray(error) ? error[0] : String(error)}</p>}
    </div>
  );
}

export function Input({ error, className = '', ...props }) {
  return <input className={cx('field', error && 'field-error', className)} {...props} />;
}

export function Textarea({ error, className = '', ...props }) {
  return <textarea className={cx('field resize-none', error && 'field-error', className)} {...props} />;
}

/** Input with a leading icon, vertically centred regardless of field height. */
export function IconInput({ icon: Icon, error, className = '', ...props }) {
  return (
    <div className="relative">
      {Icon && <Icon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />}
      <input className={cx('field', Icon && 'pl-10', error && 'field-error', className)} {...props} />
    </div>
  );
}

/** Small label + value pair used on detail screens. */
export function Detail({ label, children, className = '' }) {
  return (
    <div className={className}>
      <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="mt-1 text-slate-100 break-words">{children}</dd>
    </div>
  );
}

export function Select({ error, options, className = '', ...props }) {
  return (
    <select className={cx('field', error && 'field-error', className)} {...props}>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
