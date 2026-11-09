import React from "react";
import { Link } from "react-router-dom";
import { HeartPulse, LogIn } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

export default function Nav() { const { user, logout } = useAuth(); return <header style={{background:"#fff",borderBottom:"1px solid #f0e6dc",position:"sticky",top:0,zIndex:10}}><nav className="row" style={{maxWidth:1180,margin:"auto",padding:"16px 20px"}}><Link to="/" className="row"><HeartPulse color="#f97316"/><strong>WYC-e</strong></Link><div className="row"><Link to="/appointments">Appointments</Link>{user ? <><Link to={user.role === "DOCTOR" ? "/doctor" : "/app"}>{user.role === "DOCTOR" ? "Workspace" : "My care"}</Link><button onClick={logout} style={{border:0,background:"transparent",cursor:"pointer"}}>Sign out</button></> : <Link to="/login" className="row"><LogIn size={16}/> Sign in</Link>}</div></nav></header>; }
