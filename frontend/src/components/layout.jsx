import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Menu, X, LogOut, User, Shield, AlertCircle, Home, Bell, Map as MapIcon, Siren, BadgeCheck } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchNotifications, openNotificationSocket, refreshAccessToken } from '../api';

const isUnread = (n) => n.status === 'queued' || n.status === 'sent';

function NotificationBell({ user, active }) {
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!user) return;
    fetchNotifications({ page_size: 50 })
      .then((data) => setUnread((data.results || data).filter(isUnread).length))
      .catch(() => {});
  }, [user]);

  useEffect(() => {
    const onUnread = (e) => setUnread(Number(e.detail) || 0);
    window.addEventListener('nhwz:unread', onUnread);
    return () => window.removeEventListener('nhwz:unread', onUnread);
  }, []);

  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;
    let authRetried = false; // one token refresh per failure streak
    let timer;
    function connect() {
      if (cancelled) return;
      const ws = openNotificationSocket();
      wsRef.current = ws;
      ws.onopen = () => { authRetried = false; };
      ws.onmessage = (event) => {
        try {
          if (JSON.parse(event.data).type === 'notification_created') setUnread((c) => c + 1);
        } catch { /* ignore malformed frames */ }
      };
      ws.onclose = (event) => {
        wsRef.current = null;
        if (cancelled) return;
        if (event?.code === 4003) return;
        if (event?.code === 4001) {
          if (authRetried) return; // still rejected after a refresh: session is invalid
          authRetried = true;
          // Expired JWT: refresh once, then reconnect; give up if refresh fails.
          refreshAccessToken().then(connect).catch(() => {});
          return;
        }
        timer = setTimeout(connect, 5000);
      };
      ws.onerror = () => ws.close();
    }
    connect();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [user]);

  const handleClick = useCallback(() => {
    setUnread(0);
    navigate('/notifications');
  }, [navigate]);

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`relative p-2.5 rounded-xl transition-colors ${active ? 'bg-white/15 text-white' : 'text-slate-300 hover:bg-white/10 hover:text-white'}`}
      title="Notifications"
      aria-label={unread > 0 ? `Notifications (${unread} unread)` : 'Notifications'}
    >
      <Bell className="w-5 h-5" />
      {unread > 0 && (
        <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 px-1 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white shadow-[0_0_10px_rgba(239,68,68,0.8)]">
          {unread > 9 ? '9+' : unread}
        </span>
      )}
    </button>
  );
}

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-3 group" aria-label="NHWZ home">
      <div className="relative w-10 h-10" style={{ perspective: 400 }}>
        <div
          className="absolute inset-0 rounded-xl bg-gradient-to-br from-cyan-300 via-cyan-500 to-violet-500 flex items-center justify-center transition-transform duration-500 group-hover:[transform:rotateY(180deg)]"
          style={{ boxShadow: '0 4px 0 #0e7490, 0 10px 24px -4px rgba(34,211,238,.6), inset 0 1px 0 rgba(255,255,255,.6)', transformStyle: 'preserve-3d' }}
        >
          <Shield className="w-5 h-5 text-ink-950" strokeWidth={2.4} />
        </div>
      </div>
      <div className="leading-tight hidden sm:block">
        <p className="text-base font-bold text-white font-display tracking-tight">NHWZ</p>
        <p className="text-[10px] uppercase tracking-[0.14em] text-slate-400">Neighbourhood Watch</p>
      </div>
    </Link>
  );
}

