import { DEMO_MODE } from "../config.js";
import { demoBeds } from "../mock/demoPharmacy.js";
let beds=structuredClone(demoBeds);
const requireDemo=()=>{if(!DEMO_MODE)throw new Error("Bed management backend is not connected");};
export async function getBeds(){requireDemo();return structuredClone(beds);}
export async function assignBed(bedId,patient){requireDemo();beds=beds.map(b=>b.id===bedId?{...b,occupied:true,patient:patient.name,rfid:patient.rfid,reserved:false,incoming:null}:b);return structuredClone(beds.find(b=>b.id===bedId));}
export async function reserveBed(bedId,ambulanceId){requireDemo();beds=beds.map(b=>b.id===bedId?{...b,reserved:true,incoming:ambulanceId}:b);return structuredClone(beds.find(b=>b.id===bedId));}
export async function releaseBed(bedId){requireDemo();beds=beds.map(b=>b.id===bedId?{...b,occupied:false,patient:null,rfid:null,reserved:false,incoming:null,cleaning:"Cleaning"}:b);return structuredClone(beds.find(b=>b.id===bedId));}
