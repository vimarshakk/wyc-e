import React from 'react';
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Signup from './pages/Signup';
import AuthCallback from './pages/AuthCallback';
import PatientDashboard from './pages/PatientDashboard';
import DoctorDashboard from './pages/DoctorDashboard';
import AdminDashboard from './pages/AdminDashboard';
import OcrUpload from './pages/OcrUpload';
import Records from './pages/Records';
import Appointments from './pages/Appointments';
import WyshIdCard from './pages/WyshId';
import DoctorAvailability from './pages/DoctorAvailability';
import Documents from './pages/Documents';
import CarePlan from './pages/CarePlan';
import Consultations from './pages/Consultations';
import Billing from './pages/Billing';
import Abdm from './pages/Abdm';

function Protected({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center mono text-xs text-muted-foreground">AUTHENTICATING…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={`/app/${user.role}`} replace />;
  return children;
}

function HashRouter() {
  const loc = useLocation();
  if (loc.hash?.includes('session_id=')) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/app/patient" element={<Protected roles={['patient']}><PatientDashboard /></Protected>} />
      <Route path="/app/doctor" element={<Protected roles={['doctor']}><DoctorDashboard /></Protected>} />
      <Route path="/app/admin" element={<Protected roles={['admin']}><AdminDashboard /></Protected>} />
      <Route path="/app/ocr" element={<Protected><OcrUpload /></Protected>} />
      <Route path="/app/documents" element={<Protected><Documents /></Protected>} />
      <Route path="/app/records" element={<Protected><Records /></Protected>} />
      <Route path="/app/appointments" element={<Protected><Appointments /></Protected>} />
      <Route path="/app/wyshid" element={<Protected><WyshIdCard /></Protected>} />
      <Route path="/app/availability" element={<Protected roles={['doctor']}><DoctorAvailability /></Protected>} />
      <Route path="/app/care-plan" element={<Protected roles={['patient']}><CarePlan /></Protected>} />
      <Route path="/app/consultations" element={<Protected><Consultations /></Protected>} />
      <Route path="/app/billing" element={<Protected><Billing /></Protected>} />
      <Route path="/app/abdm" element={<Protected><Abdm /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <HashRouter />
        <Toaster richColors position="bottom-right" />
      </BrowserRouter>
    </AuthProvider>
  );
}
