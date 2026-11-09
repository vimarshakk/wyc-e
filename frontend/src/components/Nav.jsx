import React from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { LogOut } from 'lucide-react';

const navByRole = {
  patient: [
    { to: '/app/patient', label: 'Overview' },
    { to: '/app/documents', label: 'Documents' },
    { to: '/app/records', label: 'Records' },
    { to: '/app/appointments', label: 'Appointments' },
    { to: '/app/consultations', label: 'Consultations' },
    { to: '/app/care-plan', label: 'Care Plan' },
    { to: '/app/billing', label: 'Billing' },
    { to: '/app/claims', label: 'Claims' },
    { to: '/app/wyshid', label: 'WyshID' },
    { to: '/app/abdm', label: 'ABDM' },
  ],
  doctor: [
    { to: '/app/doctor', label: 'Overview' },
    { to: '/app/availability', label: 'Availability' },
    { to: '/app/appointments', label: 'Schedule' },
    { to: '/app/consultations', label: 'Consultations' },
    { to: '/app/billing', label: 'Billing' },
    { to: '/app/wyshid', label: 'WyshID' },
    { to: '/app/abdm', label: 'ABDM' },
  ],
  lab: [{ to: '/app/lab', label: 'Operations' }],
  pharmacy: [{ to: '/app/pharmacy', label: 'Fulfilment' }],
  insurer: [{ to: '/app/insurer', label: 'Claims' }],
  partner: [{ to: '/app/partner', label: 'Workspace' }],
  admin: [
    { to: '/app/admin', label: 'Control Room' },
    { to: '/app/wyshid', label: 'WyshID' },
  ],
};

export default function Nav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const items = user ? (navByRole[user.role] || []) : [];

  const onLogout = async () => { await logout(); navigate('/'); };

  return (
    <header className="glass-nav sticky top-0 z-50 w-full" data-testid="app-nav">
      <div className="max-w-[1400px] mx-auto flex items-center justify-between px-4 sm:px-6 lg:px-10 h-16">
        <Link to={user ? `/app/${user.role}` : '/'} className="flex items-center gap-2" data-testid="nav-logo">
          <img src="https://static.wixstatic.com/media/22cc26_3e80923df3954ea8a068dbbad8a2fbb6~mv2.png/v1/crop/x_171,y_276,w_965,h_381/fill/w_402,h_116,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/wyshcare.png" alt="WyshCare" data-testid="nav-brand-logo" className="h-7 w-auto max-w-32 object-contain object-left" />
          <span className="micro text-coral ml-1 hidden sm:inline">AI-Native</span>
        </Link>

        <nav className="hidden lg:flex items-center gap-1">
          {items.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              data-testid={`nav-${it.label.toLowerCase().replace(/\s+/g, '-')}`}
              className={({ isActive }) =>
                `px-3 py-1.5 text-sm transition-colors ${isActive ? 'text-foreground border-b-2 border-coral' : 'text-muted-foreground hover:text-foreground'}`}
            >{it.label}</NavLink>
          ))}
        </nav>

        {user && (
          <select
            aria-label="Navigate to"
            data-testid="mobile-nav-select"
            value={items.some((item) => item.to === location.pathname) ? location.pathname : ''}
            onChange={(event) => navigate(event.target.value)}
            className="lg:hidden min-w-0 max-w-24 border border-border bg-transparent px-2 py-1.5 text-xs"
          >
            {items.map((item) => <option key={item.to} value={item.to}>{item.label}</option>)}
          </select>
        )}

        <div className="flex items-center gap-3">
          {user ? (
            <>
              <div className="hidden sm:flex flex-col items-end">
                <span className="text-sm font-medium">{user.name}</span>
                <span className="mono text-[10px] text-muted-foreground">{user.wysh_id}</span>
              </div>
              <button onClick={onLogout} data-testid="nav-logout" className="p-2 hover:bg-muted transition-colors">
                <LogOut className="w-4 h-4" />
              </button>
            </>
          ) : (
            <>
              <Link to="/login" data-testid="nav-login" className="text-sm hover:text-coral transition-colors">Sign in</Link>
              <Link to="/signup" data-testid="nav-signup-cta" className="btn-sharp bg-slateink text-bone px-4 py-2 text-sm font-medium">
                Get WyshID
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
