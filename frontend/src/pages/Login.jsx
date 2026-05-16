import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { ArrowRight } from 'lucide-react';

const GoogleBtn = () => {
  const onClick = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/auth/callback';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };
  return (
    <button onClick={onClick} data-testid="google-login-btn"
      className="btn-sharp w-full border border-foreground py-3 inline-flex items-center justify-center gap-3 hover:bg-foreground hover:text-background transition-colors">
      <svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z"/><path fill="#FBBC05" d="M3.964 10.706A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.997 8.997 0 000 9c0 1.452.348 2.827.957 4.038l3.007-2.332z"/><path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.962L3.964 7.294C4.672 5.167 6.656 3.58 9 3.58z"/></svg>
      Continue with Google
    </button>
  );
};

export default function Login() {
  const { loginPassword } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await loginPassword(email, password);
      toast.success(`Welcome back, ${u.name}`);
      navigate(`/app/${u.role}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Login failed');
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-background grain">
      <div className="hidden lg:flex flex-col justify-between p-12 bg-slateink text-bone">
        <Link to="/" className="font-outfit text-xl" data-testid="login-logo">WyshCare</Link>
        <div>
          <div className="micro text-coral mb-4">India's healthcare OS</div>
          <h2 className="font-outfit text-4xl tracking-tighter leading-tight max-w-md">
            One identity. Every encounter. Continuous intelligence.
          </h2>
          <p className="text-bone/60 mt-6 max-w-md">Your WyshID is portable, verifiable, and longitudinal across every clinic, hospital and lab in India.</p>
        </div>
        <div className="mono text-xs text-bone/40">© 2026 · WYSHCARE</div>
      </div>
      <div className="flex items-center justify-center p-8 lg:p-16">
        <div className="w-full max-w-md">
          <Link to="/" className="lg:hidden font-outfit text-xl mb-8 inline-block">WyshCare</Link>
          <div className="micro text-coral mb-3">Sign in</div>
          <h1 className="font-outfit text-4xl tracking-tighter mb-8">Welcome back</h1>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="micro text-muted-foreground">Email</label>
              <input data-testid="login-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                className="w-full mt-2 px-4 py-3 border border-border bg-card focus:outline-none focus:border-foreground transition-colors" />
            </div>
            <div>
              <label className="micro text-muted-foreground">Password</label>
              <input data-testid="login-password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                className="w-full mt-2 px-4 py-3 border border-border bg-card focus:outline-none focus:border-foreground transition-colors" />
            </div>
            <button disabled={busy} data-testid="login-submit"
              className="btn-sharp w-full bg-slateink text-bone py-3 font-medium inline-flex items-center justify-center gap-2 disabled:opacity-60">
              {busy ? 'Signing in…' : 'Sign in'} <ArrowRight className="w-4 h-4" />
            </button>
          </form>
          <div className="flex items-center gap-3 my-6">
            <span className="flex-1 h-px bg-border"></span>
            <span className="micro text-muted-foreground">or</span>
            <span className="flex-1 h-px bg-border"></span>
          </div>
          <GoogleBtn />
          <p className="mt-8 text-sm text-muted-foreground">
            New to WyshCare?{' '}
            <Link to="/signup" data-testid="login-to-signup" className="text-foreground underline underline-offset-4 hover:text-coral">Claim your WyshID</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
