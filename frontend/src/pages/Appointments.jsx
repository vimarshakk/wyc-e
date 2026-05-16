import React, { useEffect, useState } from 'react';
import Nav from '../components/Nav';
import { api } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { Calendar } from 'lucide-react';

export default function Appointments() {
  const { user } = useAuth();
  const [doctors, setDoctors] = useState([]);
  const [appts, setAppts] = useState([]);
  const [form, setForm] = useState({ doctor_id: '', scheduled_at: '', mode: 'telemedicine', reason: '' });
  const [busy, setBusy] = useState(false);

  const reload = async () => {
    const { data } = await api.get('/appointments/mine');
    setAppts(data);
  };

  useEffect(() => {
    if (user?.role === 'patient') api.get('/appointments/doctors').then(r => setDoctors(r.data)).catch(() => {});
    reload();
  }, [user?.role]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.doctor_id || !form.scheduled_at) return;
    setBusy(true);
    try {
      await api.post('/appointments', { ...form, scheduled_at: new Date(form.scheduled_at).toISOString() });
      toast.success('Appointment booked');
      setForm({ doctor_id: '', scheduled_at: '', mode: 'telemedicine', reason: '' });
      reload();
    } catch (e) { toast.error('Booking failed'); }
    finally { setBusy(false); }
  };

  const cancel = async (id) => {
    try { await api.post(`/appointments/${id}/cancel`); toast.success('Cancelled'); reload(); }
    catch { toast.error('Cancel failed'); }
  };

  return (
    <div className="min-h-screen bg-background grain">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">
        <div className="mb-8">
          <div className="micro text-coral mb-3">Appointments</div>
          <h1 className="font-outfit text-4xl tracking-tighter">
            {user?.role === 'doctor' ? 'Your schedule' : 'Book & manage appointments'}
          </h1>
        </div>

        <div className="grid grid-cols-12 gap-6">
          {user?.role === 'patient' && (
            <div className="col-span-12 lg:col-span-5 bento-cell p-7">
              <h2 className="font-outfit text-2xl mb-5 flex items-center gap-2"><Calendar className="w-5 h-5" /> Book new</h2>
              <form onSubmit={submit} className="space-y-3">
                <div>
                  <label className="micro text-muted-foreground">Doctor</label>
                  <select required value={form.doctor_id} onChange={(e) => setForm({ ...form, doctor_id: e.target.value })}
                    data-testid="appt-doctor-select"
                    className="w-full mt-2 px-3 py-2.5 border border-border bg-card focus:outline-none focus:border-foreground">
                    <option value="">Select…</option>
                    {doctors.map(d => (
                      <option key={d.user_id} value={d.user_id}>{d.name} {d.specialty ? `· ${d.specialty}` : ''}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="micro text-muted-foreground">Date & time</label>
                  <input required type="datetime-local" value={form.scheduled_at} onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}
                    data-testid="appt-datetime"
                    className="w-full mt-2 px-3 py-2.5 border border-border bg-card focus:outline-none focus:border-foreground" />
                </div>
                <div>
                  <label className="micro text-muted-foreground">Mode</label>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {['telemedicine', 'in_person'].map(m => (
                      <button type="button" key={m} onClick={() => setForm({ ...form, mode: m })}
                        className={`py-2 text-sm capitalize border ${form.mode === m ? 'bg-slateink text-bone border-slateink' : 'border-border hover:bg-muted'}`}>
                        {m.replace('_', ' ')}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="micro text-muted-foreground">Reason</label>
                  <textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}
                    rows="2" data-testid="appt-reason"
                    className="w-full mt-2 px-3 py-2.5 border border-border bg-card focus:outline-none focus:border-foreground" />
                </div>
                <button disabled={busy} data-testid="appt-book-btn"
                  className="btn-sharp w-full bg-slateink text-bone py-3 font-medium disabled:opacity-60">
                  {busy ? 'Booking…' : 'Book appointment'}
                </button>
              </form>
            </div>
          )}

          <div className={`col-span-12 ${user?.role === 'patient' ? 'lg:col-span-7' : ''} bento-cell p-7`}>
            <h2 className="font-outfit text-2xl mb-5">Scheduled</h2>
            <ul className="space-y-3" data-testid="appt-list">
              {appts.map(a => (
                <li key={a.appointment_id} className="border border-border p-4 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm">
                      {user?.role === 'doctor' ? a.patient?.name : a.doctor?.name}
                      <span className="ml-2 mono text-xs text-muted-foreground">{user?.role === 'doctor' ? a.patient?.wysh_id : a.doctor?.wysh_id}</span>
                    </div>
                    <div className="mono text-xs text-muted-foreground mt-1">{new Date(a.scheduled_at).toLocaleString()} · {a.mode}</div>
                    {a.reason && <div className="text-xs mt-1 text-muted-foreground">{a.reason}</div>}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-xs px-2 py-1 border ${a.status === 'cancelled' ? 'border-destructive text-destructive' : 'border-border'}`}>
                      {a.status}
                    </span>
                    {a.status === 'scheduled' && (
                      <button onClick={() => cancel(a.appointment_id)} data-testid={`appt-cancel-${a.appointment_id}`}
                        className="text-xs underline text-muted-foreground hover:text-destructive">Cancel</button>
                    )}
                  </div>
                </li>
              ))}
              {appts.length === 0 && <li className="text-sm text-muted-foreground">No appointments yet.</li>}
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}
