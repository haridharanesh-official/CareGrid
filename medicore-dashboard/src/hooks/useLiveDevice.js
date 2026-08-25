import { useCareGrid } from "../app/providers.jsx";
export function useLiveDevice(){const {live,refresh}=useCareGrid();return {device:live.device,status:live.status,error:live.error,lastUpdated:live.lastUpdated,stale:live.stale,source:live.source,retry:refresh};}
