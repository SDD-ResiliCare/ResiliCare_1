import React, { useState } from 'react';
import { 
  Stethoscope, Users, Activity, HeartPulse, 
  Brain, FileText, CheckCircle2, FileSignature,
  History, AlertCircle, Pill, CreditCard, ShieldCheck, Droplet
} from 'lucide-react';

export function DoctorDashboard() {
  const [notes, setNotes] = useState('');
  const [prescription, setPrescription] = useState('');
  const [visitCompleted, setVisitCompleted] = useState(false);

  const handleComplete = () => {
    setVisitCompleted(true);
    // Ideally we would sync this to a backend so the patient sees it
  };

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      <div className="flex-1 flex flex-col p-8 overflow-y-auto custom-scrollbar relative">
        
        {/* Header */}
        <header className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <button className="flex items-center gap-2 bg-white text-black px-5 py-2.5 rounded-full text-sm font-semibold shadow-sm">
              <Stethoscope className="w-5 h-5" /> Dr. Marcus Webb
            </button>
            <div className="flex items-center gap-2 border border-white/10 text-white bg-white/5 px-4 py-2.5 rounded-full text-sm font-medium">
               ER - Trauma
            </div>
          </div>
          
          <div className="flex items-center gap-3">
             <div className="px-4 py-2.5 rounded-full bg-[#8BE8E2]/10 border border-[#8BE8E2]/20 text-[#8BE8E2] text-sm font-bold flex items-center gap-2">
                <Users className="w-4 h-4" /> 3 Patients in Queue
             </div>
          </div>
        </header>

        {!visitCompleted ? (
          <div className="flex flex-col lg:flex-row gap-6 flex-1">
            
            {/* Left Panel: Patient Information */}
            <div className="flex-1 flex flex-col gap-6">
               <div className="bg-[#161B24] border border-white/10 rounded-[2rem] p-8 flex flex-col relative overflow-hidden shadow-lg">
                 <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 blur-3xl rounded-full pointer-events-none" />
                 
                 <div className="flex items-center justify-between mb-6 relative z-10">
                    <div className="flex items-center gap-4">
                       <img src="https://i.pravatar.cc/150?u=p1" className="w-16 h-16 rounded-full border-2 border-white/10 shadow-sm" alt="Patient" />
                       <div>
                          <h2 className="text-2xl font-bold text-white leading-tight">Wade Warren</h2>
                          <p className="text-sm text-gray-400 font-medium mt-1">36 yrs (Adult) • #PT-8829</p>
                       </div>
                    </div>
                    <div className="bg-red-500/10 text-red-400 border border-red-500/20 px-3 py-1.5 rounded-lg flex flex-col items-center">
                       <span className="text-[10px] font-bold uppercase tracking-wider">Triage</span>
                       <span className="text-lg font-black leading-none mt-1">Level 2</span>
                    </div>
                 </div>

                 {/* Vitals */}
                 <div className="grid grid-cols-4 gap-3 mb-6 relative z-10">
                    <div className="bg-black/20 rounded-xl p-3 border border-white/5">
                      <div className="flex items-center gap-2 text-gray-500 mb-1">
                        <HeartPulse className="w-3.5 h-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">HR</span>
                      </div>
                      <span className="text-xl font-bold text-white">110</span>
                      <span className="text-[11px] text-red-400 ml-1">bpm</span>
                    </div>
                    <div className="bg-black/20 rounded-xl p-3 border border-white/5">
                      <div className="flex items-center gap-2 text-gray-500 mb-1">
                        <Activity className="w-3.5 h-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">BP</span>
                      </div>
                      <span className="text-xl font-bold text-white">140/90</span>
                    </div>
                    <div className="bg-black/20 rounded-xl p-3 border border-white/5">
                      <div className="flex items-center gap-2 text-gray-500 mb-1">
                        <Activity className="w-3.5 h-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">O2</span>
                      </div>
                      <span className="text-xl font-bold text-white">96</span>
                      <span className="text-[11px] text-gray-400 ml-1">%</span>
                    </div>
                    <div className="bg-black/20 rounded-xl p-3 border border-white/5">
                      <div className="flex items-center gap-2 text-gray-500 mb-1">
                        <Activity className="w-3.5 h-3.5" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">Temp</span>
                      </div>
                      <span className="text-xl font-bold text-white">99.1</span>
                      <span className="text-[11px] text-gray-400 ml-1">°F</span>
                    </div>
                 </div>

                 {/* AI Triage Summary */}
                 <div className="bg-[#080A0F] border border-white/10 rounded-2xl p-5 relative z-10">
                    <div className="flex items-center gap-2 text-[#8BE8E2] mb-3">
                       <Brain className="w-4 h-4" />
                       <span className="text-xs font-bold uppercase tracking-wide">AI Intake Analysis</span>
                    </div>
                    <p className="text-sm text-gray-300 leading-relaxed">
                       High risk of cardiac ischemia. Patient reports severe, crushing chest pain radiating to the left arm, onset 45 minutes ago. Accompanied by diaphoresis and shortness of breath. Immediate ECG was recommended and performed.
                    </p>
                 </div>
               </div>

               {/* Complete Medical Profile */}
               <div className="bg-[#161B24] border border-white/10 rounded-[2rem] p-8 shadow-lg">
                  <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                     <History className="w-5 h-5 text-gray-400" /> Complete Medical Profile
                  </h3>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                     <div className="bg-black/20 rounded-xl p-3 border border-white/5 flex flex-col items-center justify-center text-center">
                        <Droplet className="w-4 h-4 text-red-400 mb-1" />
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Blood Type</span>
                        <span className="text-sm font-bold text-white mt-1">O+</span>
                     </div>
                     <div className="bg-black/20 rounded-xl p-3 border border-white/5 flex flex-col items-center justify-center text-center">
                        <Activity className="w-4 h-4 text-blue-400 mb-1" />
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Height</span>
                        <span className="text-sm font-bold text-white mt-1">6'1"</span>
                     </div>
                     <div className="bg-black/20 rounded-xl p-3 border border-white/5 flex flex-col items-center justify-center text-center">
                        <Activity className="w-4 h-4 text-blue-400 mb-1" />
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Weight</span>
                        <span className="text-sm font-bold text-white mt-1">185 lbs</span>
                     </div>
                     <div className="bg-black/20 rounded-xl p-3 border border-white/5 flex flex-col items-center justify-center text-center">
                        <Activity className="w-4 h-4 text-[#8BE8E2] mb-1" />
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">BMI</span>
                        <span className="text-sm font-bold text-white mt-1">24.4</span>
                     </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                     <div>
                        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide flex items-center gap-2 mb-3">
                           <AlertCircle className="w-4 h-4 text-orange-400" /> Known Allergies
                        </span>
                        <div className="flex flex-wrap gap-2">
                           <span className="px-3 py-1 rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20 text-sm font-medium">Penicillin</span>
                           <span className="px-3 py-1 rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20 text-sm font-medium">Latex</span>
                        </div>
                     </div>
                     <div>
                        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide flex items-center gap-2 mb-3">
                           <Pill className="w-4 h-4 text-blue-400" /> Current Medications
                        </span>
                        <ul className="text-sm text-gray-300 space-y-1">
                           <li>&bull; Lisinopril 10mg (Daily)</li>
                           <li>&bull; Atorvastatin 20mg (Daily)</li>
                        </ul>
                     </div>
                  </div>
               </div>

               {/* Billing & Insurance */}
               <div className="bg-[#161B24] border border-white/10 rounded-[2rem] p-8 shadow-lg">
                  <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                     <CreditCard className="w-5 h-5 text-gray-400" /> Billing & Insurance
                  </h3>
                  
                  <div className="flex flex-col md:flex-row gap-6">
                     <div className="flex-1 bg-black/20 rounded-xl p-5 border border-white/5">
                        <div className="flex justify-between items-start mb-4">
                           <div>
                              <div className="text-sm font-bold text-white">BlueCross BlueShield</div>
                              <div className="text-xs text-gray-400 mt-1">PPO Plan &bull; Active</div>
                           </div>
                           <ShieldCheck className="w-6 h-6 text-green-400" />
                        </div>
                        <div className="space-y-2 mt-4">
                           <div className="flex justify-between text-sm">
                              <span className="text-gray-500">Policy No.</span>
                              <span className="text-gray-300 font-medium">BCBS-8829-110</span>
                           </div>
                           <div className="flex justify-between text-sm">
                              <span className="text-gray-500">Group No.</span>
                              <span className="text-gray-300 font-medium">TX-99210</span>
                           </div>
                        </div>
                     </div>
                     
                     <div className="flex-1 bg-black/20 rounded-xl p-5 border border-white/5 flex flex-col justify-between">
                        <div className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">Current Visit Estimate</div>
                        <div className="space-y-3">
                           <div className="flex justify-between text-sm">
                              <span className="text-gray-400">ER Copay</span>
                              <span className="text-white font-medium">$150.00</span>
                           </div>
                           <div className="flex justify-between text-sm">
                              <span className="text-gray-400">Services (Est.)</span>
                              <span className="text-white font-medium">$1,200.00</span>
                           </div>
                           <div className="flex justify-between text-sm">
                              <span className="text-gray-400">Insurance Coverage</span>
                              <span className="text-green-400 font-medium">-$1,080.00</span>
                           </div>
                           <div className="pt-3 border-t border-white/10 flex justify-between">
                              <span className="text-sm font-bold text-white">Patient Responsibility</span>
                              <span className="text-lg font-bold text-[#8BE8E2]">$270.00</span>
                           </div>
                        </div>
                     </div>
                  </div>
               </div>
            </div>

            {/* Right Panel: Doctor Notes & Prescription */}
            <div className="w-full lg:w-[400px] flex flex-col gap-4">
               <div className="bg-[#161B24] border border-white/10 rounded-[2rem] p-6 flex flex-col flex-1 shadow-lg">
                  <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                     <FileText className="w-5 h-5 text-gray-400" /> Clinical Notes
                  </h3>
                  
                  <div className="flex flex-col gap-5 flex-1">
                     <div className="flex flex-col gap-2 flex-1">
                        <label className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Diagnosis & Observations</label>
                        <textarea 
                          value={notes}
                          onChange={(e) => setNotes(e.target.value)}
                          placeholder="Enter clinical observations..."
                          className="bg-black/20 border border-white/10 rounded-xl p-4 text-sm text-white focus:outline-none focus:border-[#8BE8E2] resize-none flex-1 placeholder:text-gray-600 custom-scrollbar"
                        />
                     </div>
                     
                     <div className="flex flex-col gap-2 flex-1">
                        <label className="text-xs font-semibold text-gray-400 uppercase tracking-wide flex items-center gap-2">
                           <FileSignature className="w-3.5 h-3.5" /> Prescription & Plan
                        </label>
                        <textarea 
                          value={prescription}
                          onChange={(e) => setPrescription(e.target.value)}
                          placeholder="Enter prescribed medications, resting plan..."
                          className="bg-black/20 border border-white/10 rounded-xl p-4 text-sm text-white focus:outline-none focus:border-[#8BE8E2] resize-none flex-1 placeholder:text-gray-600 custom-scrollbar"
                        />
                     </div>
                  </div>

                  <button 
                     onClick={handleComplete}
                     className="w-full mt-6 py-3.5 rounded-xl bg-[#8BE8E2] text-black font-bold text-sm hover:bg-[#38BFC3] transition-colors shadow-[0_0_15px_rgba(139,232,226,0.2)]"
                  >
                     Complete Appointment
                  </button>
               </div>
            </div>

          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center animate-in fade-in zoom-in duration-500">
             <div className="w-20 h-20 bg-[#8BE8E2]/10 rounded-full flex items-center justify-center mb-6">
               <CheckCircle2 className="w-10 h-10 text-[#8BE8E2]" />
             </div>
             <h2 className="text-2xl font-bold text-white mb-2">Appointment Completed</h2>
             <p className="text-gray-400 mb-8 max-w-md text-center">
               The clinical notes and prescriptions have been saved and shared with the patient's dashboard.
             </p>
             <button 
               onClick={() => {
                 setVisitCompleted(false);
                 setNotes('');
                 setPrescription('');
               }}
               className="px-8 py-3 rounded-full bg-white/10 text-white font-semibold text-sm hover:bg-white/20 transition-colors"
             >
               Call Next Patient
             </button>
          </div>
        )}

      </div>
    </div>
  );
}
