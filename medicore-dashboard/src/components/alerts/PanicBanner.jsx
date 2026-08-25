import { BellRinging, Clock } from "@phosphor-icons/react";
import { useCareGrid } from "../../app/providers.jsx";
import { Button } from "../common/ui.jsx";

export function PanicBanner(){
  const {live,setSystemOpen}=useCareGrid();
  if(!live.device?.emergency.panic)return null;
  const panicEvent=live.events.find(item=>item.type==="panic");
  const received=panicEvent?.timestamp||live.device.updatedAt;
  return <section className="cg-panic-banner" role="alert" aria-live="assertive"><span><BellRinging weight="fill"/></span><div><strong>PATIENT PANIC ALERT — WARD 01</strong><small><Clock/> Received {new Date(received).toLocaleTimeString()} · Panic remains active at hospital_ward_01</small></div><Button onClick={()=>setSystemOpen(true)}>View Ward Status</Button></section>
}
