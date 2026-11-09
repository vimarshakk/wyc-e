import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import "./App.css";
import Nav from "./components/Nav";
import { AuthProvider } from "./contexts/AuthContext";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import PatientDashboard from "./pages/PatientDashboard";
import DoctorDashboard from "./pages/DoctorDashboard";
import AdminDashboard from "./pages/AdminDashboard";
import Appointments from "./pages/Appointments";
import Availability from "./pages/DoctorAvailability";
import Records from "./pages/Records";
import Documents from "./pages/Documents";
import OcrUpload from "./pages/OcrUpload";
import CarePlan from "./pages/CarePlan";
import Consultations from "./pages/Consultations";
import Billing from "./pages/Billing";
import Claims from "./pages/Claims";
import Abdm from "./pages/Abdm";
import WyshId from "./pages/WyshId";
import AuthCallback from "./pages/AuthCallback";
import PartnerWorkspace from "./pages/PartnerWorkspace";

export default function App() { return <AuthProvider><div className="app-shell"><Nav /><main><Routes><Route path="/" element={<Landing />} /><Route path="/login" element={<Login />} /><Route path="/signup" element={<Signup />} /><Route path="/auth/callback" element={<AuthCallback />} /><Route path="/app" element={<PatientDashboard />} /><Route path="/doctor" element={<DoctorDashboard />} /><Route path="/admin" element={<AdminDashboard />} /><Route path="/partner/:role" element={<PartnerWorkspace />} /><Route path="/appointments" element={<Appointments />} /><Route path="/availability" element={<Availability />} /><Route path="/records" element={<Records />} /><Route path="/documents" element={<Documents />} /><Route path="/documents/upload" element={<OcrUpload />} /><Route path="/care-plan" element={<CarePlan />} /><Route path="/consultations" element={<Consultations />} /><Route path="/billing" element={<Billing />} /><Route path="/claims" element={<Claims />} /><Route path="/abdm" element={<Abdm />} /><Route path="/wyshid" element={<WyshId />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></main></div></AuthProvider>; }
