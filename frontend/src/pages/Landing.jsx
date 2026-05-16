import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Brain, ShieldCheck, FileScan, Activity, Network, Lock } from 'lucide-react';
import Nav from '../components/Nav';

const HERO_BG = "https://static.prod-images.emergentagent.com/jobs/bfc2e3d0-665c-49fe-8a20-947f475771d1/images/fd2f59785e924d1d06ab7c2ebeaf6da732bef4b2e6a976d844a75dfe010290db.png";
const OCR_IMG = "https://static.prod-images.emergentagent.com/jobs/bfc2e3d0-665c-49fe-8a20-947f475771d1/images/0d8d5bb0827b78229c010ed1f8014aceec5da9f6fbbe9858e8d3f89d34742a57.png";
const CLINIC_IMG = "https://images.unsplash.com/photo-1758691461888-b74515208d7a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzV8MHwxfHNlYXJjaHwyfHxtb2Rlcm4lMjBob3NwaXRhbCUyMGFyY2hpdGVjdHVyZSUyMG9yJTIwZG9jdG9yJTIwaW4lMjBtb2Rlcm4lMjBjbGluaWN8ZW58MHx8fHwxNzc4NzU3OTI0fDA&ixlib=rb-4.1.0&q=85";

export default function Landing() {
  return (
    <div className="grain min-h-screen bg-background text-foreground">
      <Nav />
      <main className="max-w-[1400px] mx-auto px-6 lg:px-10">
        {/* HERO — Asymmetric */}
        <section className="grid grid-cols-12 gap-6 pt-16 lg:pt-24 pb-20">
          <div className="col-span-12 lg:col-span-7 animate-fade-up">
            <div className="flex items-center gap-2 mb-8">
              <span className="micro text-coral">v0.1 — Phase 1</span>
              <span className="w-8 h-px bg-border"></span>
              <span className="micro text-muted-foreground">India's Healthcare OS</span>
            </div>
            <h1 className="font-outfit text-5xl sm:text-6xl lg:text-7xl tracking-tighter font-medium leading-[1.02]">
              The operating system<br/>
              for <span className="italic font-light">Indian healthcare,</span><br/>
              built AI-native.
            </h1>
            <p className="mt-8 text-lg max-w-xl text-muted-foreground leading-relaxed">
              WyshID is a verified, longitudinal health identity. WyshCare turns prescriptions, lab reports and clinical encounters into a structured, intelligent record — for every patient, every clinic, every hospital.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-4">
              <Link to="/signup" data-testid="hero-cta-primary" className="btn-sharp bg-slateink text-bone px-6 py-3 inline-flex items-center gap-2 font-medium">
                Claim your WyshID <ArrowUpRight className="w-4 h-4" />
              </Link>
              <Link to="/login" data-testid="hero-cta-secondary" className="px-6 py-3 border border-foreground hover:bg-foreground hover:text-background transition-colors inline-flex items-center gap-2">
                Provider sign-in
              </Link>
            </div>
            <div className="mt-12 grid grid-cols-3 gap-6 max-w-lg">
              <div><div className="font-outfit text-3xl">1.4B</div><div className="micro text-muted-foreground mt-1">addressable lives</div></div>
              <div><div className="font-outfit text-3xl">99.2%</div><div className="micro text-muted-foreground mt-1">OCR accuracy goal</div></div>
              <div><div className="font-outfit text-3xl">&lt;3s</div><div className="micro text-muted-foreground mt-1">AI extraction latency</div></div>
            </div>
          </div>

          <div className="col-span-12 lg:col-span-5 lg:pl-8 animate-fade-up" style={{ animationDelay: '120ms' }}>
            <div className="relative">
              <img src={HERO_BG} alt="WyshID identity hologram" className="w-full h-[480px] object-cover border border-border" />
              <div className="absolute -bottom-4 -left-4 bg-card border border-border p-4 shadow-sm max-w-[260px]">
                <div className="micro text-coral mb-2">WyshID · verified</div>
                <div className="mono text-sm">WYSH-7E2A-91FC</div>
                <div className="text-xs text-muted-foreground mt-2">Longitudinal record · 14 encounters indexed</div>
              </div>
            </div>
          </div>
        </section>

        {/* MODULES — Bento */}
        <section className="py-16 border-t border-border">
          <div className="flex items-end justify-between mb-10">
            <div>
              <div className="micro text-coral mb-3">The platform</div>
              <h2 className="font-outfit text-4xl lg:text-5xl tracking-tighter font-medium">A modular healthcare OS</h2>
            </div>
            <div className="hidden md:block mono text-xs text-muted-foreground">SECTION · 02</div>
          </div>
          <div className="grid grid-cols-12 gap-4">
            <ModuleCard icon={ShieldCheck} title="WyshID Identity" desc="Verified health identity layer with trust scoring & longitudinal record graph." span="col-span-12 md:col-span-7" />
            <ModuleCard icon={FileScan} title="OCR Intelligence" desc="Claude Sonnet 4.5 reads prescriptions, normalizes meds, scores confidence per line." span="col-span-12 md:col-span-5" />
            <ModuleCard icon={Activity} title="EMR / EHR Foundation" desc="Records, encounters, vitals, imaging metadata — relationally migration-ready." span="col-span-12 md:col-span-4" />
            <ModuleCard icon={Brain} title="AI Orchestration" desc="Provider-agnostic model routing. OpenAI / Anthropic / Gemini abstracted." span="col-span-12 md:col-span-4" />
            <ModuleCard icon={Network} title="Healthcare Graph" desc="Patient journeys, medication patterns, disease progression — graph-ready." span="col-span-12 md:col-span-4" />
          </div>
        </section>

        {/* OCR Preview */}
        <section className="py-20 border-t border-border grid grid-cols-12 gap-10">
          <div className="col-span-12 lg:col-span-5">
            <div className="micro text-coral mb-3">Prescription intelligence</div>
            <h3 className="font-outfit text-4xl tracking-tighter font-medium leading-tight">
              Drop a prescription.<br/>Get structured medicine in seconds.
            </h3>
            <p className="text-muted-foreground mt-6 leading-relaxed">
              Every line in every prescription becomes machine-readable: drug name, dosage, frequency, duration, instructions — each with a per-line confidence score.
            </p>
            <ul className="mt-8 space-y-3 text-sm">
              <li className="flex items-center gap-3"><span className="w-1.5 h-1.5 bg-coral"></span> Claude Sonnet 4.5 vision pipeline</li>
              <li className="flex items-center gap-3"><span className="w-1.5 h-1.5 bg-coral"></span> Per-medication confidence scoring</li>
              <li className="flex items-center gap-3"><span className="w-1.5 h-1.5 bg-coral"></span> Auto-indexed to your WyshID record</li>
            </ul>
          </div>
          <div className="col-span-12 lg:col-span-7">
            <div className="tracing-border p-2 bg-card">
              <img src={OCR_IMG} alt="OCR extraction" className="w-full h-[420px] object-cover" />
            </div>
            <div className="grid grid-cols-3 gap-3 mt-3 mono text-xs">
              <div className="border border-border p-3"><div className="text-muted-foreground">Amoxicillin 500mg</div><div className="text-coral mt-1">0.96</div></div>
              <div className="border border-border p-3"><div className="text-muted-foreground">Paracetamol 650mg</div><div className="text-coral mt-1">0.93</div></div>
              <div className="border border-border p-3"><div className="text-muted-foreground">Pantoprazole 40mg</div><div className="text-coral mt-1">0.89</div></div>
            </div>
          </div>
        </section>

        {/* For Providers */}
        <section className="py-20 border-t border-border grid grid-cols-12 gap-10">
          <div className="col-span-12 lg:col-span-6 order-2 lg:order-1">
            <img src={CLINIC_IMG} alt="Modern clinic" className="w-full h-[400px] object-cover border border-border" />
          </div>
          <div className="col-span-12 lg:col-span-6 order-1 lg:order-2">
            <div className="micro text-coral mb-3">For providers</div>
            <h3 className="font-outfit text-4xl tracking-tighter font-medium leading-tight">Built for clinicians. Engineered for hospitals.</h3>
            <p className="text-muted-foreground mt-6 leading-relaxed">
              Doctor and clinic portals with patient queues, schedules, instant WyshID lookup, and a clean clinical timeline. RBAC, audit logs, and DPDP-Act-aware consent architecture by default.
            </p>
            <div className="mt-8 grid grid-cols-2 gap-4">
              <div className="border border-border p-5">
                <Lock className="w-5 h-5 mb-3" />
                <div className="font-outfit text-xl tracking-tight">Healthcare-grade</div>
                <div className="text-sm text-muted-foreground mt-1">HIPAA-inspired controls, full audit trail</div>
              </div>
              <div className="border border-border p-5">
                <Network className="w-5 h-5 mb-3" />
                <div className="font-outfit text-xl tracking-tight">Interoperable</div>
                <div className="text-sm text-muted-foreground mt-1">API-first, graph-ready, FHIR roadmap</div>
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-24 border-t border-border grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8">
            <h2 className="font-outfit text-5xl lg:text-6xl tracking-tighter font-medium leading-[1.02]">
              The next decade of healthcare<br/>will run on identity.
            </h2>
          </div>
          <div className="col-span-12 lg:col-span-4 flex flex-col justify-end">
            <Link to="/signup" data-testid="cta-bottom-signup" className="btn-sharp bg-coral text-white px-6 py-4 inline-flex items-center justify-between font-medium text-lg">
              Get your WyshID <ArrowUpRight className="w-5 h-5" />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-10 flex flex-wrap items-center justify-between gap-4">
          <div className="mono text-xs text-muted-foreground">WYSHCARE © 2026 · India · v0.1.0</div>
          <div className="flex gap-6 text-xs text-muted-foreground">
            <span>Privacy</span><span>Security</span><span>DPDP</span><span>Contact</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function ModuleCard({ icon: Icon, title, desc, span }) {
  return (
    <div className={`bento-cell ${span} p-7 group`}>
      <Icon className="w-6 h-6 text-coral mb-6" />
      <div className="font-outfit text-2xl tracking-tight mb-2">{title}</div>
      <div className="text-sm text-muted-foreground leading-relaxed">{desc}</div>
    </div>
  );
}
