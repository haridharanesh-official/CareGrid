import { Broadcast } from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";
import { useCareGrid } from "../../app/providers.jsx";
import { Badge, Button, Card, PageHeader } from "../../components/common/ui.jsx";

export default function RealtimeWards(){
  const {live}=useCareGrid(),d=live.device,navigate=useNavigate();
  const wardState=d?.connectionStatus||"OFFLINE",tone=wardState==="LIVE"?"healthy":wardState==="STALE"?"warning":"critical";
  return <><PageHeader title="Connected hospital nodes" subtitle="Gateway connectivity and physical ward freshness are tracked separately."/>{d?<div className="cg-ward-grid"><Card title="Ward 01 · hospital_ward_01" action={<Badge tone={tone}>{wardState}</Badge>}><div className="cg-status-rows"><div><span>Node type</span><Badge>{d.nodeType}</Badge></div><div><span>Wi-Fi (last reported)</span><Badge tone={d.connectivity.wifi?"healthy":"critical"}>{d.connectivity.wifi?`${d.connectivity.wifiRssi} dBm`:"Offline"}</Badge></div><div><span>MQTT (last reported)</span><Badge tone={d.connectivity.mqtt?"healthy":"critical"}>{d.connectivity.mqtt?"Connected":"Disconnected"}</Badge></div><div><span>Last telemetry</span><Badge>{new Date(d.updatedAt).toLocaleTimeString()} · {d.ageSeconds??"--"}s ago</Badge></div></div><Button disabled={wardState!=="LIVE"} onClick={()=>navigate("/nurse/dashboard")}>{wardState==="LIVE"?"Open live ward":wardState==="STALE"?"Ward signal stale":"Ward offline"}</Button></Card></div>:<div className="cg-live-empty"><Broadcast/><h2>No hospital ward node available</h2><p>{live.status==="offline"?"Live ward telemetry is temporarily unavailable.":"Waiting for hospital_ward_01."}</p></div>}</>
}
