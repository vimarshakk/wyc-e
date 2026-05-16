import React, { useState, useRef } from 'react';
import Nav from '../components/Nav';
import { api } from '../lib/api';
import { UploadCloud, Loader2, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';

export default function OcrUpload() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const inp = useRef(null);

  const onFile = (f) => {
    if (!f) return;
    if (!/^image\/(jpeg|jpg|png|webp)$/.test(f.type)) {
      toast.error('Use JPEG, PNG or WEBP image'); return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
  };

  const onDrop = (e) => { e.preventDefault(); onFile(e.dataTransfer.files?.[0]); };

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const { data } = await api.post('/ocr/prescriptions', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(data);
      toast.success(`Extracted ${data.extracted?.medications?.length || 0} medication(s)`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'OCR failed');
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-background grain">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10 py-10">
        <div className="mb-8">
          <div className="micro text-coral mb-3">Prescription Intelligence · Claude Sonnet 4.5</div>
          <h1 className="font-outfit text-4xl tracking-tighter">Scan a prescription</h1>
          <p className="text-muted-foreground mt-2">Drop or pick an image. We'll extract medications, dosage, frequency, and per-line confidence scores.</p>
        </div>

        <div className="grid grid-cols-12 gap-6">
          {/* Upload area */}
          <div className="col-span-12 lg:col-span-6">
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              data-testid="ocr-dropzone"
              className={`${busy ? 'tracing-border' : 'border-2 border-dashed border-border'} bg-card p-8 min-h-[420px] flex flex-col items-center justify-center cursor-pointer transition-colors hover:border-foreground`}
              onClick={() => inp.current?.click()}
            >
              <input ref={inp} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
                data-testid="ocr-file-input"
                onChange={(e) => onFile(e.target.files?.[0])} />
              {preview ? (
                <img src={preview} alt="prescription" className="max-h-[360px] object-contain" />
              ) : (
                <>
                  <UploadCloud className="w-10 h-10 text-coral mb-4" />
                  <div className="font-outfit text-xl">Drop your prescription here</div>
                  <div className="text-sm text-muted-foreground mt-2">JPEG · PNG · WEBP · up to 10MB</div>
                </>
              )}
            </div>
            <button
              disabled={!file || busy}
              onClick={submit}
              data-testid="ocr-extract-btn"
              className="btn-sharp w-full mt-4 bg-slateink text-bone py-3 font-medium inline-flex items-center justify-center gap-2 disabled:opacity-50">
              {busy ? <><Loader2 className="w-4 h-4 animate-spin" /> Extracting with Claude…</> : 'Extract with AI'}
            </button>
          </div>

          {/* Result panel */}
          <div className="col-span-12 lg:col-span-6">
            {!result ? (
              <div className="bento-cell p-8 min-h-[420px] flex items-center justify-center">
                <div className="text-center max-w-sm">
                  <div className="micro text-muted-foreground mb-3">AWAITING UPLOAD</div>
                  <div className="font-outfit text-2xl tracking-tight">Structured medication output appears here</div>
                  <div className="text-sm text-muted-foreground mt-3">
                    Each line gets a confidence score in <span className="mono">IBM Plex Mono</span> — built for clinical review.
                  </div>
                </div>
              </div>
            ) : (
              <div className="bento-cell p-7" data-testid="ocr-result">
                <div className="flex items-center gap-2 mb-5">
                  <CheckCircle2 className="w-5 h-5 text-coral" />
                  <span className="micro text-coral">EXTRACTED</span>
                  <span className="mono text-xs text-muted-foreground ml-auto">
                    confidence · {(result.extracted?.overall_confidence ?? 0).toFixed(2)}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4 mb-5 text-sm">
                  <Field label="Doctor" value={result.extracted?.doctor_name} />
                  <Field label="Clinic" value={result.extracted?.clinic_name} />
                  <Field label="Patient" value={result.extracted?.patient_name} />
                  <Field label="Date" value={result.extracted?.prescription_date} />
                </div>
                {result.extracted?.diagnosis && (
                  <div className="mb-5"><div className="micro text-muted-foreground">DIAGNOSIS</div>
                    <div className="text-sm mt-1">{result.extracted.diagnosis}</div></div>
                )}
                <div className="micro text-coral mb-3">MEDICATIONS · {result.extracted?.medications?.length || 0}</div>
                <div className="space-y-2">
                  {(result.extracted?.medications || []).map((m, i) => (
                    <div key={i} className="border border-border p-3 hover:border-foreground transition-colors">
                      <div className="flex justify-between items-start gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium">{m.name}</div>
                          <div className="mono text-xs text-muted-foreground mt-0.5">
                            {[m.dosage, m.frequency, m.duration].filter(Boolean).join(' · ')}
                          </div>
                          {m.instructions && <div className="text-xs mt-1">{m.instructions}</div>}
                        </div>
                        <div className="mono text-sm text-coral">{(m.confidence ?? 0).toFixed(2)}</div>
                      </div>
                    </div>
                  ))}
                  {!result.extracted?.medications?.length && (
                    <div className="text-sm text-muted-foreground">No medications detected. Image may be unclear.</div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <div className="micro text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm">{value || '—'}</div>
    </div>
  );
}
