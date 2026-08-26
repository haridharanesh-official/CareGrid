import { BellRinging, Clock } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { useCareGrid } from "../../app/providers.jsx";
import { resolveRfidUid } from "../../services/rfidService.js";
import { Button } from "../common/ui.jsx";

export function PanicBanner(){
  const {live,setSystemOpen}=useCareGrid();
  const [identity,setIdentity]=useState(null);
  const uid=live.device?.rfid.lastUid;
  useEffect(()=>{let active=true;if(!uid){setIdentity(null);return()=>{active=false}}resolveRfidUid(uid).then(result=>{if(active)setIdentity(result)});return()=>{active=false}},[uid]);
  if(!live.device?.emergency.panic)return null;
  const panicEvent=live.events.find(item=>item.type==="panic");
  const received=panicEvent?.timestamp||live.device.updatedAt;
  const patient=identity?.known&&identity.entity_type==="patient"?identity.entity:null;
  return <section className="cg-panic-banner" role="alert" aria-live="assertive"><span><BellRinging weight="fill"/></span><div><strong>PATIENT PANIC ALERT — WARD 01</strong>{patient&&<b>{patient.name} — {patient.patient_id}</b>}<small><Clock/> Received {new Date(received).toLocaleTimeString()} · Panic remains active at hospital_ward_01</small></div><Button onClick={()=>setSystemOpen(true)}>View Ward Status</Button></section>
}
