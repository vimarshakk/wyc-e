import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, withCredentials: true });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem('wysh_token');
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export const setToken = (t) => {
  if (t) localStorage.setItem('wysh_token', t);
  else localStorage.removeItem('wysh_token');
};
export const getToken = () => localStorage.getItem('wysh_token');
