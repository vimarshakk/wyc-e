import React, { useEffect, useRef, useState } from 'react';
import { FileScan, FileText, Loader2, ShieldCheck, UploadCloud } from 'lucide-react';
import { toast } from 'sonner';
import Nav from '../components/Nav';
import { api } from '../lib/api';

const labels = { prescription: 'Prescription', lab_report: 'Lab report' };

export default function Documents() {
  const [kind, setKind] = useState('prescription');
  const [file, setFile] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState(null);
  const [reviewText, setReviewText] = useState('');
  const [busy, setBusy] = useState(false);
  const input = useRef(null);
  const load = async () => { try { const { data } = await api.get('/ocr/documents'); setDocuments(data); } catch { toast.error('Documents could not be loaded'); } };
  useEffect(() => { load(); }, []);
  const select = (doc) => { setSelected(doc); setReviewText(JSON.stringify(doc.reviewed_extraction || doc.extracted || {}, null, 2)); };
  const download = async () => { try { const response = await api.get(`/ocr/files/${selected.file_id}`, { responseType: 'blob' }); const url = URL.createObjectURL(response.data); window.open(url, '_blank', 'noopener,noreferrer'); setTimeout(() => URL.revokeObjectURL(url), 60000); } catch { toast.error('Source document could not be opened'); } };
  const upload = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData(); form.append('file', file);
      const { data } = await api.post(`/ocr/documents/${kind}`, form, { headers: { 'Content-Type': 'multipart/form-data' } });
      select(data); setFile(null); await load();
      toast.success(data.extraction_status === 'complete' ? 'Extraction ready for review' : 'Document stored securely; review is required');
    } catch (error) { toast.error(error?.response?.data?.detail || 'Upload failed'); } finally { setBusy(false); }
  };
  const review = async (decision) => {
    try {
      const extracted = JSON.parse(reviewText);
      const { data } = await api.post(`/ocr/documents/${selected.document_id}/review`, { decision, extracted });
      select(data); await load(); toast.success(decision === 'approved' ? 'Committed to your EMR' : 'Document kept out of the record');
    } catch (error) { toast.error(error instanceof SyntaxError ? 'Review data must be valid JSON' : (error?.response?.data?.detail || 'Review failed')); }
  };
  return <div className="min-h-screen bg-background grain"><Nav /><main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">
    <div className="mb-9"><div className="micro text-coral mb-3">Clinical document review</div><h1 data-testid="documents-heading" className="font-outfit text-4xl tracking-tighter">Review before it becomes record</h1><p className="text-muted-foreground mt-2">Securely store a prescription or lab report, verify the extraction, then commit only the corrected result.</p></div>
    <div className="grid grid-cols-12 gap-6"><section className="col-span-12 lg:col-span-4 bento-cell p-7">
      <div className="flex items-center gap-2 mb-5"><UploadCloud className="w-5 h-5 text-coral" /><h2 className="font-outfit text-2xl">Secure intake</h2></div>
      <label htmlFor="document-kind" className="micro text-muted-foreground">Document type</label><select id="document-kind" value={kind} onChange={(e) => setKind(e.target.value)} data-testid="document-kind-select" className="w-full mt-2 mb-4 border border-border bg-card px-3 py-2.5"><option value="prescription">Prescription</option><option value="lab_report">Lab report</option></select>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp,application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="document-file-input" className="hidden" />
      <button onClick={() => input.current?.click()} data-testid="choose-document-btn" className="w-full border border-dashed border-border px-4 py-8 text-sm hover:border-foreground transition-colors"><FileText className="w-6 h-6 text-coral mx-auto mb-3" />{file ? file.name : 'Choose image or PDF'}</button>
      <p data-testid="document-upload-limits" className="mono text-xs text-muted-foreground mt-3">JPEG · PNG · WEBP · PDF · 20MB max</p>
      <button onClick={upload} disabled={!file || busy} data-testid="upload-document-btn" className="btn-sharp w-full mt-5 bg-slateink text-bone py-3 disabled:opacity-50">{busy ? <span className="inline-flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Extracting</span> : `Extract ${labels[kind]}`}</button>
    </section>
    <section className="col-span-12 lg:col-span-4 bento-cell p-7"><div className="flex items-center gap-2 mb-5"><ShieldCheck className="w-5 h-5 text-coral" /><h2 className="font-outfit text-2xl">Review queue</h2></div><div className="space-y-2" data-testid="document-review-list">{documents.map((doc) => <button key={doc.document_id} onClick={() => select(doc)} data-testid={`document-row-${doc.document_id}`} className={`w-full text-left border p-3 transition-colors ${selected?.document_id === doc.document_id ? 'border-coral' : 'border-border hover:border-foreground'}`}><div className="flex justify-between gap-2"><span className="text-sm font-medium">{labels[doc.document_kind]}</span><span className="mono text-xs text-coral">{doc.review_state}</span></div><div className="mono text-xs text-muted-foreground mt-1">{new Date(doc.created_at).toLocaleString()}</div></button>)}{documents.length === 0 && <p data-testid="document-empty-state" className="text-sm text-muted-foreground py-8">No clinical documents yet.</p>}</div></section>
    <section className="col-span-12 lg:col-span-4 bento-cell p-7">{selected ? <><div className="flex justify-between gap-3 mb-5"><div><div className="micro text-coral">{labels[selected.document_kind]}</div><h2 className="font-outfit text-2xl">Extraction review</h2></div><span data-testid="document-confidence" className="mono text-xs">{((selected.extracted?.overall_confidence || 0) * 100).toFixed(0)}%</span></div><button onClick={download} data-testid="download-source-document-btn" className="w-full border border-foreground py-2 text-xs mb-3">Open source document</button><textarea value={reviewText} onChange={(e) => setReviewText(e.target.value)} disabled={selected.review_state !== 'pending'} data-testid="document-review-json" rows="14" className="w-full mono text-xs border border-border bg-card p-3 focus:outline-none focus:border-foreground disabled:opacity-60" />{selected.review_state === 'pending' ? <div className="grid grid-cols-2 gap-3 mt-4"><button onClick={() => review('rejected')} data-testid="reject-document-btn" className="border border-foreground py-2.5 text-sm">Reject</button><button onClick={() => review('approved')} data-testid="approve-document-btn" className="btn-sharp bg-slateink text-bone py-2.5 text-sm">Approve & commit</button></div> : <p data-testid="document-review-status" className="mt-4 text-sm text-muted-foreground">Review {selected.review_state}.</p>}</> : <div data-testid="document-review-placeholder" className="h-full min-h-72 flex items-center justify-center text-center text-muted-foreground text-sm"><FileScan className="w-8 h-8 text-coral mr-3" />Select a document to review its extraction.</div>}</section></div>
  </main></div>;
}