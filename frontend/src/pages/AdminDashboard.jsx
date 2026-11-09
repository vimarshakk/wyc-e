import React, { useEffect, useState } from 'react';
import Nav from '../components/Nav';
import { api } from '../lib/api';
import { Activity, Users, FileScan, Calendar, Shield } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminDashboard() {
  const [stats, setStats] = useState({});
  const [users, setUsers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [calendar, setCalendar] = useState({ connected: false });
  const [pending, setPending] = useState([]);

  useEffect(() => {
    (async () => {
      const [s, u, a, calendarStatus, pendingPartners] = await Promise.all([
        api.get('/admin/stats').catch(() => ({ data: {} })),
        api.get('/admin/users').catch(() => ({ data: [] })),
        api.get('/admin/audit?limit=20').catch(() => ({ data: [] })),
        api.get('/calendar/status').catch(() => ({ data: { connected: false } })),
        api.get('/auth/partners/pending').catch(() => ({ data: [] })),
      ]);
      setStats(s.data); setUsers(u.data); setAudit(a.data); setCalendar(calendarStatus.data || { connected: false }); setPending(pendingPartners.data || []);
    })();
  }, []);

  const connectCalendar = async () => {
    try { const { data } = await api.get('/calendar/connect'); window.location.assign(data.authorization_url); }
    catch (error) { toast.error(error?.response?.data?.detail || 'Calendar connection could not start'); }
  };
  const decide = async (id, decision) => { try { await api.post(`/auth/partners/${id}/verification`, { decision }); setPending(pending.filter((item) => item.user_id !== id)); toast.success(`Account ${decision.toLowerCase()}`); } catch { toast.error('Decision could not be saved'); } };

  return (
    <div className="min-h-screen bg-background grain">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">
        <div className="mb-8">
          <div className="micro text-coral mb-3">Control Room</div>
          <h1 className="font-outfit text-4xl tracking-tighter">Platform telemetry</h1>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
          <Stat icon={Users} label="Total users" value={stats.users_total} />
          <Stat icon={Users} label="Patients" value={stats.patients} />
          <Stat icon={Activity} label="Doctors" value={stats.doctors} />
          <Stat icon={Shield} label="Verified WyshIDs" value={stats.wysh_ids_verified} />
          <Stat icon={FileScan} label="OCR runs" value={stats.prescriptions_ocr} />
          <Stat icon={Calendar} label="Scheduled" value={stats.appointments_scheduled} />
        </div>

        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 bento-cell p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4" data-testid="calendar-organizer-card">
            <div><div className="micro text-coral">Google Calendar organizer</div><div data-testid="calendar-organizer-status" className="text-sm mt-1">{calendar.connected ? `Connected: ${calendar.organizer_email}` : 'Connect one clinic organizer to create Google Meet links.'}</div></div>
            <button onClick={connectCalendar} data-testid="connect-google-calendar-btn" className="btn-sharp border border-foreground px-4 py-2.5 text-sm">{calendar.connected ? 'Reconnect organizer' : 'Connect Google Calendar'}</button>
          </div>
          <div className="col-span-12 bento-cell p-7" data-testid="partner-verification-queue"><h2 className="font-outfit text-2xl mb-4">Verification queue</h2><div className="space-y-3">{pending.map((item) => <div key={item.user_id} className="border border-border p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><div className="text-sm font-medium">{item.name} · {item.organization_name}</div><div className="mono text-xs text-muted-foreground mt-1">{item.role} · {item.registration_number} · {item.registration_jurisdiction || 'jurisdiction not supplied'}</div></div><div className="flex gap-2"><button onClick={() => decide(item.user_id, 'REJECTED')} data-testid={`reject-verification-${item.user_id}`} className="border border-foreground px-3 py-2 text-xs">Reject</button><button onClick={() => decide(item.user_id, 'APPROVED')} data-testid={`approve-verification-${item.user_id}`} className="btn-sharp bg-slateink text-bone px-3 py-2 text-xs">Approve</button></div></div>)}{pending.length === 0 && <p data-testid="verification-empty-state" className="text-sm text-muted-foreground">No professional or partner registrations are waiting.</p>}</div></div>
          <div className="col-span-12 lg:col-span-7 bento-cell p-7">
            <h2 className="font-outfit text-2xl tracking-tight mb-4">Users</h2>
            <table className="w-full text-sm" data-testid="admin-users-table">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 micro text-muted-foreground">Name</th>
                  <th className="text-left py-2 micro text-muted-foreground">WyshID</th>
                  <th className="text-left py-2 micro text-muted-foreground">Role</th>
                  <th className="text-left py-2 micro text-muted-foreground">Joined</th>
                </tr>
              </thead>
              <tbody>
                {users.slice(0, 15).map(u => (
                  <tr key={u.user_id} className="border-b border-border hover:bg-muted/40">
                    <td className="py-3">{u.name}<div className="text-xs text-muted-foreground">{u.email}</div></td>
                    <td className="py-3 mono text-xs">{u.wysh_id}</td>
                    <td className="py-3 capitalize"><span className="text-xs px-2 py-1 border border-border">{u.role}</span></td>
                    <td className="py-3 mono text-xs">{new Date(u.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="col-span-12 lg:col-span-5 bento-cell p-7">
            <h2 className="font-outfit text-2xl tracking-tight mb-4">Audit trail</h2>
            <ul className="space-y-3" data-testid="admin-audit-log">
              {audit.map(a => (
                <li key={a.audit_id} className="flex items-start justify-between gap-3 border-b border-border pb-3 last:border-0">
                  <div className="flex-1 min-w-0">
                    <div className="mono text-xs text-coral">{a.action}</div>
                    <div className="text-xs text-muted-foreground mt-1 truncate">{a.resource} · {a.resource_id}</div>
                  </div>
                  <div className="mono text-[10px] text-muted-foreground whitespace-nowrap">
                    {new Date(a.created_at).toLocaleTimeString()}
                  </div>
                </li>
              ))}
              {audit.length === 0 && <li className="text-sm text-muted-foreground">No audit events yet</li>}
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="bento-cell p-5">
      <Icon className="w-4 h-4 text-coral mb-3" />
      <div className="font-outfit text-3xl tracking-tighter">{value ?? 0}</div>
      <div className="micro text-muted-foreground mt-1">{label}</div>
    </div>
  );
}
