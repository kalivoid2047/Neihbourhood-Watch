import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, Lock, AlertCircle, Shield } from 'lucide-react';
import { login, extractErrors } from '../api';
import { Button, IconInput, FormField, Alert, Spinner, Tilt } from '../components/ui';
import { PageContent } from '../components/layout';

export default function LoginPage({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [serverError, setServerError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});
    setServerError(null);
    setLoading(true);
    try {
      const user = await login(email, password);
      onLogin(user);
    } catch (err) {
      const fieldErrors = extractErrors(err.payload);
      if (Object.keys(fieldErrors).length > 0) {
        setErrors(fieldErrors);
      } else {
        setServerError(err.payload?.detail || 'Login failed. Please check your credentials and try again.');
      }
      setLoading(false);
    }
  };

  return (
    <PageContent>
      <div className="max-w-md mx-auto py-10 animate-rise">
        <div className="text-center mb-8">
          <div
            className="mx-auto mb-5 w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-300 via-cyan-500 to-violet-500 flex items-center justify-center"
            style={{ boxShadow: '0 6px 0 #0e7490, 0 18px 34px -6px rgba(34,211,238,.55), inset 0 1px 0 rgba(255,255,255,.6)' }}
          >
            <Shield className="w-8 h-8 text-ink-950" strokeWidth={2.4} />
          </div>
          <h1 className="text-3xl mb-2">Welcome back</h1>
          <p className="text-slate-400">Sign in to your account to continue</p>
        </div>

        <Tilt max={4} className="glass glass-strong p-8">
          {serverError && <Alert variant="danger" icon={AlertCircle} message={serverError} className="mb-6" />}

          <form onSubmit={handleSubmit} className="space-y-5">
            <FormField label="Email address" error={errors.email} required>
              <IconInput icon={Mail} type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} error={errors.email} disabled={loading} required />
            </FormField>
            <FormField label="Password" error={errors.password} required>
              <IconInput icon={Lock} type="password" autoComplete="current-password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} error={errors.password} disabled={loading} required />
            </FormField>
            <Button type="submit" size="lg" className="w-full" disabled={loading}>
              {loading ? <><Spinner className="w-4 h-4" /> Signing in…</> : 'Sign in'}
            </Button>
          </form>

          <p className="text-center text-slate-400 text-sm mt-6">
            Don&apos;t have an account?{' '}
            <Link to="/register" className="text-cyan-300 font-semibold hover:text-cyan-200">Register now</Link>
          </p>
        </Tilt>
      </div>
    </PageContent>
  );
}
