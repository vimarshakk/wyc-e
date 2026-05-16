import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { ArrowRight } from 'lucide-react';

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'patient', specialty: '' });
  const [busy, setBusy] = useState(false);

  const upd = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await signup(form);
      toast.success(`WyshID issued: ${u.wysh_id}`);
      navigate(`/app/${u.role}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Signup failed');
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-background grain">
      <div className="flex items-center justify-center p-8 lg:p-16 order-2 lg:order-1">
        <div className="w-full max-w-md">
          <Link to="/" className="lg:hidden font-outfit text-xl mb-8 inline-block">WyshCare</Link>
          <div className="micro text-coral mb-3">Issue a WyshID</div>
          <h1 className="font-outfit text-4xl tracking-tighter mb-8">Claim your verified<br/>health identity</h1>
          <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-3 gap-2 p-1 border border-border">
              {['patient', 'doctor', 'admin'].map(r => (
                <button type="button" key={r} onClick={() => setForm({ ...form, role: r })}
                  data-testid={`signup-role-${r}`}
                  className={`py-2 text-sm capitalize transition-colors ${form.role === r ? 'bg-slateink text-bone' : 'hover:bg-muted'}`}>
                  {r}
                </button>
              ))}
            </div>
            <input data-testid="signup-name" required placeholder="Full name" value={form.name} onChange={upd('name')}
              className="w-full px-4 py-3 border border-border bg-card focus:outline-none focus:border-foreground" />
            <input data-testid="signup-email" required type="email" placeholder="Email" value={form.email} onChange={upd('email')}
              className="w-full px-4 py-3 border border-border bg-card focus:outline-none focus:border-foreground" />
            <input data-testid="signup-password" required type="password" minLength="8" placeholder="Password (min 8 chars)" value={form.password} onChange={upd('password')}
              className="w-full px-4 py-3 border border-border bg-card focus:outline-none focus:border-foreground" />
            {form.role === 'doctor' && (
              <input data-testid="signup-specialty" placeholder="Specialty (e.g. Cardiology)" value={form.specialty} onChange={upd('specialty')}
                className="w-full px-4 py-3 border border-border bg-card focus:outline-none focus:border-foreground" />
            )}
            <button disabled={busy} data-testid="signup-submit"
              className="btn-sharp w-full bg-slateink text-bone py-3 font-medium inline-flex items-center justify-center gap-2 disabled:opacity-60">
              {busy ? 'Issuing…' : 'Issue WyshID'} <ArrowRight className="w-4 h-4" />
            </button>
          </form>
          <p className="mt-8 text-sm text-muted-foreground">
            Already have a WyshID?{' '}
            <Link to="/login" data-testid="signup-to-login" className="text-foreground underline underline-offset-4 hover:text-coral">Sign in</Link>
          </p>
        </div>
      </div>
      <div className="hidden lg:flex flex-col justify-between p-12 bg-slateink text-bone order-1 lg:order-2">
        <div className="text-right font-outfit text-xl">WyshCare</div>
        <div>
          <div className="micro text-coral mb-4">Your record. Your control.</div>
          <h2 className="font-outfit text-4xl tracking-tighter leading-tight max-w-md">
            A verified, longitudinal identity that follows you to every clinic.
          </h2>
        </div>
        <div className="mono text-xs text-bone/40 text-right">© 2026 · WYSHCARE</div>
      </div>
    </div>
  );
}