export function Header({ user, onLogout }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const isActive = (path) => (path === '/' ? location.pathname === '/' : location.pathname.startsWith(path));
  const roleCode = user?.role?.code;
  const canReview = roleCode === 'coordinator' || roleCode === 'system_admin' || roleCode === 'block_captain';

  const navItems = [
    { path: '/', label: 'Home', icon: Home, public: true },
    ...(user
      ? [
          { path: '/incidents', label: 'Incidents', icon: AlertCircle },
          { path: '/map', label: 'Live Map', icon: MapIcon },
          { path: '/sos', label: 'SOS', icon: Siren, danger: true },
          { path: '/profile', label: 'Profile', icon: User },
          ...(canReview ? [{ path: '/coordinator', label: 'Reviews', icon: Shield }] : []),
          ...(user.verification_status !== 'approved' ? [{ path: '/verify', label: 'Get verified', icon: BadgeCheck }] : []),
        ]
      : []),
  ];

  const linkClass = (item) =>
    `px-3.5 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-2 ${
      isActive(item.path)
        ? 'bg-white/15 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.25)]'
        : item.danger
          ? 'text-red-300 hover:text-red-200 hover:bg-red-400/10'
          : 'text-slate-300 hover:text-white hover:bg-white/10'
    }`;

  return (
    <header className="sticky top-0 z-[600] px-3 sm:px-6 pt-3">
      <div className="glass glass-strong max-w-7xl mx-auto !rounded-2xl">
        <div className="flex items-center justify-between h-16 px-4">
          <div className="flex items-center gap-6">
            <Logo />
            <nav className="hidden lg:flex items-center gap-1" aria-label="Main">
              {navItems.map((item) => (
                <Link key={item.path} to={item.path} className={linkClass(item)} aria-current={isActive(item.path) ? 'page' : undefined}>
                  <item.icon className="w-4 h-4" />
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            {user ? (
              <>
                <NotificationBell user={user} active={isActive('/notifications')} />
                <div className="hidden sm:block text-right ml-2 mr-1 max-w-[160px]">
                  <p className="text-sm font-semibold text-white truncate">{user.full_name}</p>
                  <p className="text-[11px] text-slate-400 capitalize truncate">{user.role?.name || 'Resident'}</p>
                </div>
                <button type="button" onClick={onLogout} className="hidden sm:inline-flex p-2.5 rounded-xl text-slate-300 hover:bg-white/10 hover:text-white transition-colors" title="Log out" aria-label="Log out">
                  <LogOut className="w-5 h-5" />
                </button>
              </>
            ) : (
              <div className="hidden sm:flex gap-2">
                <button type="button" onClick={() => navigate('/login')} className="btn btn-ghost px-4 py-2 text-sm">Log in</button>
                <button type="button" onClick={() => navigate('/register')} className="btn btn-primary px-4 py-2 text-sm">Register</button>
              </div>
            )}

            <button
              type="button"
              onClick={() => setMobileMenuOpen((o) => !o)}
              className="lg:hidden p-2.5 rounded-xl text-slate-200 hover:bg-white/10"
              aria-label="Toggle menu"
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="lg:hidden border-t border-white/10 p-3 space-y-1">
            {navItems.map((item) => (
              <Link key={item.path} to={item.path} className={`${linkClass(item)} w-full`}>
                <item.icon className="w-4 h-4" />
                {item.label}
              </Link>
            ))}
            {user && (
              <>
                <Link to="/notifications" className={`${linkClass({ path: '/notifications' })} w-full`}>
                  <Bell className="w-4 h-4" /> Notifications
                </Link>
                <button type="button" onClick={onLogout} className="w-full text-left px-3.5 py-2 rounded-xl text-sm font-medium text-slate-300 hover:bg-white/10 flex items-center gap-2">
                  <LogOut className="w-4 h-4" /> Log out
                </button>
              </>
            )}
            {!user && (
              <div className="flex gap-2 pt-1">
                <Link to="/login" className="btn btn-secondary flex-1 py-2.5 text-sm">Log in</Link>
                <Link to="/register" className="btn btn-primary flex-1 py-2.5 text-sm">Register</Link>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="px-3 sm:px-6 pb-6 mt-20">
      <div className="glass max-w-7xl mx-auto !rounded-3xl px-6 sm:px-10 py-10">
        <div className="grid md:grid-cols-4 gap-8 mb-8">
          <div>
            <h3 className="font-bold text-white mb-3 text-lg">NHWZ</h3>
            <p className="text-sm text-slate-400">Community-driven security and emergency response for Zimbabwean neighbourhoods.</p>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-3 text-sm uppercase tracking-wider">Platform</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li><Link to="/incidents" className="hover:text-cyan-300 transition">Incident Reporting</Link></li>
              <li><Link to="/sos" className="hover:text-cyan-300 transition">Emergency SOS</Link></li>
              <li><Link to="/map" className="hover:text-cyan-300 transition">Community Map</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-3 text-sm uppercase tracking-wider">Account</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li><Link to="/profile" className="hover:text-cyan-300 transition">Profile</Link></li>
              <li><Link to="/verify" className="hover:text-cyan-300 transition">Get verified</Link></li>
              <li><Link to="/notifications" className="hover:text-cyan-300 transition">Notifications</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-3 text-sm uppercase tracking-wider">Emergency</h4>
            <p className="text-sm text-slate-400">In immediate danger, contact the Zimbabwe Republic Police on <span className="text-white font-semibold">995</span> first, then raise an SOS here.</p>
          </div>
        </div>
        <div className="border-t border-white/10 pt-6 flex flex-col md:flex-row items-center justify-between gap-2 text-xs text-slate-500">
          <p>&copy; {new Date().getFullYear()} Neighbourhood Watch Zimbabwe. All rights reserved.</p>
          <p>Map data &copy; OpenStreetMap contributors</p>
        </div>
      </div>
    </footer>
  );
}

export function PageHeader({ title, description, action, eyebrow }) {
  return (
    <div className="page-header">
      <div className="container">
        <div className="flex flex-wrap items-end justify-between gap-4 animate-rise">
          <div className="min-w-0">
            {eyebrow && <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300 mb-2">{eyebrow}</p>}
            <h1 className="text-3xl sm:text-4xl break-words">{title}</h1>
            {description && <p className="text-slate-400 mt-2 max-w-2xl">{description}</p>}
          </div>
          {action}
        </div>
      </div>
    </div>
  );
}

export function PageContent({ children, className = '' }) {
  return (
    <div className={`page-content ${className}`}>
      <div className="container">{children}</div>
    </div>
  );
}
