import * as Doctor from "./Pages.jsx";
import { IncomingEmergencyCards, IncomingMedicineRequirements } from "../../components/emergencies/IncomingEmergencyCards.jsx";
import { useCareGrid } from "../../app/providers.jsx";
export function EmergenciesWithPreAlerts(){const {live}=useCareGrid();return <><IncomingEmergencyCards live={live} doctor/><Doctor.Emergencies/></>}
export function PharmacyWithEmergencies(){const {live}=useCareGrid();return <><IncomingMedicineRequirements live={live}/><Doctor.Pharmacy/></>}
