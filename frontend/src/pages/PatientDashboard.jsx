import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Nav from '../components/Nav';
import { api } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { FileScan, Calendar, Pill, Activity, ArrowUpRight, Sparkles } from 'lucide-react';

export default function PatientDashboard() {
  const { user } = useAuth();
  const [timeline, setTimeline] = useState([]);
  const [appts, setAppts] = useState([]);
  const [pres, setPres] = useState([]);

  useEffect(() => {
    (async () => {
      const [t, a, p] = await Promise.all([
        api.get('/records/timeline').catch(() => ({ data: [] })),
        api.get('/appointments/mine').catch(() => ({ data: [] })),
        api.get('/ocr/prescriptions').catch(() => ({ data: [] })),
      ]);
      setTimeline(t.data); setAppts(a.data); setPres(p.data);
    })();
  }, []);

  return (
    <div className="min-h-screen bg-background grain">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">
        {/* Hero strip */}
        <div className="grid grid-cols-12 gap-4 mb-6">
          <div className="col-span-12 lg:col-span-8 bento-cell p-8">
            <div className="micro text-coral mb-3">Patient overview</div>
            <h1 className="font-outfit text-4xl tracking-tighter">Welcome, {user?.name?.split(' ')[0]}</h1>
            <p className="text-muted-foreground mt-3">Your longitudinal health record · {timeline.length} indexed events</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/app/ocr" data-testid="patient-cta-ocr" className="btn-sharp bg-slateink text-bone px-5 py-2.5 inline-flex items-center gap-2 text-sm font-medium">
                <FileScan className="w-4 h-4" /> Scan Prescription
              </Link>
              <Link to="/app/appointments" data-testid="patient-cta-book" className="btn-sharp border border-foreground px-5 py-2.5 inline-flex items-center gap-2 text-sm">
                <Calendar className="w-4 h-4" /> Book Appointment
              </Link>
            </div>
          </div>
          <div className="col-span-12 lg:col-span-4 bento-cell p-6 bg-slateink text-bone">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-coral" />
              <span className="micro text-coral">WyshID</span>
            </div>
            <div className="mono text-2xl tracking-tight">{user?.wysh_id}</div>
            <div className="text-xs text-bone/60 mt-2">Verified · Trust score 50</div>
            <Link to="/app/wyshid" data-testid="patient-wyshid-link" className="micro text-coral mt-6 inline-flex items-center gap-1 hover:gap-2 transition-all">
              View identity card <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Kpi icon={Pill} label="Prescriptions" value={pres.length} />
          <Kpi icon={Calendar} label="Appointments" value={appts.length} />
          <Kpi icon={Activity} label="Records" value={timeline.length} />
          <Kpi icon={FileScan} label="OCR runs" value={pres.length} />
        </div>

        {/* Timeline + sidebar */}
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8 bento-cell p-7">
            <div className="flex justify-between items-center mb-6">
              <h2 className="font-outfit text-2xl tracking-tight">Longitudinal timeline</h2>
              <span className="mono text-xs text-muted-foreground">{timeline.length} EVENTS</span>
            </div>
            {timeline.length === 0 ? (
              <Empty msg="No events yet. Scan a prescription to begin your record." />
            ) : (
              <ul className="relative pl-8 timeline-rail space-y-5" data-testid="patient-timeline">
                {timeline.slice(0, 10).map((e) => (
                  <li key={e.id} className="relative">
                    <span className="absolute -left-8 top-1.5 w-3 h-3 bg-coral border-2 border-background"></span>
                    <div className="flex items-baseline justify-between gap-3">
                      <div>
                        <div className="micro text-muted-foreground">{e.kind.replace('_', ' ')}</div>
                        <div className="text-base mt-1">{e.title}</div>
                        {e.summary && <div className="text-sm text-muted-foreground mt-0.5">{e.summary}</div>}
                      </div>
                      <div className="mono text-xs text-muted-foreground whitespace-nowrap">
                        {new Date(e.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="col-span-12 lg:col-span-4 space-y-4">
            <div className="bento-cell p-6">
              <h3 className="font-outfit text-lg mb-4">Upcoming</h3>
              {appts.filter(a => a.status === 'scheduled').slice(0, 3).map(a => (
                <div key={a.appointment_id} className="border-b border-border last:border-0 py-3">
                  <div className="text-sm">{a.doctor?.name || 'Doctor'}</div>
                  <div className="mono text-xs text-muted-foreground mt-1">
                    {new Date(a.scheduled_at).toLocaleString()}
                  </div>
                </div>
              ))}
              {appts.length === 0 && <Empty msg="No appointments yet" small />}
            </div>
            <div className="bento-cell p-6">
              <h3 className="font-outfit text-lg mb-2">AI Insight</h3>
              <div className="micro text-coral mb-3">PROACTIVE</div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Upload your latest prescription and we'll automatically index medications, dosage and reminders into your record.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function Kpi({ icon: Icon, label, value }) {
  return (
    <div className="bento-cell p-5">
      <Icon className="w-4 h-4 text-coral mb-3" />
      <div className="font-outfit text-3xl">{value}</div>
      <div className="micro text-muted-foreground mt-1">{label}</div>
    </div>
  );
}

function Empty({ msg, small }) {
  return (
    <div className={`text-muted-foreground ${small ? 'text-xs' : 'text-sm'} py-4`}>{msg}</div>
  );
}
