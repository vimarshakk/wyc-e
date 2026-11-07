import React, { useEffect, useState } from 'react';
import Nav from '../components/Nav';
import { api } from '../lib/api';

export default function Records() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    api.get('/records/timeline').then(r => setItems(r.data)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-background grain">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">
        <div className="mb-8">
          <div className="micro text-coral mb-3">Records</div>
          <h1 data-testid="records-heading" className="font-outfit text-4xl tracking-tighter">Your health record</h1>
        </div>
        <div className="bento-cell p-7" data-testid="records-list">
          <h2 className="font-outfit text-2xl mb-5">Longitudinal timeline ({items.length})</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 micro text-muted-foreground">Date</th>
                <th className="text-left py-2 micro text-muted-foreground">Event</th>
                <th className="text-left py-2 micro text-muted-foreground">Summary</th>
                <th className="text-left py-2 micro text-muted-foreground">Type</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={`${item.kind}-${item.id}`} className="border-b border-border hover:bg-muted/40">
                  <td className="py-3 mono text-xs">{new Date(item.created_at).toLocaleDateString()}</td>
                  <td className="py-3">{item.title}</td>
                  <td className="py-3 text-muted-foreground">{item.summary || '—'}</td>
                  <td className="py-3"><span className="text-xs px-2 py-1 border border-border">{item.kind}</span></td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan="4" className="py-6 text-center text-muted-foreground text-sm">No reviewed records yet. Add a document to start your timeline.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
