import { createContext, useContext, useMemo, useState } from "react";
import { DEMO_MODE } from "../config.js";
import { useCareGridRealtime } from "../hooks/useCareGridRealtime.js";
import * as authService from "../services/authService.js";

const AuthContext=createContext(null),CareGridContext=createContext(null);

export function AuthProvider({children}){
  const [session,setSession]=useState(()=>authService.getSession());
  const login=async credentials=>{const next=await authService.login(credentials);setSession(next);return next;};
  const logout=async()=>{await authService.logout();setSession(null);};
  const switchRole=async role=>login({name:session?.name||"CareGrid Demo",role});
  return <AuthContext.Provider value={{session,login,logout,switchRole,demoMode:DEMO_MODE}}>{children}</AuthContext.Provider>;
}

export function CareGridProvider({children}){
  const realtime=useCareGridRealtime();
  const [manualAlerts,setManualAlerts]=useState([]);
  const [acknowledged,setAcknowledged]=useState(()=>new Set());
  const [emergency,setEmergency]=useState(null);
  const [preAlert,setPreAlert]=useState(null);
  const [systemOpen,setSystemOpen]=useState(false);

  const live=useMemo(()=>({...realtime,connectionState:realtime.status,status:realtime.status==="live"?"online":realtime.status,health:realtime.gateway,devices:realtime.device?[realtime.device]:[],events:realtime.activityLog,emergencyEvents:realtime.emergencyEvents||[],source:realtime.device?"live":"none"}),[realtime]);
  const alerts=useMemo(()=>[...manualAlerts,...realtime.activityLog].map(item=>({...item,acknowledged:acknowledged.has(item.id)})),[manualAlerts,realtime.activityLog,acknowledged]);
  const acknowledgeAlert=id=>setAcknowledged(current=>new Set([...current,id]));
  const addAlert=alert=>setManualAlerts(current=>[{id:`local-${Date.now()}`,timestamp:new Date().toISOString(),acknowledged:false,...alert},...current]);
  const value=useMemo(()=>({live,refresh:realtime.refresh,alerts,acknowledgeAlert,addAlert,emergency,setEmergency,preAlert,setPreAlert,systemOpen,setSystemOpen}),[live,alerts,emergency,preAlert,systemOpen,realtime.refresh]);
  return <CareGridContext.Provider value={value}>{children}</CareGridContext.Provider>;
}

export const useAuth=()=>{const v=useContext(AuthContext);if(!v)throw new Error("useAuth must be used within AuthProvider");return v;};
export const useCareGrid=()=>{const v=useContext(CareGridContext);if(!v)throw new Error("useCareGrid must be used within CareGridProvider");return v;};

export function AppProviders({children}){return <AuthProvider><CareGridProvider>{children}</CareGridProvider></AuthProvider>}
