import React, { useEffect, useState } from 'react';
import Nav from '../components/Nav';
import { api } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { Users, Calendar, Search } from 'lucide-react';
import { toast } from 'sonner';

export default function DoctorDashboard() {
  const { user } = useAuth();
  const [appts, setAppts] = useState([]);
  const [lookup, setLookup] = useState('');
  const [lookupResult, setLookupResult] = useState(null);

  useEffect(() => {
    api.get('/appointments/mine').then(r => setAppts(r.data)).catch(() => {});
  }, []);

  const doLookup = async (e) => {
    e.preventDefault();
    if (!lookup) return;
    try {
      const { data } = await api.get(`/wyshid/${lookup}`);
      setLookupResult(data);
    } catch {
      toast.error('WyshID not found');
      setLookupResult(null);
    }
  };

  const today = appts.filter(a => {
    const d = new Date(a.scheduled_at);
    const now = new Date();
    return d.toDateString() === now.toDateString();
  });

  return (
    <div className="min-h-screen bg-background grain">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">
        <div className="grid grid-cols-12 gap-4 mb-6">
          <div className="col-span-12 lg:col-span-7 bento-cell p-8">
            <div className="micro text-coral mb-3">Provider</div>
            <h1 className="font-outfit text-4xl tracking-tighter">Dr. {user?.name?.split(' ').slice(-1)}</h1>
            <p className="text-muted-foreground mt-2">{user?.specialty || 'General practice'} · {user?.wysh_id}</p>
          </div>
          <div className="col-span-12 lg:col-span-5 bento-cell p-8">
            <div className="micro text-coral mb-3">Today</div>
            <div className="font-outfit text-5xl tracking-tighter">{today.length}</div>
            <div className="text-sm text-muted-foreground mt-1">scheduled consultations</div>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8 bento-cell p-7">
            <div className="flex justify-between items-center mb-6">
              <h2 className="font-outfit text-2xl tracking-tight">Patient queue</h2>
              <Users className="w-4 h-4 text-muted-foreground" />
            </div>
            <table className="w-full text-sm" data-testid="doctor-queue">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 micro text-muted-foreground">Patient</th>
                  <th className="text-left py-2 micro text-muted-foreground">WyshID</th>
                  <th className="text-left py-2 micro text-muted-foreground">Time</th>
                  <th className="text-left py-2 micro text-muted-foreground">Mode</th>
                </tr>
              </thead>
              <tbody>
                {appts.slice(0, 12).map(a => (
                  <tr key={a.appointment_id} className="border-b border-border hover:bg-muted/40">
                    <td className="py-3">{a.patient?.name || '—'}</td>
                    <td className="py-3 mono text-xs">{a.patient?.wysh_id}</td>
                    <td className="py-3 mono text-xs">{new Date(a.scheduled_at).toLocaleString()}</td>
                    <td className="py-3"><span className="text-xs px-2 py-1 border border-border">{a.mode}</span></td>
                  </tr>
                ))}
                {appts.length === 0 && (
                  <tr><td colSpan="4" className="py-6 text-center text-muted-foreground text-sm">No scheduled patients</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="col-span-12 lg:col-span-4 space-y-4">
            <div className="bento-cell p-6">
              <h3 className="font-outfit text-lg mb-4 flex items-center gap-2"><Search className="w-4 h-4" /> WyshID lookup</h3>
              <form onSubmit={doLookup} className="space-y-3">
                <input value={lookup} onChange={(e) => setLookup(e.target.value)} placeholder="WYSH-XXXX-XXXX"
                  data-testid="doctor-wyshid-input"
                  className="w-full px-3 py-2 mono text-sm border border-border bg-card focus:outline-none focus:border-foreground" />
                <button data-testid="doctor-wyshid-lookup-btn" className="btn-sharp bg-slateink text-bone px-4 py-2 text-sm w-full">Lookup</button>
              </form>
              {lookupResult && (
                <div className="mt-4 p-3 border border-coral">
                  <div className="mono text-xs text-coral">{lookupResult.wysh_id}</div>
                  <div className="text-sm mt-1">{lookupResult.user?.name}</div>
                  <div className="text-xs text-muted-foreground capitalize">{lookupResult.user?.role}</div>
                </div>
              )}
            </div>
            <div className="bento-cell p-6">
              <h3 className="font-outfit text-lg mb-2 flex items-center gap-2"><Calendar className="w-4 h-4" /> Total appointments</h3>
              <div className="font-outfit text-4xl tracking-tighter">{appts.length}</div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
