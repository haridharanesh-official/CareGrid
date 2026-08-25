export const demoAmbulances = [
  {id:"AMB-108",eta:8,type:"Cardiac",severity:"Critical",patient:"Rakesh Patel",vitals:{heartRate:118,spo2:91},department:"Cardiology",bed:"Emergency",status:"Pre-alert received",destination:"CityCare Multi-Speciality Hospital"},
  {id:"AMB-204",eta:14,type:"Road traffic accident",severity:"High",patient:"Unknown male",vitals:{heartRate:104,spo2:94},department:"Trauma",bed:"Emergency",status:"Awaiting acceptance",destination:"CityCare Multi-Speciality Hospital"},
];

export const demoAlerts = [
  {id:"a1",severity:"critical",source:"Ambulance AMB-108",message:"Incoming cardiac emergency — ETA 8 minutes",timestamp:"Now",acknowledged:false,action:"Open emergency"},
  {id:"a2",severity:"warning",source:"hospital_ward_01",message:"Vital sensor requires calibration check",timestamp:"2 min ago",acknowledged:false,action:"View sensor"},
  {id:"a3",severity:"warning",source:"Pharmacy",message:"O-negative blood stock below configured threshold",timestamp:"6 min ago",acknowledged:false,action:"View availability"},
  {id:"a4",severity:"info",source:"Bed ER-05",message:"Bed reserved for incoming ambulance AMB-108",timestamp:"8 min ago",acknowledged:true,action:"View bed"},
];
