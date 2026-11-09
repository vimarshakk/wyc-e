import React from "react";
import { useParams } from "react-router-dom";
import { ShieldCheck } from "lucide-react";

export default function PartnerWorkspace(){
  const { role = "PARTNER" } = useParams();
  return <div className="page" style={{maxWidth:760}}><span className="eyebrow">{role} workspace</span><h1>Consent-gated partner access</h1><div className="card"><ShieldCheck color="#f97316"/><h3>Your account is approved</h3><p className="muted">Patient information is not visible by default. A patient-specific consent, role permission and audit record are required before any clinical data is shown.</p><div className="button" style={{display:"inline-flex",marginTop:12}}>Request scoped consent</div></div></div>;
}
