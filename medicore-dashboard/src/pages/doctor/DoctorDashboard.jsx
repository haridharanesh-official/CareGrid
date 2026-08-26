import { useEffect, useState } from "react";
import { useCareGrid } from "../../app/providers.jsx";
import { Badge, Card } from "../../components/common/ui.jsx";
import { resolveRfidUid } from "../../services/rfidService.js";
import { Dashboard as ClinicalDashboard } from "./Pages.jsx";

export default function DoctorDashboard(){
  const {live}=useCareGrid();
  const [identity,setIdentity]=useState(null);
  const uid=live.device?.rfid.lastUid;
  useEffect(()=>{let active=true;if(!uid){setIdentity(null);return()=>{active=false}}resolveRfidUid(uid).then(result=>{if(active)setIdentity(result)});return()=>{active=false}},[uid]);
  const patient=identity?.known&&identity.entity_type==="patient"?identity.entity:null;
  const vitals=live.device?.vitals;
  return <>
    <div className="cg-two-col">
      <Card title="Doctor Hari · DOC-001" action={<Badge tone="info">Emergency Medicine</Badge>}><p className="cg-help">DEMO HACKATHON doctor identity · RFID AA:B4:32:06</p></Card>
      <Card title="Current RFID patient" action={identity?.offline_fallback?<Badge tone="warning">Offline demo mode</Badge>:null}>
        {patient?<div className="cg-status-rows"><div><span>Patient</span><Badge tone="healthy">{patient.name} · {patient.patient_id}</Badge></div><div><span>Blood group</span><Badge>{patient.blood_group}</Badge></div><div><span>RFID</span><Badge tone="healthy">Verified · {identity.uid}</Badge></div><div><span>Heart rate</span><Badge>{vitals?.waitingForPatient?"Waiting for patient":vitals?.heartRate.available?vitals.heartRate.display:"Unavailable"}</Badge></div><div><span>SpO₂</span><Badge>{vitals?.waitingForPatient?"Waiting for patient":vitals?.spo2.available?vitals.spo2.display:"Unavailable"}</Badge></div></div>:<div className="cg-empty">No patient identified</div>}
      </Card>
    </div>
    <ClinicalDashboard/>
  </>;
}
