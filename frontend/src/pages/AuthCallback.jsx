import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setToken } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = window.location.hash || '';
    const m = hash.match(/session_id=([^&]+)/);
    if (!m) { navigate('/login'); return; }
    const session_id = m[1];

    (async () => {
      try {
        const { data } = await api.post('/auth/google/exchange', { session_id });
        setToken(data.token);
        setSession(data.token, data.user);
        window.history.replaceState({}, '', '/');
        toast.success(`Welcome, ${data.user.name}`);
        navigate(`/app/${data.user.role}`, { state: { user: data.user } });
      } catch (e) {
        toast.error('Google sign-in failed');
        navigate('/login');
      }
    })();
  }, [navigate, setSession]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <div className="mono text-xs text-muted-foreground mb-4">WYSHCARE · AUTH</div>
        <div className="font-outfit text-2xl">Establishing secure session…</div>
      </div>
    </div>
  );
}
