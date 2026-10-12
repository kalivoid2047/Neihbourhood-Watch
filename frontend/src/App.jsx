import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Header, Footer } from './components/layout';
import HomePage from './pages/home';
import LoginPage from './pages/login';
import RegisterPage from './pages/register';
import ProfilePage from './pages/profile';
import IncidentsPage from './pages/incidents';
import IncidentDetailPage from './pages/incident-detail';
import VerificationPage from './pages/verification';
import CoordinatorPage from './pages/coordinator';
import NotificationsPage from './pages/notifications';
import MapPage from './pages/map';
import SosPage from './pages/sos';
import { clearTokens, getRefreshToken, getStoredTokens, fetchProfile, logout } from './api';
import { Aurora, Spinner } from './components/ui';
import LiveAlerts from './components/LiveAlerts';
import './styles/globals.css';

function useAuthState() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!getStoredTokens()) {
        setLoading(false);
        return;
      }
      try {
        const profile = await fetchProfile();
        if (!cancelled) setUser(profile);
      } catch {
        clearTokens();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  return { user, setUser, loading };
}

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

// Defined at module scope so route elements keep a stable identity across renders
// (a component declared inside AppRoutes remounts its whole subtree on every auth update).
function Protected({ user, children }) {
  return user ? children : <Navigate to="/login" replace />;
}

function GuestOnly({ user, children }) {
  return user ? <Navigate to="/incidents" replace /> : children;
}

function AppRoutes() {
  const auth = useAuthState();
  const navigate = useNavigate();

  const handleLogout = () => {
    const refresh = getRefreshToken();
    clearTokens();
    auth.setUser(null);
    navigate('/');
    // Blacklist the refresh token server-side. Fire-and-forget: the UI is
    // already cleared so a network failure here is non-blocking for the user.
    if (refresh) logout(refresh).catch(() => {});
  };

  if (auth.loading) {
    return (
      <>
        <Aurora />
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <Spinner className="w-12 h-12 mx-auto mb-4 text-cyan-300" />
            <p className="text-slate-400">Loading…</p>
          </div>
        </div>
      </>
    );
  }

  const { user } = auth;

  return (
    <>
      <Aurora />
      <ScrollToTop />
      {user && <LiveAlerts user={user} />}
      <div className="min-h-screen flex flex-col">
        <Header user={user} onLogout={handleLogout} />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<HomePage user={user} />} />
            <Route
              path="/login"
              element={<GuestOnly user={user}><LoginPage onLogin={(u) => { auth.setUser(u); navigate('/incidents'); }} /></GuestOnly>}
            />
            <Route
              path="/register"
              element={<GuestOnly user={user}><RegisterPage onRegister={(u) => { auth.setUser(u); navigate('/profile'); }} /></GuestOnly>}
            />
            <Route path="/profile" element={<Protected user={user}><ProfilePage user={user} onUpdate={auth.setUser} /></Protected>} />
            <Route path="/incidents" element={<Protected user={user}><IncidentsPage user={user} /></Protected>} />
            <Route path="/incidents/:id" element={<Protected user={user}><IncidentDetailPage user={user} /></Protected>} />
            <Route path="/map" element={<Protected user={user}><MapPage user={user} /></Protected>} />
            <Route path="/sos" element={<Protected user={user}><SosPage user={user} /></Protected>} />
            <Route path="/verify" element={<Protected user={user}><VerificationPage user={user} onUpdate={auth.setUser} /></Protected>} />
            <Route path="/coordinator" element={<Protected user={user}><CoordinatorPage user={user} /></Protected>} />
            <Route path="/notifications" element={<Protected user={user}><NotificationsPage user={user} /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
