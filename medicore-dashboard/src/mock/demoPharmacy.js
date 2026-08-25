export const demoPharmacy = [
  { id:"m1", medicine:"Adrenaline", hospital:"CityCare Multi-Speciality Hospital", quantity:18, reserved:4, updated:"2 min ago", travel:8, status:"available" },
  { id:"m2", medicine:"O-negative blood", hospital:"CityCare Multi-Speciality Hospital", quantity:6, reserved:2, updated:"1 min ago", travel:8, status:"low" },
  { id:"m3", medicine:"Atropine", hospital:"Northside General Hospital", quantity:0, reserved:0, updated:"4 min ago", travel:6, status:"unavailable" },
  { id:"m4", medicine:"Insulin", hospital:"St. Anne Care Centre", quantity:42, reserved:8, updated:"3 min ago", travel:11, status:"available" },
  { id:"m5", medicine:"Adrenaline", hospital:"Riverside Community Hospital", quantity:9, reserved:1, updated:"8 min ago", travel:14, status:"available" },
  { id:"m6", medicine:"Paracetamol 500mg", hospital:"CityCare Multi-Speciality Hospital", quantity:420, reserved:32, updated:"1 min ago", travel:8, status:"available" },
];

export const demoMedicationQueue = [
  {id:"dose-1",patient:"Aarav Sharma",rfid:"04:A8:91:7C",medicine:"Aspirin",dosage:"75 mg",route:"Oral",time:"09:00",prescriber:"Dr. Rohan Mehta",status:"Due"},
  {id:"dose-2",patient:"Neha Kapoor",rfid:"A1:09:CC:32",medicine:"Budesonide",dosage:"0.5 mg",route:"Nebulized",time:"09:15",prescriber:"Dr. Ananya Joshi",status:"Due"},
  {id:"dose-3",patient:"Vikram Singh",rfid:"92:11:BC:70",medicine:"Ceftriaxone",dosage:"1 g",route:"IV",time:"08:30",prescriber:"Dr. Priya Nair",status:"Administered"},
  {id:"dose-4",patient:"Aarav Sharma",rfid:"04:A8:91:7C",medicine:"Atorvastatin",dosage:"10 mg",route:"Oral",time:"21:00",prescriber:"Dr. Rohan Mehta",status:"Waiting Pharmacy"},
];

export const demoBeds = [
  {id:"ER-04",type:"Emergency",ward:"Emergency",occupied:true,patient:"Aarav Sharma",rfid:"04:A8:91:7C",sensor:"live",cleaning:"Ready",reserved:false,incoming:null},
  {id:"ICU-02",type:"ICU",ward:"ICU",occupied:true,patient:"Neha Kapoor",rfid:"A1:09:CC:32",sensor:"demo",cleaning:"Ready",reserved:false,incoming:null},
  {id:"ER-05",type:"Emergency",ward:"Emergency",occupied:false,patient:null,rfid:null,sensor:"demo",cleaning:"Ready",reserved:true,incoming:"AMB-108"},
  {id:"GEN-12",type:"General",ward:"Ward B",occupied:true,patient:"Vikram Singh",rfid:"92:11:BC:70",sensor:"demo",cleaning:"Ready",reserved:false,incoming:null},
  {id:"GEN-13",type:"General",ward:"Ward B",occupied:false,patient:null,rfid:null,sensor:"demo",cleaning:"Cleaning",reserved:false,incoming:null},
  {id:"PVT-07",type:"Private",ward:"Private",occupied:false,patient:null,rfid:null,sensor:"demo",cleaning:"Ready",reserved:false,incoming:null},
];
