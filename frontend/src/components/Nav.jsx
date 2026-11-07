import React from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { LogOut, Sparkles } from 'lucide-react';

const navByRole = {
  patient: [
    { to: '/app/patient', label: 'Overview' },
    { to: '/app/ocr', label: 'OCR Scan' },
    { to: '/app/records', label: 'Records' },
    { to: '/app/appointments', label: 'Appointments' },
    { to: '/app/wyshid', label: 'WyshID' },
  ],
  doctor: [
    { to: '/app/doctor', label: 'Overview' },
    { to: '/app/availability', label: 'Availability' },
    { to: '/app/appointments', label: 'Schedule' },
    { to: '/app/wyshid', label: 'WyshID' },
  ],
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
          <div className="w-7 h-7 bg-slateink dark:bg-bone flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-coral" />
          </div>
          <span className="font-outfit text-lg tracking-tight font-medium">WyshCare</span>
          <span className="micro text-coral ml-1 hidden sm:inline">AI-Native</span>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
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
            className="md:hidden min-w-0 max-w-24 border border-border bg-transparent px-2 py-1.5 text-xs"
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
