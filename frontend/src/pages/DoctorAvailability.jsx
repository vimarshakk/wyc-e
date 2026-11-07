import React, { useEffect, useRef, useState } from 'react';
import Nav from '../components/Nav';
import { api } from '../lib/api';
import { toast } from 'sonner';
import { Plus, Trash2, Calendar, Clock } from 'lucide-react';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function DoctorAvailability() {
  const [blocks, setBlocks] = useState([]);
  const [timeOff, setTimeOff] = useState([]);
  const [loadingSchedule, setLoadingSchedule] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [newToff, setNewToff] = useState({ start_at: '', end_at: '', reason: '' });
  const loadSequence = useRef(0);

  const load = async () => {
    const sequence = ++loadSequence.current;
    setLoadingSchedule(true);
    setLoadError('');
    try {
      const [s, t] = await Promise.all([
        api.get('/availability/me'),
        api.get('/availability/time-off/me'),
      ]);
      if (sequence === loadSequence.current) {
        setBlocks(s.data.blocks || []);
        setTimeOff(t.data || []);
      }
      return true;
    } catch {
      if (sequence === loadSequence.current) setLoadError('Your saved schedule could not be loaded. Retry before making changes.');
      return false;
    } finally {
      if (sequence === loadSequence.current) setLoadingSchedule(false);
    }
  };

  useEffect(() => { load(); }, []);

  const addBlock = () => setBlocks((current) => [...current, { day_of_week: 0, start_time: '09:00', end_time: '17:00', slot_minutes: 30 }]);
  const removeBlock = (i) => setBlocks(blocks.filter((_, idx) => idx !== i));
  const updBlock = (i, patch) => setBlocks(blocks.map((b, idx) => idx === i ? { ...b, ...patch } : b));

  const save = async () => {
    setBusy(true);
    try {
      await api.put('/availability/me', { blocks });
      toast.success('Weekly schedule saved');
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Save failed'); }
    finally { setBusy(false); }
  };

  const addTimeOff = async (e) => {
    e.preventDefault();
    if (!newToff.start_at || !newToff.end_at) return;
    try {
      await api.post('/availability/time-off', {
        start_at: new Date(newToff.start_at).toISOString(),
        end_at: new Date(newToff.end_at).toISOString(),
        reason: newToff.reason,
      });
      toast.success('Time off added');
      setNewToff({ start_at: '', end_at: '', reason: '' });
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
  };

  const deleteToff = async (id) => {
    try { await api.delete(`/availability/time-off/${id}`); toast.success('Removed'); await load(); }
    catch { toast.error('Failed'); }
  };

  return (
    <div className="min-h-screen bg-background grain">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">
        <div className="mb-8">
          <div className="micro text-coral mb-3">Availability engine</div>
          <h1 className="font-outfit text-4xl tracking-tighter">Your schedule</h1>
          <p className="text-muted-foreground mt-2">Define your weekly hours. Patients see only generated slots that aren't already booked or blocked.</p>
        </div>

        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-7 bento-cell p-7">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-outfit text-2xl tracking-tight flex items-center gap-2"><Calendar className="w-5 h-5" /> Weekly hours</h2>
              <button onClick={addBlock} disabled={loadingSchedule || Boolean(loadError)} data-testid="add-block-btn" className="btn-sharp border border-foreground px-3 py-1.5 text-xs inline-flex items-center gap-1.5 disabled:opacity-50">
                <Plus className="w-3.5 h-3.5" /> {loadingSchedule ? 'Loading…' : 'Add block'}
              </button>
            </div>
            {loadError && (
              <div role="alert" data-testid="schedule-load-error" className="mb-4 flex items-center justify-between gap-3 border border-destructive px-3 py-2 text-sm text-destructive">
                <span>{loadError}</span>
                <button onClick={load} data-testid="retry-schedule-load-btn" className="shrink-0 underline">Retry</button>
              </div>
            )}
            {blocks.length === 0 ? (
              <div className="text-sm text-muted-foreground py-6">No availability set yet. Click "Add block" to start.</div>
            ) : (
              <div className="space-y-3" data-testid="schedule-blocks">
                {blocks.map((b, i) => (
                  <div key={i} className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-center border border-border p-3">
                    <select value={b.day_of_week} onChange={(e) => updBlock(i, { day_of_week: parseInt(e.target.value) })}
                      data-testid={`block-${i}-day`}
                      className="sm:col-span-3 px-2 py-2 border border-border bg-card text-sm">
                      {DAYS.map((d, idx) => <option key={idx} value={idx}>{d}</option>)}
                    </select>
                    <input type="time" value={b.start_time} onChange={(e) => updBlock(i, { start_time: e.target.value })}
                      data-testid={`block-${i}-start`}
                      className="sm:col-span-3 px-2 py-2 border border-border bg-card text-sm mono" />
                    <input type="time" value={b.end_time} onChange={(e) => updBlock(i, { end_time: e.target.value })}
                      data-testid={`block-${i}-end`}
                      className="sm:col-span-3 px-2 py-2 border border-border bg-card text-sm mono" />
                    <select value={b.slot_minutes} onChange={(e) => updBlock(i, { slot_minutes: parseInt(e.target.value) })}
                      data-testid={`block-${i}-slot`}
                      className="sm:col-span-2 px-2 py-2 border border-border bg-card text-sm">
                      <option value="15">15m</option>
                      <option value="20">20m</option>
                      <option value="30">30m</option>
                      <option value="45">45m</option>
                      <option value="60">60m</option>
                    </select>
                    <button onClick={() => removeBlock(i)} data-testid={`block-${i}-remove`}
                      aria-label="Remove weekly block" className="sm:col-span-1 p-2 hover:bg-destructive hover:text-destructive-foreground transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <button onClick={save} disabled={busy || loadingSchedule || Boolean(loadError)} data-testid="save-schedule-btn"
              className="btn-sharp w-full mt-5 bg-slateink text-bone py-3 font-medium disabled:opacity-60">
              {busy ? 'Saving…' : 'Save weekly schedule'}
            </button>
          </div>

          <div className="col-span-12 lg:col-span-5 bento-cell p-7">
            <h2 className="font-outfit text-2xl tracking-tight mb-5 flex items-center gap-2"><Clock className="w-5 h-5" /> Time off</h2>
            <form onSubmit={addTimeOff} className="space-y-2 mb-5">
              <label htmlFor="timeoff-start" className="micro text-muted-foreground">From</label>
              <input id="timeoff-start" type="datetime-local" required value={newToff.start_at} onChange={(e) => setNewToff({ ...newToff, start_at: e.target.value })}
                data-testid="timeoff-start"
                className="w-full px-3 py-2 border border-border bg-card text-sm" />
              <label htmlFor="timeoff-end" className="micro text-muted-foreground">To</label>
              <input id="timeoff-end" type="datetime-local" required value={newToff.end_at} onChange={(e) => setNewToff({ ...newToff, end_at: e.target.value })}
                data-testid="timeoff-end"
                className="w-full px-3 py-2 border border-border bg-card text-sm" />
              <input value={newToff.reason} onChange={(e) => setNewToff({ ...newToff, reason: e.target.value })}
                data-testid="timeoff-reason"
                placeholder="Reason (optional)" className="w-full px-3 py-2 border border-border bg-card text-sm" />
              <button data-testid="add-timeoff-btn" className="btn-sharp w-full bg-slateink text-bone py-2 text-sm">Add time off</button>
            </form>
            <ul className="space-y-2" data-testid="timeoff-list">
              {timeOff.map(t => (
                <li key={t.time_off_id} className="border border-border p-3 flex items-center justify-between">
                  <div className="min-w-0">
                    <div className="mono text-xs">{new Date(t.start_at).toLocaleString()} → {new Date(t.end_at).toLocaleString()}</div>
                    {t.reason && <div className="text-xs text-muted-foreground mt-1 truncate">{t.reason}</div>}
                  </div>
                  <button onClick={() => deleteToff(t.time_off_id)} data-testid={`timeoff-delete-${t.time_off_id}`} aria-label="Remove time off" className="p-1.5 hover:bg-destructive hover:text-destructive-foreground transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </li>
              ))}
              {timeOff.length === 0 && <li className="text-xs text-muted-foreground">No blocks scheduled.</li>}
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}
