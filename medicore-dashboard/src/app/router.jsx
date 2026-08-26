import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./providers.jsx";
import AmbulanceLayout from "../layouts/AmbulanceLayout.jsx";
import NurseLayout from "../layouts/NurseLayout.jsx";
import DoctorLayout from "../layouts/DoctorLayout.jsx";
import { Login } from "../pages/auth/Login.jsx";
import * as Ambulance from "../pages/ambulance/Pages.jsx";
import * as Nurse from "../pages/nurse/Pages.jsx";
import RealtimeDashboard from "../pages/nurse/RealtimeDashboard.jsx";
import RealtimeRFID from "../pages/nurse/RealtimeRFID.jsx";
import RealtimeWards from "../pages/nurse/RealtimeWards.jsx";
import * as Doctor from "../pages/doctor/Pages.jsx";
import DoctorDashboard from "../pages/doctor/DoctorDashboard.jsx";

function AuthGate({children}){const {session}=useAuth(),location=useLocation();return session?children:<Navigate to="/login" replace state={{from:location.pathname}}/>}
function RoleGate({role,children}){const {session}=useAuth();return session?.role===role?children:<Navigate to={`/${session?.role||"ambulance"}/dashboard`} replace/>}
const protectedRole=(role,Layout)=><AuthGate><RoleGate role={role}><Layout/></RoleGate></AuthGate>;
export function AppRouter(){return <BrowserRouter><Routes>
  <Route path="/login" element={<Login/>}/>
  <Route path="/ambulance" element={protectedRole("ambulance",AmbulanceLayout)}><Route index element={<Navigate to="dashboard" replace/>}/><Route path="dashboard" element={<Ambulance.Dashboard/>}/><Route path="emergency" element={<Ambulance.Emergency/>}/><Route path="patient" element={<Ambulance.Patient/>}/><Route path="hospital-finder" element={<Ambulance.HospitalFinder/>}/><Route path="pre-alert" element={<Ambulance.PreAlert/>}/><Route path="history" element={<Ambulance.History/>}/></Route>
  <Route path="/nurse" element={protectedRole("nurse",NurseLayout)}><Route index element={<Navigate to="dashboard" replace/>}/><Route path="dashboard" element={<RealtimeDashboard/>}/><Route path="wards" element={<RealtimeWards/>}/><Route path="beds" element={<Nurse.Beds/>}/><Route path="patients" element={<Nurse.Patients/>}/><Route path="rfid" element={<RealtimeRFID/>}/><Route path="medications" element={<Nurse.Medications/>}/><Route path="pharmacy" element={<Nurse.Pharmacy/>}/><Route path="tasks" element={<Nurse.Tasks/>}/><Route path="alerts" element={<Nurse.Alerts/>}/></Route>
  <Route path="/doctor" element={protectedRole("doctor",DoctorLayout)}><Route index element={<Navigate to="dashboard" replace/>}/><Route path="dashboard" element={<DoctorDashboard/>}/><Route path="emergencies" element={<Doctor.Emergencies/>}/><Route path="patients" element={<Doctor.Patients/>}/><Route path="patient/:id" element={<Doctor.PatientDetail/>}/><Route path="prescriptions" element={<Doctor.Prescriptions/>}/><Route path="orders" element={<Doctor.Orders/>}/><Route path="ambulances" element={<Doctor.Ambulances/>}/><Route path="beds" element={<Doctor.Beds/>}/><Route path="pharmacy" element={<Doctor.Pharmacy/>}/><Route path="reports" element={<Doctor.Reports/>}/></Route>
  <Route path="/" element={<HomeRedirect/>}/><Route path="*" element={<Navigate to="/" replace/>}/>
</Routes></BrowserRouter>}
function HomeRedirect(){const {session}=useAuth();return <Navigate to={session?`/${session.role}/dashboard`:"/login"} replace/>}
