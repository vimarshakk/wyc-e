import React, { useEffect, useState } from 'react';
import Nav from '../components/Nav';
import { api } from '../lib/api';

export default function Records() {
  const [items, setItems] = useState([]);
  const [pres, setPres] = useState([]);

  useEffect(() => {
    api.get('/records').then(r => setItems(r.data)).catch(() => {});
    api.get('/ocr/prescriptions').then(r => setPres(r.data)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-background grain">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">
        <div className="mb-8">
          <div className="micro text-coral mb-3">Records</div>
          <h1 className="font-outfit text-4xl tracking-tighter">Your health record</h1>
        </div>
        <div className="bento-cell p-7" data-testid="records-list">
          <h2 className="font-outfit text-2xl mb-5">OCR Prescriptions ({pres.length})</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 micro text-muted-foreground">Date</th>
                <th className="text-left py-2 micro text-muted-foreground">Doctor</th>
                <th className="text-left py-2 micro text-muted-foreground">Medications</th>
                <th className="text-left py-2 micro text-muted-foreground">Confidence</th>
                <th className="text-left py-2 micro text-muted-foreground">Status</th>
              </tr>
            </thead>
            <tbody>
              {pres.map(p => (
                <tr key={p.prescription_id} className="border-b border-border hover:bg-muted/40">
                  <td className="py-3 mono text-xs">{new Date(p.created_at).toLocaleDateString()}</td>
                  <td className="py-3">{p.extracted?.doctor_name || '—'}</td>
                  <td className="py-3">{p.extracted?.medications?.length || 0} extracted</td>
                  <td className="py-3 mono text-xs text-coral">{(p.extracted?.overall_confidence ?? 0).toFixed(2)}</td>
                  <td className="py-3"><span className="text-xs px-2 py-1 border border-border">{p.status}</span></td>
                </tr>
              ))}
              {pres.length === 0 && (
                <tr><td colSpan="5" className="py-6 text-center text-muted-foreground text-sm">No prescriptions yet. Scan one to build your record.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="bento-cell p-7 mt-6">
          <h2 className="font-outfit text-2xl mb-5">Other records ({items.length})</h2>
          {items.length === 0 ? (
            <div className="text-sm text-muted-foreground">No other records.</div>
          ) : (
            <ul className="space-y-3">
              {items.map(r => (
                <li key={r.record_id} className="border-b border-border pb-3 flex items-center justify-between">
                  <div>
                    <div className="text-sm">{r.title}</div>
                    <div className="micro text-muted-foreground mt-1">{r.record_type}</div>
                  </div>
                  <div className="mono text-xs text-muted-foreground">{new Date(r.created_at).toLocaleDateString()}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
