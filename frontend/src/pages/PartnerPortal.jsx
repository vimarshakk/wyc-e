import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import Nav from '../components/Nav';
import { useAuth } from '../contexts/AuthContext';

const content = { lab: ['Lab operations', 'Reports assigned through patient consent will appear here.'], pharmacy: ['Pharmacy fulfilment', 'Consent-linked prescriptions and fulfilment tasks will appear here.'], insurer: ['Insurer workspace', 'Consent-bound eligibility, pre-authorisation, and claims tasks will appear here.'], partner: ['Partner workspace', 'Only consent-scoped integration tasks will appear here.'] };

export default function PartnerPortal() {
  const { user } = useAuth(); const [title, description] = content[user?.role] || content.partner; const [tasks, setTasks] = useState([]);
  useEffect(() => { api.get('/partner-tasks/mine').then((r) => setTasks(r.data)).catch(() => setTasks([])); }, []);
  return <div className="min-h-screen bg-background grain"><Nav /><main className="max-w-[1100px] mx-auto px-6 lg:px-10 py-10"><div className="micro text-coral mb-3">{user?.organization_name || 'WyshCare partner'}</div><h1 data-testid="partner-portal-heading" className="font-outfit text-4xl tracking-tighter">{title}</h1><section data-testid="partner-consent-gate" className="bento-cell p-7 mt-8"><h2 className="font-outfit text-2xl">Consent-protected queue</h2><p className="text-muted-foreground mt-3">{description}</p><div data-testid="partner-task-list" className="mt-6 space-y-2">{tasks.map((task) => <div key={task.task_id} className="border border-border p-3 mono text-xs">{task.task_type} · {task.status}</div>)}{tasks.length === 0 && <p data-testid="partner-empty-state" className="mono text-xs border border-border p-4">No patient information is available until a valid consent grants this organization a specific task.</p>}</div></section></main></div>;
}