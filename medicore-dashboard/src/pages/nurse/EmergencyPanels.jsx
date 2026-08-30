import * as Nurse from "./Pages.jsx";
import { IncomingEmergencyCards, IncomingMedicineRequirements } from "../../components/emergencies/IncomingEmergencyCards.jsx";
import { useCareGrid } from "../../app/providers.jsx";
export function AlertsWithEmergencies(){const {live}=useCareGrid();return <><IncomingEmergencyCards live={live}/><Nurse.Alerts/></>}
export function PharmacyWithEmergencies(){const {live}=useCareGrid();return <><IncomingMedicineRequirements live={live}/><Nurse.Pharmacy/></>}
