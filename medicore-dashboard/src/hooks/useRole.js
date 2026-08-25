import { useAuth } from "../app/providers.jsx";
export const useRole=()=>useAuth().session?.role||null;
