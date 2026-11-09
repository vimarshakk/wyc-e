import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "../lib/api";
const Context = createContext(null);
export function AuthProvider({ children }) { const [user,setUser]=useState(()=>JSON.parse(localStorage.getItem("wyc_user")||"null")); useEffect(()=>{user?localStorage.setItem("wyc_user",JSON.stringify(user)):localStorage.removeItem("wyc_user")},[user]); const login=async(credentials)=>{const data=await api.post("/auth/login",credentials); localStorage.setItem("wyc_token",data.access_token); setUser(data.user); return data;}; const signup=async(credentials)=>{const data=await api.post("/auth/signup",credentials); if(data.access_token){localStorage.setItem("wyc_token",data.access_token);setUser(data.user);} return data;}; const logout=()=>{localStorage.removeItem("wyc_token");setUser(null)}; return <Context.Provider value={{user,login,signup,logout}}>{children}</Context.Provider>; }
export const useAuth=()=>useContext(Context);
