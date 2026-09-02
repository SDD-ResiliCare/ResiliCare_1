import React, { useState, useEffect, useRef } from 'react';
import { LayoutDashboard, Download, Star, Plus, Bell, Mail, Search, SlidersHorizontal, Calendar, ChevronDown, ArrowUpRight, ArrowDownRight, Heart, Video, Mic, PhoneOff, AlertTriangle, ShieldCheck, Activity, HeartPulse, Thermometer, Wind, Droplets, Brain, Clock, CreditCard, ClipboardList, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '../lib/utils';
import { api } from '../api';
import { QueueSnapshot, Patient } from '../types';

const AllocationSelector = ({ patient, onAllocate }: { key?: React.Key; patient: Patient; onAllocate: (data: any) => void }) => {
  const [hospitals, setHospitals] = useState<any[]>([]);
  const [wards, setWards] = useState<any[]>([]);
  const [doctors, setDoctors] = useState<any[]>([]);
  
  const [selectedHospital, setSelectedHospital] = useState(patient.allocation?.hospital_id || '');
  const [selectedWard, setSelectedWard] = useState(patient.allocation?.suggested_ward?.id || '');
  const [selectedDoctor, setSelectedDoctor] = useState(patient.allocation?.primary_doctor?.id || '');

  useEffect(() => {
    api.getHospitals().then(setHospitals);
  }, []);

  useEffect(() => {
    if (selectedHospital) {
      api.getWards(selectedHospital).then(setWards);
    } else {
      setWards([]);
    }
  }, [selectedHospital]);

  useEffect(() => {
    if (selectedWard) {
      Promise.all([api.getDoctors(selectedWard), api.getDoctorWorkloads()]).then(([wardDoctors, workloads]) => {
        const workloadByDoctor = new Map(workloads.map((workload: any) => [workload.doctor.id, workload]));
        setDoctors(wardDoctors.map((doctor: any) => {
          const workload = workloadByDoctor.get(doctor.id);
          return workload
            ? { ...doctor, availability: workload.availability, waiting_count: workload.waiting_count }
            : { ...doctor, availability: 'unknown', waiting_count: 0 };
        }));
      });
    } else {
      setDoctors([]);
    }
  }, [selectedWard]);

  useEffect(() => {
    onAllocate({
      hospital_id: selectedHospital,
      ward_id: selectedWard,
      doctor_id: selectedDoctor
    });
  }, [selectedHospital, selectedWard, selectedDoctor]);

  return (
    <div className="space-y-3 relative z-10 flex-1 mb-2 border-t border-white/10 pt-4 mt-4">
      <div className="flex flex-col gap-1">
        <label className="text-[10px] text-gray-500 uppercase tracking-wider font-bold">Hospital</label>
        <select 
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[13px] font-semibold text-[#D6FF38] focus:outline-none focus:border-[#D6FF38] appearance-none cursor-pointer"
          value={selectedHospital}
          onChange={(e) => { setSelectedHospital(e.target.value); setSelectedWard(''); setSelectedDoctor(''); }}
        >
          <option value="" disabled className="text-black">Select Hospital...</option>
          {hospitals.map(h => (
            <option key={h.id} value={h.id} className="text-black">{h.name}</option>
          ))}
          {patient.allocation?.hospital_id && !hospitals.find(h => h.id === patient.allocation!.hospital_id) && (
            <option value={patient.allocation.hospital_id} className="text-black">{patient.allocation.hospital_name}</option>
          )}
        </select>
      </div>

      <div className="flex flex-col gap-1 mt-2">
        <label className="text-[10px] text-gray-500 uppercase tracking-wider font-bold">Ward</label>
        <select 
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[13px] font-semibold text-[#D6FF38] focus:outline-none focus:border-[#D6FF38] appearance-none cursor-pointer disabled:opacity-50"
          value={selectedWard}
          onChange={(e) => { setSelectedWard(e.target.value); setSelectedDoctor(''); }}
          disabled={!selectedHospital}
        >
          <option value="" disabled className="text-black">Select Ward...</option>
          {wards.map(w => (
            <option key={w.id} value={w.id} className="text-black">{w.name}</option>
          ))}
          {patient.allocation?.suggested_ward?.id && !wards.find(w => w.id === patient.allocation!.suggested_ward!.id) && (
            <option value={patient.allocation.suggested_ward.id} className="text-black">{patient.allocation.suggested_ward.name}</option>
          )}
        </select>
      </div>
      
      <div className="flex flex-col gap-1 mt-2">
        <label className="text-[10px] text-gray-500 uppercase tracking-wider font-bold">Primary Doctor</label>
        <select 
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[13px] font-semibold text-white focus:outline-none focus:border-[#D6FF38] appearance-none cursor-pointer disabled:opacity-50"
          value={selectedDoctor}
          onChange={(e) => setSelectedDoctor(e.target.value)}
          disabled={!selectedWard}
        >
            <option value="" className="text-black">Unassigned</option>
          {doctors.map(d => (
            <option key={d.id} value={d.id} className="text-black">
              Dr. {d.first_name} {d.last_name} — {d.availability === 'busy' ? `${d.waiting_count || 0} waiting` : 'Free'}
            </option>
          ))}
          {patient.allocation?.primary_doctor?.id && !doctors.find(d => d.id === patient.allocation!.primary_doctor!.id) && (
            <option value={patient.allocation.primary_doctor.id} className="text-black">Dr. {patient.allocation.primary_doctor.first_name} {patient.allocation.primary_doctor.last_name}</option>
          )}
        </select>
      </div>
    </div>
  );
};

export function NurseDashboard() {
  const VitalIndicator = ({ value, baseline, inverse = false }: { value?: number, baseline: number, inverse?: boolean }) => {
    if (value === undefined || value === null) return null;
    const diff = Math.round((value - baseline) * 10) / 10;
    if (diff === 0) return null;
    
    const isPositive = diff > 0;
    const color = inverse 
      ? (diff < 0 ? 'text-red-500 bg-red-500/10' : 'text-emerald-500 bg-emerald-500/10') 
      : (diff > 0 ? 'text-red-500 bg-red-500/10' : 'text-emerald-500 bg-emerald-500/10');
    
    return (
      <div className={`flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-md ${color}`}>
        {isPositive ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
        {Math.abs(diff)}
      </div>
    );
  };

  const [isSurgeMode, setIsSurgeMode] = useState(false);
  const [queueData, setQueueData] = useState<QueueSnapshot | null>(null);
  const [activePatientId, setActivePatientId] = useState<string | null>(null);
  const [doctorWorkloads, setDoctorWorkloads] = useState<any[]>([]);
  const [mlSuggestion, setMlSuggestion] = useState<any | null>(null);
  const [isLoadingML, setIsLoadingML] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleWheel = (e: WheelEvent) => {
      if (scrollContainerRef.current) {
        e.preventDefault();
        scrollContainerRef.current.scrollBy({ left: e.deltaY, behavior: 'smooth' });
      }
    };
    
    const container = scrollContainerRef.current;
    if (container) {
      container.addEventListener('wheel', handleWheel, { passive: false });
    }
    return () => {
      if (container) {
        container.removeEventListener('wheel', handleWheel);
      }
    };
  }, []);

  useEffect(() => {
    api.getQueue().then(data => {
      setQueueData(data);
      if (data && data.patients.length > 0) {
        setActivePatientId(data.patients[0].id);
      }
    });
    api.getDoctorWorkloads().then(data => setDoctorWorkloads(data));
  }, []);

  const activePatient = queueData?.patients.find(p => p.id === activePatientId) || null;

  useEffect(() => {
    if (activePatient?.encounter_id) {
      setIsLoadingML(true);
      api.getMLSuggestion(activePatient.encounter_id).then(data => {
        setMlSuggestion(data);
        setIsLoadingML(false);
      });
    } else {
      setMlSuggestion(null);
    }
  }, [activePatient?.encounter_id]);

  if (!queueData) return <div className="p-8 text-gray-500">Loading queue...</div>;

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col p-8 pb-0 overflow-y-auto custom-scrollbar pr-4 relative">
        
        {/* Top Navigation Strip */}
        <header className="flex items-center justify-between mb-12">
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 bg-white text-black px-4 py-2.5 rounded-full text-sm font-semibold shadow-sm">
              <LayoutDashboard className="w-[18px] h-[18px]" /> Dashboard
            </button>
            <button 
              onClick={() => setIsSurgeMode(!isSurgeMode)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-bold transition-colors ${
                isSurgeMode 
                  ? 'bg-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]' 
                  : 'border border-white/10 text-white hover:bg-white/5'
              }`}
            >
              {isSurgeMode ? <Activity className="w-[18px] h-[18px]" /> : <HeartPulse className="w-[18px] h-[18px]" />} 
              {isSurgeMode ? 'Surge Mode ON' : 'Enable Surge'}
            </button>
          </div>

          <div className="flex items-center gap-8">
            <div className="flex items-center">
              <div className="flex -space-x-3">
                <img src="https://i.pravatar.cc/150?u=a1" className="w-9 h-9 rounded-full border-[3px] border-[#111215] relative z-30" />
                <img src="https://i.pravatar.cc/150?u=a2" className="w-9 h-9 rounded-full border-[3px] border-[#111215] relative z-20" />
                <img src="https://i.pravatar.cc/150?u=a3" className="w-9 h-9 rounded-full border-[3px] border-[#111215] relative z-10" />
                <div className="w-9 h-9 rounded-full border-[3px] border-[#111215] relative z-0 bg-white text-black flex items-center justify-center text-xs font-bold">+6</div>
              </div>
            </div>

            <div className="flex items-center gap-4 border-l border-white/10 pl-8">
              <button className="w-11 h-11 rounded-full border border-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors">
                <Bell className="w-5 h-5" />
              </button>
              <button className="w-11 h-11 rounded-full border border-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors">
                <Mail className="w-5 h-5" />
              </button>
              <img src="https://i.pravatar.cc/150?u=a4" className="w-11 h-11 rounded-full border border-white/20 ml-2" />
            </div>
          </div>
        </header>

        {/* Dashboard Title & Stats */}
        <div className={`flex items-end justify-between mb-12 transition-all duration-300 ${isSurgeMode ? 'hidden' : 'flex'}`}>
          <div className="flex items-center gap-6">
            <h1 className="text-[3.5rem] leading-none font-light tracking-tight">Dashboard</h1>
            <button className="border border-white/20 border-dashed rounded-full px-5 py-2 text-sm font-medium text-gray-400 hover:text-white hover:border-white flex items-center gap-2 mb-2 transition-all">
              <Plus className="w-4 h-4" /> Patient
            </button>
          </div>
          
          <div className="flex items-center gap-16 mb-2">
            <div className="flex flex-col items-start">
              <div className="flex items-start gap-1">
                <span className="text-[2.75rem] leading-none font-light">34</span>
                <span className="text-[#D6FF38] text-xs font-semibold mt-1.5 tracking-wide">+4</span>
              </div>
              <span className="text-sm text-gray-500 font-medium mt-1">Queue Length</span>
            </div>
            <div className="flex flex-col items-start">
              <div className="flex items-start gap-1">
                <span className="text-[2.75rem] leading-none font-light">12</span>
                <span className="text-[#D6FF38] text-xs font-semibold mt-1.5 tracking-wide">+2</span>
              </div>
              <span className="text-sm text-gray-500 font-medium mt-1">Total Assigned</span>
            </div>
            <div className="flex flex-col items-start">
              <div className="flex items-start gap-1">
                <span className="text-[2.75rem] leading-none font-light">6</span>
                <span className="text-red-500 text-xs font-semibold mt-1.5 tracking-wide">-2</span>
              </div>
              <span className="text-sm text-gray-500 font-medium mt-1">Total Available Doctors</span>
            </div>
          </div>
        </div>

        {/* Search & Filters */}
        <div className={`flex items-center justify-between mb-10 transition-all duration-300 ${isSurgeMode ? 'hidden' : 'flex'}`}>
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
              <input 
                type="text" 
                placeholder="Search" 
                className="bg-[#1C1D21] text-sm text-white rounded-full pl-11 pr-4 py-3 outline-none w-72 border border-transparent focus:border-white/20 transition-all placeholder:text-gray-500" 
              />
            </div>
            <button className="text-gray-400 hover:text-white w-10 h-10 flex items-center justify-center transition-colors">
              <SlidersHorizontal className="w-5 h-5" />
            </button>
          </div>

          <div className="flex items-center gap-3">
            <button className="px-5 py-2.5 rounded-full border border-white/10 text-xs font-medium text-gray-300 hover:text-white hover:bg-white/5 transition-all">Heart problems</button>
            <button className="px-5 py-2.5 rounded-full border border-white/10 text-xs font-medium text-gray-300 hover:text-white hover:bg-white/5 transition-all">Lung problems</button>
            <button className="px-5 py-2.5 rounded-full border border-white/10 text-xs font-medium text-gray-300 hover:text-white hover:bg-white/5 transition-all">Intestinal problems</button>
            <button className="px-5 py-2.5 rounded-full border border-white/10 text-xs font-medium text-white flex items-center gap-2 ml-2 hover:bg-white/5 transition-all">
              <Calendar className="w-3.5 h-3.5" /> 20-27 Jan, 2025 <ChevronDown className="w-3.5 h-3.5 ml-1" />
            </button>
          </div>
        </div>

        {/* Patient Cards */}
        <div 
          ref={scrollContainerRef}
          className="flex overflow-x-auto gap-6 mb-12 custom-scrollbar pb-12 snap-x snap-mandatory hide-scroll items-start min-h-[460px] h-fit shrink-0"
        >
          {!queueData ? (
             <div className="text-white w-full text-center py-12">Loading queue...</div>
          ) : queueData.patients.length === 0 ? (
             <div className="text-white w-full text-center py-12">No patients in queue.</div>
          ) : queueData.patients.map((patient) => {
             const isActive = patient.id === activePatientId;
             return (
               <div 
                 key={patient.id} 
                 onClick={() => setActivePatientId(patient.id)}
                 className={`min-w-[380px] min-h-[440px] h-auto shrink-0 snap-start cursor-pointer ${isActive ? "bg-[#D6FF38] text-black rounded-[2rem] p-7 relative flex flex-col shadow-[0_10px_30px_rgba(214,255,56,0.15)] overflow-hidden" : "bg-[#18191C] border border-[#2A2B30] text-white rounded-[2rem] p-7 relative flex flex-col hover:border-[#D6FF38]/30 transition-all duration-300 group"}`}
               >
                 {isActive && <div className="absolute -top-12 -right-12 w-48 h-48 bg-white/20 rounded-full blur-3xl pointer-events-none" />}
                 
                 <button className={`absolute top-6 right-6 w-9 h-9 rounded-full flex items-center justify-center transition-colors z-10 ${isActive ? 'bg-black/5 hover:bg-black/10' : 'bg-white/5 text-gray-400 group-hover:text-white group-hover:bg-white/10'}`}>
                   <ArrowUpRight className="w-4 h-4" />
                 </button>

                 <div className={`flex items-${isActive ? 'start justify-between' : 'center'} gap-4 mb-${isActive ? '8' : '10'} relative z-10`}>
                   {isActive ? (
                     <div className="flex items-center gap-4">
                       <img src={patient.avatar} className="w-14 h-14 rounded-full shadow-sm" />
                       <div>
                         <h3 className="font-semibold text-[1.35rem] leading-tight">{patient.name}</h3>
                         <p className="text-[13px] opacity-70 font-semibold tracking-wide uppercase mt-0.5">{patient.age} yrs &bull; ESI Level {patient.esi || 'Unknown'}</p>
                       </div>
                     </div>
                   ) : (
                     <>
                       <img src={patient.avatar} className="w-14 h-14 rounded-full" />
                       <div>
                         <h3 className="font-semibold text-[1.35rem] leading-tight">{patient.name}</h3>
                         <p className="text-[13px] text-gray-400 font-semibold tracking-wide uppercase mt-0.5">{patient.age} yrs &bull; ESI Level {patient.esi || 'Unknown'}</p>
                       </div>
                     </>
                   )}
                 </div>

                 {!isSurgeMode ? (
                   <>
                     <div className="grid grid-cols-2 gap-3 mb-6 relative z-10">
                       {/* HR */}
                       <div className={isActive ? "bg-black/5 rounded-2xl p-3 px-4" : "bg-white/5 border border-white/5 rounded-2xl p-3 px-4"}>
                         <div className={`flex items-center gap-2 mb-2 ${isActive ? 'opacity-60' : 'text-gray-500'}`}>
                           <HeartPulse className="w-3.5 h-3.5" />
                           <span className="text-[10px] font-bold uppercase tracking-wider">HR</span>
                         </div>
                         <div className="flex items-end justify-between">
                           <span className={`text-xl font-bold leading-none ${!isActive ? 'text-gray-300' : ''}`}>{patient.vitals?.heart_rate_bpm || '--'}</span>
                           {patient.vitals?.heart_rate_bpm && <VitalIndicator value={Number(patient.vitals.heart_rate_bpm)} baseline={80} />}
                         </div>
                       </div>
                       
                       {/* SpO2 */}
                       <div className={isActive ? "bg-black/5 rounded-2xl p-3 px-4" : "bg-white/5 border border-white/5 rounded-2xl p-3 px-4"}>
                         <div className={`flex items-center gap-2 mb-2 ${isActive ? 'opacity-60' : 'text-gray-500'}`}>
                           <Droplets className="w-3.5 h-3.5" />
                           <span className="text-[10px] font-bold uppercase tracking-wider">SpO₂</span>
                         </div>
                         <div className="flex items-end justify-between">
                           <span className={`text-xl font-bold leading-none ${!isActive ? 'text-gray-300' : ''}`}>{patient.vitals?.spo2_percent ? `${patient.vitals.spo2_percent}%` : '--'}</span>
                           {patient.vitals?.spo2_percent && <VitalIndicator value={Number(patient.vitals.spo2_percent)} baseline={98} inverse={true} />}
                         </div>
                       </div>

                       {/* BP */}
                       <div className={isActive ? "bg-black/5 rounded-2xl p-3 px-4" : "bg-white/5 border border-white/5 rounded-2xl p-3 px-4"}>
                         <div className={`flex items-center gap-2 mb-2 ${isActive ? 'opacity-60' : 'text-gray-500'}`}>
                           <Activity className="w-3.5 h-3.5" />
                           <span className="text-[10px] font-bold uppercase tracking-wider">BP</span>
                         </div>
                         <div className="flex items-end justify-between">
                           <span className={`text-xl font-bold leading-none ${!isActive ? 'text-gray-300' : ''}`}>{patient.vitals?.systolic_bp_mmhg ? `${patient.vitals.systolic_bp_mmhg}/${patient.vitals.diastolic_bp_mmhg}` : '--'}</span>
                           {patient.vitals?.systolic_bp_mmhg && <VitalIndicator value={Number(patient.vitals.systolic_bp_mmhg)} baseline={120} />}
                         </div>
                       </div>

                       {/* Temp */}
                       <div className={isActive ? "bg-black/5 rounded-2xl p-3 px-4" : "bg-white/5 border border-white/5 rounded-2xl p-3 px-4"}>
                         <div className={`flex items-center gap-2 mb-2 ${isActive ? 'opacity-60' : 'text-gray-500'}`}>
                           <Thermometer className="w-3.5 h-3.5" />
                           <span className="text-[10px] font-bold uppercase tracking-wider">Temp</span>
                         </div>
                         <div className="flex items-end justify-between">
                           <span className={`text-xl font-bold leading-none ${!isActive ? 'text-gray-300' : ''}`}>{patient.vitals?.temperature_c ? `${patient.vitals.temperature_c}°` : '--'}</span>
                           {patient.vitals?.temperature_c && <VitalIndicator value={Number(patient.vitals.temperature_c)} baseline={37.0} />}
                         </div>
                       </div>
                     </div>

                     <div className={`mb-8 relative z-10 rounded-xl p-3 flex items-start gap-3 ${isActive ? 'bg-black/5 border border-black/5' : 'bg-white/5 border border-white/5'}`}>
                       <ClipboardList className={`w-4 h-4 mt-0.5 shrink-0 ${isActive ? 'opacity-60' : 'text-gray-500'}`} />
                       <p className={`text-[13px] leading-snug ${isActive ? 'font-semibold opacity-90' : 'font-medium text-gray-300'}`}>{patient.complaint || 'No complaint recorded'}</p>
                     </div>

                     <div className={`flex items-center justify-between mt-auto relative z-10 ${isActive ? 'pt-4 border-t border-black/10' : ''}`}>
                       <div className="flex items-center gap-2">
                         {isActive ? (
                           <>
                             <AlertTriangle className="w-4 h-4 text-red-500" />
                             <span className="text-[13px] font-bold text-red-600">Cardiac Risk</span>
                           </>
                         ) : (
                           <>
                             <div className="w-2.5 h-2.5 rounded-full bg-[#D6FF38]" />
                             <span className="text-[13px] font-semibold">Observation</span>
                           </>
                         )}
                       </div>
                       {isActive ? (
                         <span className="text-[12px] font-bold bg-black text-white px-3 py-1.5 rounded-full">Triage Ready</span>
                       ) : (
                         <span className="text-[13px] font-medium text-gray-500">{new Date(patient.timeInQueue).toLocaleDateString()}</span>
                       )}
                     </div>
                   </>
                 ) : (
                    <div className={`rounded-2xl p-5 relative overflow-hidden mt-2 flex-1 flex flex-col justify-center animate-in fade-in duration-500 ${isActive ? 'bg-[#111215] text-white border border-white/10' : 'bg-black/20 text-white border border-white/5'}`}>
                      {isActive && <div className="absolute top-0 right-0 w-32 h-32 bg-[#D6FF38]/10 blur-3xl rounded-full pointer-events-none" />}
                      <div className="flex items-center justify-between mb-4 relative z-10">
                        <div className="flex items-center gap-2 text-gray-400">
                          <Brain className="w-4 h-4" />
                          <span className="text-xs font-semibold uppercase tracking-wide">AI Recommendation</span>
                        </div>
                        <span className="bg-[#D6FF38]/20 text-[#D6FF38] text-[10px] font-bold px-2 py-1 rounded-full flex items-center gap-1">
                           <Activity className="w-3 h-3" /> 94% Confidence
                        </span>
                      </div>
                      
                      <p className="text-[11px] text-gray-400 font-medium leading-relaxed relative z-10 mb-3">
                        {patient.aiOverview || `AI suggests ESI Level ${patient.aiSuggestion?.esi || patient.esi || 'Unknown'}.`}
                      </p>
                      
                      <div className="space-y-3 relative z-10 flex-1 mb-2">
                         <div className="flex flex-col gap-1">
                            <label className="text-[10px] text-gray-500 uppercase tracking-wider font-bold">ESI Level</label>
                            <select 
                             value={patient.esi || ''}
                             readOnly
                             disabled={!isActive}
                             className={`bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[13px] font-semibold focus:outline-none focus:border-[#D6FF38] appearance-none ${isActive ? 'text-[#D6FF38] cursor-pointer' : 'text-gray-500 cursor-default'}`}
                            >
                               <option value="1">Level 1 - Resuscitation</option>
                               <option value="2">Level 2 - Emergent</option>
                               <option value="3">Level 3 - Urgent</option>
                               <option value="4">Level 4 - Less Urgent</option>
                               <option value="5">Level 5 - Non-Urgent</option>
                            </select>
                         </div>
                      </div>
                      
                      {patient.allocation && (
                        <div className={!isActive ? 'opacity-50 pointer-events-none' : ''}>
                          <AllocationSelector patient={patient} onAllocate={(data) => {}} />
                        </div>
                      )}
                      
                      <div className="flex gap-3 mt-auto pt-4 border-t border-white/10 relative z-10">
                        <button className={`flex-1 font-semibold text-sm py-2.5 rounded-full transition-colors ${isActive ? 'bg-[#D6FF38] text-black hover:bg-[#c2e633]' : 'bg-white/10 text-white hover:bg-white/20'}`}>Approve</button>
                        <button className={`flex-1 font-medium text-sm py-2.5 rounded-full transition-colors ${isActive ? 'border border-white/20 text-white hover:bg-white/5' : 'border border-white/10 text-gray-400 hover:text-white'}`}>Bring Next</button>
                      </div>
                    </div>
                 )}
               </div>
             );
          })}
        </div>

        {/* Timeline Area */}
        <div className="mt-6 mb-12 flex-1">
          <h3 className="text-xl font-medium mb-6">Schedule</h3>
          
          <div className="flex flex-col gap-8">
            
            {doctorWorkloads.length === 0 ? (
              <div className="text-gray-500 text-sm">No doctor workloads found.</div>
            ) : doctorWorkloads.map((workload, index) => (
              <div key={workload.doctor.id || index} className="flex items-start gap-4 lg:gap-6">
                <div className="w-32 pt-3 shrink-0">
                   <div className="text-sm font-bold text-gray-200">
                     Dr. {workload.doctor.first_name?.charAt(0)}. {workload.doctor.last_name || workload.doctor.first_name}
                   </div>
                   <div className="text-[11px] font-semibold text-gray-500 mt-0.5">
                     {workload.current_patient?.ward?.name || 'Assigned Ward'}
                   </div>
                   <div className="text-[10px] font-bold mt-1 uppercase tracking-wider text-[#D6FF38]">
                     {workload.availability}
                   </div>
                </div>
                <div className="flex-1 grid grid-cols-1 xl:grid-cols-2 gap-4">
                   
                   {workload.waiting_patients.length === 0 && !workload.current_patient ? (
                     <div className="text-sm text-gray-500 mt-3">No patients in queue.</div>
                   ) : null}

                   {/* Current Patient */}
                   {workload.current_patient && (
                     <div className="bg-[#18191C] border border-[#D6FF38]/20 rounded-2xl p-4 flex gap-4 items-center relative overflow-hidden group hover:border-[#D6FF38]/40 transition-colors">
                       <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#D6FF38]" />
                       <img src={`https://i.pravatar.cc/150?u=${workload.current_patient.patient_id}`} className="w-10 h-10 rounded-full shrink-0" />
                       <div className="flex flex-col flex-1 min-w-0">
                         <span className="text-sm font-bold text-white truncate">{workload.current_patient.patient_name}</span>
                         <span className="text-xs text-gray-400 mt-0.5 truncate">Level {workload.current_patient.confirmed_esi}</span>
                       </div>
                       <span className="bg-[#D6FF38]/10 text-[#D6FF38] text-[11px] font-bold px-2.5 py-1 rounded-md shrink-0 border border-[#D6FF38]/20">Current</span>
                     </div>
                   )}

                   {/* Queued Patients */}
                   {workload.waiting_patients.map((wp: any, i: number) => (
                     <div key={wp.work_item_id || i} className="bg-[#18191C] border border-white/5 rounded-2xl p-4 flex gap-4 items-center relative overflow-hidden group hover:border-white/10 transition-colors">
                       <div className="absolute left-0 top-0 bottom-0 w-1 bg-white/20" />
                       <img src={`https://i.pravatar.cc/150?u=${wp.patient_id}`} className="w-10 h-10 rounded-full shrink-0" />
                       <div className="flex flex-col flex-1 min-w-0">
                         <span className="text-sm font-bold text-white truncate">{wp.patient_name}</span>
                         <span className="text-xs text-gray-400 mt-0.5 truncate">Level {wp.confirmed_esi}</span>
                       </div>
                       <span className="bg-white/5 text-gray-300 text-[11px] font-bold px-2.5 py-1 rounded-md shrink-0">Queue #{wp.queue_position || i + 1}</span>
                     </div>
                   ))}
                   
                </div>
              </div>
            ))}

          </div>
        </div>

      </div>

      {/* Right Overview Panel - Clinical Data */}
      {activePatient && (
        <div className="w-[360px] bg-white rounded-[2rem] m-6 ml-0 flex flex-col p-6 relative shadow-xl shrink-0 overflow-y-auto no-scrollbar animate-in fade-in slide-in-from-right-8 duration-500">
          {/* Header - Profile */}
        <div className="shrink-0 flex items-center justify-between mb-6">
           <div className="flex items-center gap-3">
              <img src={activePatient.avatar} className="w-12 h-12 rounded-full shadow-sm" alt="Patient" />
              <div>
                 <h2 className="text-[1.2rem] font-bold text-black leading-tight">{activePatient.name}</h2>
                 <p className="text-xs text-gray-500 font-medium">{activePatient.age} yrs • #{activePatient.id.substring(0, 8)}</p>
              </div>
           </div>
           <button className="w-8 h-8 rounded-full border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-gray-50 transition">
              <ArrowUpRight className="w-4 h-4" />
           </button>
        </div>

        {/* AI ESI Suggestion */}
        {!isSurgeMode && (
          <div className="shrink-0 bg-[#111215] text-white rounded-2xl p-5 mb-5 relative overflow-hidden">
           <div className="absolute top-0 right-0 w-32 h-32 bg-[#D6FF38]/10 blur-3xl rounded-full pointer-events-none" />
           <div className="flex items-center justify-between mb-4 relative z-10">
             <div className="flex items-center gap-2 text-gray-400">
                <Brain className="w-4 h-4" />
                <span className="text-xs font-semibold uppercase tracking-wide">AI Recommendation</span>
             </div>
             <span className="bg-[#D6FF38]/20 text-[#D6FF38] text-[10px] font-bold px-2 py-1 rounded-full flex items-center gap-1">
                <Activity className="w-3 h-3" /> 94% Confidence
             </span>
           </div>
           
           <p className="text-[11px] text-gray-300 font-medium leading-relaxed relative z-10 mb-3">
             {activePatient.aiOverview || `AI suggests ESI Level ${activePatient.aiSuggestion?.esi || activePatient.esi || 'Unknown'}.`}
           </p>
           
           <div className="space-y-3 relative z-10 flex-1 mb-2">
              <div className="flex flex-col gap-1">
                 <label className="text-[10px] text-gray-500 uppercase tracking-wider font-bold">ESI Level</label>
                 <select 
                  value={activePatient.esi || ''}
                  readOnly
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[13px] font-semibold text-[#D6FF38] focus:outline-none focus:border-[#D6FF38] appearance-none cursor-pointer"
                 >
                    <option value="1">Level 1 - Resuscitation</option>
                    <option value="2">Level 2 - Emergent</option>
                    <option value="3">Level 3 - Urgent</option>
                    <option value="4">Level 4 - Less Urgent</option>
                    <option value="5">Level 5 - Non-Urgent</option>
                 </select>
              </div>
           </div>
           
            {activePatient.allocation && (
              <AllocationSelector key={activePatient.id} patient={activePatient} onAllocate={(data) => {
                // In future: update local state or prep for Approve button click
              }} />
            )}
            
            <div className="flex gap-3 mt-4 pt-4 border-t border-white/10 relative z-10">
             <button className="flex-1 bg-[#D6FF38] text-black font-semibold text-sm py-2.5 rounded-full hover:bg-[#c2e633] transition-colors">Approve</button>
             <button className="flex-1 border border-white/20 text-white font-medium text-sm py-2.5 rounded-full hover:bg-white/5 transition-colors">Bring Next</button>
           </div>
        </div>
        )}

        {/* Vitals Grid */}
            <div className="shrink-0 mb-5">
               <div className="flex items-center gap-2 mb-2">
             <Activity className="w-3.5 h-3.5 text-gray-400" />
             <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">Vitals</span>
           </div>
           <div className="grid grid-cols-2 gap-3">
              {/* HR Cell */}
              <div className="bg-gray-50 rounded-xl p-3 border border-gray-100 flex flex-col justify-between">
                <div className="flex items-center gap-2 text-gray-500 mb-2">
                  <HeartPulse className="w-3.5 h-3.5" />
                  <span className="text-[10px] font-bold uppercase tracking-wider">HR</span>
                </div>
                <div className="flex items-end justify-between">
                  <span className="text-xl font-bold leading-none text-black">{activePatient.vitals?.heart_rate_bpm || '--'}</span>
                  {activePatient.vitals?.heart_rate_bpm && <VitalIndicator value={Number(activePatient.vitals.heart_rate_bpm)} baseline={80} />}
                </div>
              </div>

              {/* SpO2 Cell */}
              <div className="bg-gray-50 rounded-xl p-3 border border-gray-100 flex flex-col justify-between">
                <div className="flex items-center gap-2 text-gray-500 mb-2">
                  <Droplets className="w-3.5 h-3.5" />
                  <span className="text-[10px] font-bold uppercase tracking-wider">SpO₂</span>
                </div>
                <div className="flex items-end justify-between">
                  <span className="text-xl font-bold leading-none text-black">{activePatient.vitals?.spo2_percent ? `${activePatient.vitals.spo2_percent}%` : '--'}</span>
                  {activePatient.vitals?.spo2_percent && <VitalIndicator value={Number(activePatient.vitals.spo2_percent)} baseline={98} inverse={true} />}
                </div>
              </div>

              {/* BP Cell */}
              <div className="bg-gray-50 rounded-xl p-3 border border-gray-100 flex flex-col justify-between">
                <div className="flex items-center gap-2 text-gray-500 mb-2">
                  <Activity className="w-3.5 h-3.5" />
                  <span className="text-[10px] font-bold uppercase tracking-wider">BP</span>
                </div>
                <div className="flex items-end justify-between">
                  <span className="text-xl font-bold leading-none text-black">
                    {activePatient.vitals?.systolic_bp_mmhg ? `${activePatient.vitals.systolic_bp_mmhg}/${activePatient.vitals.diastolic_bp_mmhg}` : '--'}
                  </span>
                  {activePatient.vitals?.systolic_bp_mmhg && <VitalIndicator value={Number(activePatient.vitals.systolic_bp_mmhg)} baseline={120} />}
                </div>
              </div>

              {/* Temp Cell */}
              <div className="bg-gray-50 rounded-xl p-3 border border-gray-100 flex flex-col justify-between">
                <div className="flex items-center gap-2 text-gray-500 mb-2">
                  <Thermometer className="w-3.5 h-3.5" />
                  <span className="text-[10px] font-bold uppercase tracking-wider">Temp</span>
                </div>
                <div className="flex items-end justify-between">
                  <span className="text-xl font-bold leading-none text-black">
                    {activePatient.vitals?.temperature_c ? `${activePatient.vitals.temperature_c}°` : '--'}
                  </span>
                  {activePatient.vitals?.temperature_c && <VitalIndicator value={Number(activePatient.vitals.temperature_c)} baseline={37.0} />}
                </div>
              </div>
           </div>
        </div>

        {!isSurgeMode && (
          <>
            {/* Complaint & Details */}
            <div className="shrink-0 mb-5 bg-gray-50 rounded-xl p-4 border border-gray-100 relative">
           <ClipboardList className="w-4 h-4 text-gray-400 absolute top-4 right-4" />
           <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Chief Complaint</span>
           <p className="text-[13px] font-semibold text-black mb-3 leading-tight pr-6">{activePatient.complaint || 'No complaint recorded'}</p>
        </div>

        {/* ML Clinical Rationale */}
        <div className="shrink-0 mb-5">
           <div className="flex items-center gap-2 mb-2">
              <ShieldCheck className="w-3.5 h-3.5 text-gray-400" />
              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">ML Suggestion</span>
           </div>
           
           {isLoadingML ? (
             <div className="p-4 text-sm text-gray-400 animate-pulse bg-gray-50 rounded-xl border border-gray-100">Analyzing encounter data...</div>
           ) : mlSuggestion ? (
             <div className="flex flex-col gap-2">
                <div className={`p-4 rounded-xl border ${mlSuggestion.is_uncertain ? 'bg-amber-50 border-amber-100 text-amber-800' : 'bg-emerald-50 border-emerald-100 text-emerald-800'}`}>
                   <p className="text-[12px] font-medium leading-relaxed">{mlSuggestion.clinical_rationale || 'No rationale provided.'}</p>
                   {mlSuggestion.final_esi && (
                     <div className="mt-3 inline-block px-2.5 py-1 rounded-md bg-white border border-black/5 text-[11px] font-bold shadow-sm">
                       Suggested ESI Level: {mlSuggestion.final_esi}
                     </div>
                   )}
                </div>
                {mlSuggestion.top_contributing_factors && mlSuggestion.top_contributing_factors.length > 0 && (
                  <div className="mt-2 pl-1">
                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-1.5">Top Factors</span>
                    <div className="flex flex-wrap gap-1.5">
                      {mlSuggestion.top_contributing_factors.slice(0, 3).map((factor: any, i: number) => (
                        <span key={i} className="text-[10px] font-semibold bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                          {factor.feature || factor.feature_name}
                        </span>
                      ))}

                    </div>
                  </div>
                )}
             </div>
           ) : (
             <div className="p-4 text-sm text-gray-400 bg-gray-50 rounded-xl border border-gray-100">No ML suggestion available.</div>
           )}
        </div>

        {/* History & Routing */}
        <div className="shrink-0 mt-auto space-y-5 pt-4">
           <div>
              <div className="flex items-center gap-2 mb-1">
                 <Clock className="w-3 h-3 text-gray-400" />
                 <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">Prior ResiliCare Visits</span>
              </div>
              <p className="text-[12px] font-medium text-black">None on record</p>
           </div>
           
           <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              <div>
                <div className="flex items-center gap-1.5 mb-0.5">
                   <CreditCard className="w-3 h-3 text-gray-400" />
                   <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">Financial Routing</span>
                </div>
                <span className="text-[12px] font-bold text-black">Aetna PPO (In-Network)</span>
              </div>
              <div className="text-right">
                <div className="flex items-center justify-end gap-1.5 mb-0.5">
                   <ShieldCheck className="w-3 h-3 text-gray-400" />
                   <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">ML Confidence</span>
                </div>
                <span className={`text-[12px] font-bold ${isLoadingML ? 'text-gray-400' : mlSuggestion?.is_uncertain ? 'text-amber-600' : 'text-green-600'}`}>
                  {isLoadingML ? '--' : mlSuggestion ? `${Math.round(mlSuggestion.confidence_score * 100)}% Confidence` : 'Unknown'}
                </span>
              </div>
           </div>
        </div>
          </>
        )}
      </div>
      )}
    </div>
  );
}
