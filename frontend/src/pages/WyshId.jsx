import React, { useEffect, useState } from 'react';
import Nav from '../components/Nav';
import { api } from '../lib/api';
import { ShieldCheck, Sparkles } from 'lucide-react';

export default function WyshIdCard() {
  const [w, setW] = useState(null);

  useEffect(() => {
    api.get('/wyshid/me').then(r => setW(r.data)).catch(() => {});
  }, []);

  if (!w) return (
    <div className="min-h-screen bg-background grain">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">Loading…</main>
    </div>
  );

  return (
    <div className="min-h-screen bg-background grain">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">
        <div className="mb-8">
          <div className="micro text-coral mb-3">WyshID · Identity</div>
          <h1 className="font-outfit text-4xl tracking-tighter">Your verified health identity</h1>
        </div>

        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-7" data-testid="wyshid-card">
            <div className="bg-slateink text-bone p-10 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-coral opacity-20 blur-3xl"></div>
              <div className="flex items-center justify-between mb-12">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-coral" />
                  <span className="micro text-coral">WYSHCARE</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs">
                  <ShieldCheck className="w-3.5 h-3.5 text-coral" /> {w.verification_status}
                </div>
              </div>
              <div className="mono text-3xl tracking-tight mb-1">{w.wysh_id}</div>
              <div className="text-sm text-bone/60 mb-12">Verified longitudinal health identity</div>
              <div className="grid grid-cols-3 gap-6">
                <div><div className="micro text-bone/40">Name</div><div className="text-sm mt-1.5">{w.name}</div></div>
                <div><div className="micro text-bone/40">Role</div><div className="text-sm mt-1.5 capitalize">{w.role}</div></div>
                <div><div className="micro text-bone/40">Trust</div><div className="text-sm mt-1.5 mono">{w.trust_score}/100</div></div>
              </div>
            </div>
          </div>
          <div className="col-span-12 lg:col-span-5 space-y-4">
            <div className="bento-cell p-6">
              <h3 className="font-outfit text-lg mb-3">What is WyshID?</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                A portable, verifiable identifier that links every clinical encounter, prescription, and lab into one longitudinal record. Built for the Indian healthcare graph.
              </p>
            </div>
            <div className="bento-cell p-6">
              <h3 className="font-outfit text-lg mb-3">Issued</h3>
              <div className="mono text-sm text-muted-foreground">{new Date(w.created_at).toLocaleString()}</div>
            </div>
            <div className="bento-cell p-6 bg-slateink text-bone">
              <h3 className="font-outfit text-lg mb-2">Next: verify in person</h3>
              <p className="text-sm text-bone/60 leading-relaxed">Visit a participating provider to upgrade your trust score and unlock full record portability.</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
