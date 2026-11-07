import React, { useEffect, useRef, useState } from 'react';
import Nav from '../components/Nav';
import { api } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { Calendar, Loader2 } from 'lucide-react';

export default function Appointments() {
  const { user } = useAuth();
  const [doctors, setDoctors] = useState([]);
  const [appts, setAppts] = useState([]);
  const [doctor_id, setDoctorId] = useState('');
  const [date, setDate] = useState('');
  const [slots, setSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [picked, setPicked] = useState('');
  const [mode, setMode] = useState('telemedicine');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState('');
  const slotRequestSequence = useRef(0);

  const reload = async () => {
    try {
      const { data } = await api.get('/appointments/mine');
      setAppts(data);
    } catch {
      setLoadError('Appointments could not be loaded. Please try again.');
    }
  };

  useEffect(() => {
    setLoadError('');
    if (user?.role === 'patient') api.get('/appointments/doctors').then(r => setDoctors(r.data)).catch(() => setLoadError('Doctors could not be loaded. Please try again.'));
    reload();
  }, [user?.role]);

  useEffect(() => {
    const sequence = ++slotRequestSequence.current;
    setLoadError('');
    setPicked(''); setSlots([]);
    if (!doctor_id || !date) return;
    setLoadingSlots(true);
    api.get(`/availability/${doctor_id}/slots`, { params: { date } })
      .then(r => { if (sequence === slotRequestSequence.current) setSlots(r.data.slots || []); })
      .catch(() => { if (sequence === slotRequestSequence.current) setLoadError('Available slots could not be loaded. Please choose another date or retry.'); })
      .finally(() => { if (sequence === slotRequestSequence.current) setLoadingSlots(false); });
  }, [doctor_id, date]);

  const book = async () => {
    if (!picked) return;
    setBusy(true);
    try {
      await api.post('/appointments', { doctor_id, scheduled_at: picked, mode, reason });
      toast.success('Appointment booked');
      setPicked(''); setDate(''); setDoctorId(''); setReason('');
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Booking failed'); }
    finally { setBusy(false); }
  };

  const cancel = async (id) => {
    try { await api.post(`/appointments/${id}/cancel`); toast.success('Cancelled'); reload(); }
    catch { toast.error('Cancel failed'); }
  };

  const today = new Date().toISOString().split('T')[0];

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
        {loadError && <div role="alert" data-testid="appointments-load-error" className="mb-6 border border-destructive px-4 py-3 text-sm text-destructive">{loadError}</div>}

        <div className="grid grid-cols-12 gap-6">
          {user?.role === 'patient' && (
            <div className="col-span-12 lg:col-span-5 bento-cell p-7">
              <h2 className="font-outfit text-2xl mb-5 flex items-center gap-2"><Calendar className="w-5 h-5" /> Book new</h2>

              <div className="space-y-4">
                <div>
                  <label htmlFor="appt-doctor" className="micro text-muted-foreground">Doctor</label>
                  <select id="appt-doctor" value={doctor_id} onChange={(e) => setDoctorId(e.target.value)}
                    data-testid="appt-doctor-select"
                    className="w-full mt-2 px-3 py-2.5 border border-border bg-card focus:outline-none focus:border-foreground">
                    <option value="">Select doctor…</option>
                    {doctors.map(d => (
                      <option key={d.user_id} value={d.user_id}>{d.name} {d.specialty ? `· ${d.specialty}` : ''}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="appt-date" className="micro text-muted-foreground">Date</label>
                  <input id="appt-date" type="date" min={today} value={date} onChange={(e) => setDate(e.target.value)}
                    data-testid="appt-date"
                    className="w-full mt-2 px-3 py-2.5 border border-border bg-card focus:outline-none focus:border-foreground" />
                </div>

                {doctor_id && date && (
                  <div>
                    <label className="micro text-muted-foreground">Available slots</label>
                    {loadingSlots ? (
                      <div className="mt-3 text-sm text-muted-foreground flex items-center gap-2">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading…
                      </div>
                    ) : slots.length === 0 ? (
                      <div className="mt-3 text-sm text-muted-foreground">No slots available on this date. Try another day.</div>
                    ) : (
                      <div className="mt-3 grid grid-cols-3 gap-2" data-testid="slot-grid">
                        {slots.map(s => {
                          const lbl = new Date(s).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                          const active = picked === s;
                          return (
                            <button key={s} onClick={() => setPicked(s)}
                              data-testid={`slot-${lbl}`}
                              className={`mono text-xs py-2 border transition-colors ${active ? 'bg-coral text-white border-coral' : 'border-border hover:border-foreground'}`}>
                              {lbl}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {picked && (
                  <>
                    <div>
                      <label className="micro text-muted-foreground">Mode</label>
                      <div className="grid grid-cols-2 gap-2 mt-2">
                        {['telemedicine', 'in_person'].map(m => (
                          <button type="button" key={m} onClick={() => setMode(m)}
                            data-testid={`appt-mode-${m}`}
                            className={`py-2 text-sm capitalize border ${mode === m ? 'bg-slateink text-bone border-slateink' : 'border-border hover:bg-muted'}`}>
                            {m.replace('_', ' ')}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="micro text-muted-foreground">Reason</label>
                      <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows="2"
                        data-testid="appt-reason"
                        className="w-full mt-2 px-3 py-2.5 border border-border bg-card focus:outline-none focus:border-foreground" />
                    </div>
                    <button onClick={book} disabled={busy} data-testid="appt-book-btn"
                      className="btn-sharp w-full bg-slateink text-bone py-3 font-medium disabled:opacity-60">
                      {busy ? 'Booking…' : `Confirm ${new Date(picked).toLocaleString()}`}
                    </button>
                  </>
                )}
              </div>
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
