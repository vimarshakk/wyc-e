import React, { useEffect, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import Nav from '../components/Nav';
import { api } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';

export default function Abdm() {
  const { user } = useAuth(); const [state, setState] = useState(null);
  useEffect(() => { const path = user?.role === 'admin' ? '/abdm/status' : '/abdm/my-status'; api.get(path).then((r) => setState(r.data)).catch(() => setState({ unavailable: true })); }, [user]);
  return <div className="min-h-screen bg-background grain"><Nav /><main className="max-w-[1000px] mx-auto px-6 lg:px-10 py-10"><div className="micro text-coral mb-3">ABDM interoperability</div><h1 data-testid="abdm-heading" className="font-outfit text-4xl tracking-tighter">Consent-led health exchange</h1><div data-testid="abdm-status-panel" className="bento-cell p-7 mt-8"><div className="flex items-center gap-3"><ShieldCheck className="w-6 h-6 text-coral" /><div><h2 className="font-outfit text-2xl">Sandbox status</h2><p className="text-sm text-muted-foreground mt-1">ABHA, care-context, consent and health-information exchanges only progress after ABDM confirms each step.</p></div></div><pre className="mono text-xs mt-6 whitespace-pre-wrap border border-border p-4">{state ? JSON.stringify(state, null, 2) : 'Loading secure status…'}</pre></div></main></div>;
}