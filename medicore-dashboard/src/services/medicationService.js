import { DEMO_MODE } from "../config.js";
import { demoMedicationQueue } from "../mock/demoPharmacy.js";
let queue=structuredClone(demoMedicationQueue),prescriptions=[];
const requireDemo=()=>{if(!DEMO_MODE)throw new Error("Medication backend is not connected");};
export async function getMedicationQueue(){requireDemo();return structuredClone(queue);}
export async function administerMedication(id,rfid){requireDemo();const dose=queue.find(x=>x.id===id);if(!dose)throw new Error("Medication dose not found");if(dose.rfid!==rfid)throw new Error("RFID does not match the selected patient");dose.status="Administered";return structuredClone(dose);}
export async function getPrescriptions(){requireDemo();return structuredClone(prescriptions);}
export async function createPrescription(input){requireDemo();const item={id:`rx-${Date.now()}`,status:"Active",...input};prescriptions=[item,...prescriptions];return structuredClone(item);}
