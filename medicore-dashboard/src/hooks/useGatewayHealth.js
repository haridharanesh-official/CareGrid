import { useCareGrid } from "../app/providers.jsx";
export function useGatewayHealth(){const {live,refresh}=useCareGrid();return {status:live.status,health:live.health,error:live.error,lastUpdated:live.lastUpdated,stale:live.stale,source:live.source,retry:refresh};}
