import { useCallback, useEffect, useRef, useState } from "react";
import { adaptHospitalEnvelope } from "../adapters/hospitalWardAdapter.js";
import { createHospitalSocket, getHospitalLatest } from "../services/hospitalRealtimeService.js";
import { deriveRealtimeEvents, reconnectDelay } from "../services/realtimeEventService.js";

const initialState = {status:"loading",device:null,gateway:null,transport:null,error:null,lastUpdated:null,receivedAt:null,stale:true,reconnectAttempt:0};

export function useCareGridRealtime() {
  const [live,setLive]=useState(initialState);
  const [activityLog,setActivityLog]=useState([]);
  const [emergencyEvents,setEmergencyEvents]=useState([]);
  const previous=useRef(null),socketRef=useRef(null),reconnectRef=useRef(null),attemptRef=useRef(0),mounted=useRef(true);

  const recordTransitions=useCallback(next=>{
    const prior=previous.current;
    const entries=deriveRealtimeEvents(prior,next);
    if(entries.length)setActivityLog(current=>[...entries,...current].slice(0,100));
    previous.current=next;
  },[]);

  const ingest=useCallback((envelope,status="live")=>{
    const device=adaptHospitalEnvelope(envelope);
    if(!device)throw new Error("hospital_ward_01 was not found in the gateway response");
    recordTransitions(device);
    const receivedAt=new Date();
    setLive(current=>({...current,status,device,gateway:envelope.gateway||current.gateway,transport:envelope._transport||"websocket",error:null,lastUpdated:new Date(device.updatedAt),receivedAt,stale:device.connectionStatus!=="LIVE",reconnectAttempt:attemptRef.current}));
    return device;
  },[recordTransitions]);

  const refresh=useCallback(async({quiet=false}={})=>{
    if(!quiet)setLive(current=>current.device?current:{...current,status:"loading",error:null});
    try{const envelope=await getHospitalLatest();return ingest(envelope,socketRef.current?.readyState===1?"live":"reconnecting")}
    catch(error){setLive(current=>({...current,status:current.device?"reconnecting":"offline",error:error.message,stale:true}));return null}
  },[ingest]);

  useEffect(()=>{
    mounted.current=true;
    const connect=()=>{
      if(!mounted.current)return;
      clearTimeout(reconnectRef.current);
      setLive(current=>({...current,status:current.device?"reconnecting":attemptRef.current?"offline":"loading",reconnectAttempt:attemptRef.current}));
      try{
        const socket=createHospitalSocket({
          open:()=>{attemptRef.current=0;setLive(current=>({...current,status:"live",error:null,reconnectAttempt:0}))},
          message:message=>{try{const payload=JSON.parse(message.data);if(payload.type&&payload.type!=="hospital_update"){setEmergencyEvents(current=>[payload,...current].slice(0,100));return}ingest(payload,"live")}catch(error){setLive(current=>({...current,error:`Realtime payload rejected: ${error.message}`}))}},
          error:()=>setLive(current=>({...current,error:"Hospital realtime connection interrupted"})),
          close:()=>{if(!mounted.current)return;attemptRef.current+=1;setLive(current=>({...current,status:current.device?"reconnecting":"offline",reconnectAttempt:attemptRef.current,stale:true}));reconnectRef.current=setTimeout(connect,reconnectDelay(attemptRef.current))},
        });
        socketRef.current=socket;
      }catch(error){attemptRef.current+=1;setLive(current=>({...current,status:current.device?"reconnecting":"offline",error:error.message,reconnectAttempt:attemptRef.current}));reconnectRef.current=setTimeout(connect,reconnectDelay(attemptRef.current))}
    };
    refresh();connect();
    const restSafety=setInterval(()=>{if(socketRef.current?.readyState!==1)refresh({quiet:true})},10000);
    const staleTimer=setInterval(()=>setLive(current=>{
      if(!current.device?.updatedAt)return current;
      const ageSeconds=Math.max(0,(Date.now()-new Date(current.device.updatedAt).getTime())/1000);
      const connectionStatus=ageSeconds<=15?"LIVE":ageSeconds<=30?"STALE":"OFFLINE";
      return {...current,device:{...current.device,ageSeconds:Math.round(ageSeconds*10)/10,connectionStatus,online:connectionStatus==="LIVE"},stale:connectionStatus!=="LIVE"};
    }),3000);
    return()=>{mounted.current=false;clearTimeout(reconnectRef.current);clearInterval(restSafety);clearInterval(staleTimer);socketRef.current?.close()};
  },[ingest,refresh]);

  return {...live,activityLog,emergencyEvents,refresh};
}
