import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, Lock, Phone, CreditCard, MapPin, User, AlertCircle, KeyRound, ShieldCheck } from 'lucide-react';
import { register, verifyOtp, requestOtp, extractErrors } from '../api';
import { Button, Input, IconInput, FormField, Alert, Spinner, Tilt } from '../components/ui';
import { PageContent } from '../components/layout';
import { firstError } from '../lib/incidents';

export default function RegisterPage({ onRegister }) {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({ email: '', password: '', full_name: '', phone_number: '', national_id: '', address: '' });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [serverError, setServerError] = useState(null);

  // OTP step
  const [otpStep, setOtpStep] = useState(false);
  const [registeredUser, setRegisteredUser] = useState(null);
  const [debugCode, setDebugCode] = useState(null);
  const [otpCode, setOtpCode] = useState('');
  const [otpError, setOtpError] = useState(null);
  const [resendLoading, setResendLoading] = useState(false);
  const [resendMessage, setResendMessage] = useState(null);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    if (errors[e.target.name]) setErrors({ ...errors, [e.target.name]: undefined });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});
    setServerError(null);
    setLoading(true);
    try {
      const { user, otp } = await register(formData);
      setRegisteredUser(user);
      if (otp?.debug_code) setDebugCode(otp.debug_code);
      setOtpStep(true);
    } catch (err) {
      const fieldErrors = extractErrors(err.payload);
      if (Object.keys(fieldErrors).length > 0) setErrors(fieldErrors);
      else setServerError(err.payload?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setOtpError(null);
    setLoading(true);
    try {
      await verifyOtp(registeredUser.email, 'registration', otpCode);
      onRegister(registeredUser);
    } catch (err) {
      setOtpError(firstError(err.payload?.code) || err.payload?.detail || 'Invalid or expired code. Please try again.');
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResendLoading(true);
    setResendMessage(null);
    try {
      const result = await requestOtp(registeredUser.email, 'registration', 'sms');
      if (result?.debug_code) setDebugCode(result.debug_code);
      setResendMessage('A new code has been sent.');
    } catch {
      setResendMessage('Could not resend code. Please try again.');
    } finally {
      setResendLoading(false);
    }
  };

  if (otpStep) {
    return (
      <PageContent>
        <div className="max-w-md mx-auto py-10 animate-rise">
          <div className="text-center mb-8">
            <div className="mx-auto mb-5 w-16 h-16 rounded-2xl glass flex items-center justify-center">
              <ShieldCheck className="w-8 h-8 text-cyan-300" />
            </div>
            <h1 className="text-3xl mb-2">Verify your account</h1>
            <p className="text-slate-400">
              Enter the code sent to <strong className="text-white">{registeredUser?.phone_number}</strong>
            </p>
          </div>
          <Tilt max={4} className="glass glass-strong p-8">
            {debugCode && <Alert variant="info" icon={KeyRound} title="Dev mode — OTP code" message={`Your code is: ${debugCode}`} className="mb-6" />}
            {otpError && <Alert variant="danger" icon={AlertCircle} message={otpError} className="mb-6" />}
            {resendMessage && <Alert variant="success" message={resendMessage} className="mb-6" />}

            <form onSubmit={handleVerifyOtp} className="space-y-5">
              <FormField label="Verification code" required>
                <Input
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  placeholder="000000"
                  maxLength={12}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  disabled={loading}
                  required
                  className="text-center text-2xl tracking-[0.4em]"
                />
              </FormField>
              <Button type="submit" size="lg" className="w-full" disabled={loading || !otpCode}>
                {loading ? <><Spinner className="w-4 h-4" /> Verifying…</> : 'Verify account'}
              </Button>
            </form>

            <div className="text-center mt-6 text-sm text-slate-400 space-y-2">
              <p>
                Didn&apos;t receive a code?{' '}
                <button type="button" onClick={handleResend} disabled={resendLoading} className="text-cyan-300 font-semibold hover:text-cyan-200 disabled:opacity-50">
                  {resendLoading ? 'Sending…' : 'Resend code'}
                </button>
              </p>
              <p>
                Already verified?{' '}
                <button type="button" onClick={() => navigate('/login')} className="text-cyan-300 font-semibold hover:text-cyan-200">Sign in</button>
              </p>
            </div>
          </Tilt>
        </div>
      </PageContent>
    );
  }

  const field = (name, label, icon, extra = {}) => (
    <FormField label={label} error={errors[name]} required={name !== 'address'}>
      <IconInput icon={icon} name={name} value={formData[name]} onChange={handleChange} error={errors[name]} disabled={loading} required={name !== 'address'} {...extra} />
    </FormField>
  );

  return (
    <PageContent>
      <div className="max-w-2xl mx-auto py-10 animate-rise">
        <div className="text-center mb-8">
          <h1 className="text-3xl mb-2">Join the community</h1>
          <p className="text-slate-400">Create your account to get started with neighbourhood safety</p>
        </div>
        <Tilt max={3} className="glass glass-strong p-8">
          {serverError && <Alert variant="danger" icon={AlertCircle} message={serverError} className="mb-6" />}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid md:grid-cols-2 gap-5">
              {field('full_name', 'Full name', User, { placeholder: 'John Doe', autoComplete: 'name' })}
              {field('email', 'Email address', Mail, { type: 'email', placeholder: 'you@example.com', autoComplete: 'email' })}
              {field('phone_number', 'Phone number', Phone, { placeholder: '+263771234567', autoComplete: 'tel' })}
              {field('national_id', 'National ID', CreditCard, { placeholder: '12345678A' })}
              {field('password', 'Password', Lock, { type: 'password', placeholder: '••••••••', autoComplete: 'new-password' })}
              {field('address', 'Address', MapPin, { placeholder: '123 Main Street', autoComplete: 'street-address' })}
            </div>
            <Button type="submit" size="lg" className="w-full" disabled={loading}>
              {loading ? <><Spinner className="w-4 h-4" /> Creating account…</> : 'Create account'}
            </Button>
          </form>
          <p className="text-center text-slate-400 text-sm mt-6">
            Already have an account? <Link to="/login" className="text-cyan-300 font-semibold hover:text-cyan-200">Sign in</Link>
          </p>
        </Tilt>
      </div>
    </PageContent>
  );
}
