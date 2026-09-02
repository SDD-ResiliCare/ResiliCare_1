import React, { useEffect, useState } from 'react';
import { 
  ShieldAlert, Download, Server, Zap, Users, Activity, Plus, Search, 
  Building2, Bed, Stethoscope, CheckCircle2, AlertCircle, Clock, FileText, 
  TrendingUp, ActivitySquare, Settings, Star
} from 'lucide-react';
import { api } from '../api';

export function AdminDashboard() {
  const [surgeActive, setSurgeActive] = useState(false);
  const [doctorWorkloads, setDoctorWorkloads] = useState<any[]>([]);

  useEffect(() => {
    api.getDoctorWorkloads().then(setDoctorWorkloads);
  }, []);

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      <div className="flex-1 flex flex-col p-8 overflow-y-auto custom-scrollbar relative">
        {/* Header */}
        <header className="flex items-center justify-between mb-12">
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 bg-white text-black px-4 py-2.5 rounded-full text-sm font-semibold shadow-sm">
              <ShieldAlert className="w-[18px] h-[18px]" /> Admin Console
            </button>
            <button className="flex items-center gap-2 border border-white/10 text-white hover:bg-white/5 px-4 py-2.5 rounded-full text-sm font-medium transition-colors">
              <Download className="w-[18px] h-[18px]" /> Export Logs
            </button>
            <button className="flex items-center gap-2 border border-white/10 text-white hover:bg-white/5 px-4 py-2.5 rounded-full text-sm font-medium transition-colors">
              <Star className="w-[18px] h-[18px]" /> Reviews
            </button>
          </div>
          <div className="flex items-center gap-4">
             <div className="px-4 py-2 rounded-full bg-[#D6FF38]/10 border border-[#D6FF38]/20 text-[#D6FF38] text-sm font-medium flex items-center gap-2">
                <Server className="w-4 h-4" /> System Online
             </div>
          </div>
        </header>

        {/* Top Operations & System Controls */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-10">
          <div className="col-span-1 lg:col-span-2 bg-[#18191C] border border-[#2A2B30] rounded-[2rem] p-8">
             <div className="flex items-center justify-between mb-6">
                <h3 className="text-gray-300 font-semibold text-lg flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-gray-500" /> System Management
                </h3>
                <button className="text-sm font-medium text-gray-400 hover:text-white transition-colors">View All</button>
             </div>
             
             <div className="grid grid-cols-2 gap-4">
                <button className="flex items-center gap-3 bg-white/5 hover:bg-white/10 border border-white/5 rounded-xl p-4 transition-colors text-left">
                   <div className="w-10 h-10 rounded-full bg-[#D6FF38]/10 flex items-center justify-center shrink-0">
                      <Plus className="w-5 h-5 text-[#D6FF38]" />
                   </div>
                   <div>
                      <h4 className="text-sm font-semibold text-white">Add Hospital</h4>
                      <p className="text-[11px] text-gray-500 mt-0.5">Register new facility</p>
                   </div>
                </button>
                <button className="flex items-center gap-3 bg-white/5 hover:bg-white/10 border border-white/5 rounded-xl p-4 transition-colors text-left">
                   <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center shrink-0">
                      <Stethoscope className="w-5 h-5 text-white" />
                   </div>
                   <div>
                      <h4 className="text-sm font-semibold text-white">Add Clinician</h4>
                      <p className="text-[11px] text-gray-500 mt-0.5">Link ID to nurse</p>
                   </div>
                </button>
                <button className="flex items-center gap-3 bg-white/5 hover:bg-white/10 border border-white/5 rounded-xl p-4 transition-colors text-left col-span-2">
                   <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center shrink-0">
                      <Settings className="w-5 h-5 text-white" />
                   </div>
                   <div>
                      <h4 className="text-sm font-semibold text-white">Modify Wards & Beds</h4>
                      <p className="text-[11px] text-gray-500 mt-0.5">Adjust bed counts and ward distributions across hospitals</p>
                   </div>
                </button>
             </div>
          </div>

          <div className="bg-[#18191C] border border-[#2A2B30] rounded-[2rem] p-8 flex flex-col justify-center text-center">
             <h3 className="text-gray-400 font-medium mb-2">Network Occupancy</h3>
             <span className="text-5xl font-light mb-2">78<span className="text-2xl text-gray-500">%</span></span>
             <p className="text-sm text-gray-500">142 of 182 beds filled</p>
             <div className="w-full bg-white/10 rounded-full h-1.5 mt-6 overflow-hidden">
                <div className="bg-[#D6FF38] h-full rounded-full" style={{ width: '78%' }}></div>
             </div>
          </div>

          <div className={`rounded-[2rem] p-8 relative overflow-hidden flex flex-col justify-between transition-colors duration-500 ${surgeActive ? 'bg-red-500 text-white' : 'bg-[#D6FF38] text-black shadow-[0_10px_30px_rgba(214,255,56,0.15)]'}`}>
             <div className="relative z-10">
               <h3 className="font-semibold mb-2">{surgeActive ? 'Surge Protocol Active' : 'Normal Operations'}</h3>
               <p className="text-sm opacity-80 mb-6 font-medium">
                 {surgeActive ? 'Emergency high-acuity routing enabled. All elective admissions paused.' : 'System operating under standard baselines. Quiet mode active.'}
               </p>
               <button 
                 onClick={() => setSurgeActive(!surgeActive)}
                 className={`px-6 py-3 rounded-full text-sm font-bold flex items-center gap-2 transition-colors w-max ${surgeActive ? 'bg-white text-red-600 hover:bg-gray-100' : 'bg-black text-white hover:bg-gray-900'}`}
               >
                 {surgeActive ? <CheckCircle2 className="w-4 h-4" /> : <Zap className="w-4 h-4" />}
                 {surgeActive ? 'Reset to Quiet' : 'Declare Surge'}
               </button>
             </div>
             <Zap className={`absolute -bottom-10 -right-10 w-48 h-48 ${surgeActive ? 'text-white/10' : 'text-black/5'}`} />
          </div>
        </div>

        {/* Grid: Ward & Doctor Overview */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
           {/* Ward Overview */}
           <div className="bg-[#18191C] border border-[#2A2B30] rounded-[2rem] p-8">
              <div className="flex items-center justify-between mb-8">
                <h3 className="text-white font-semibold text-lg">Ward Overview</h3>
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Live Dist</span>
              </div>
              
              <div className="space-y-4">
                 {[
                   { name: 'Trauma ICU', hospital: 'Central General', beds: '28/30', pct: 93, colorClass: 'text-red-500', doc: 'Dr. Hayes (Assigned)' },
                   { name: 'Cardiology', hospital: 'Central General', beds: '14/20', pct: 70, colorClass: 'text-[#D6FF38]', doc: 'Dr. Kim (Free)' },
                   { name: 'General Med', hospital: 'Westside Clinic', beds: '45/50', pct: 90, colorClass: 'text-white', doc: 'Dr. Rivera (Assigned)' },
                   { name: 'Pediatrics', hospital: 'Westside Clinic', beds: '8/15', pct: 53, colorClass: 'text-gray-400', doc: 'Dr. Patel (Free)' },
                 ].map((ward, i) => (
                   <div key={i} className="flex items-center justify-between bg-white/5 border border-white/5 rounded-xl p-4">
                      <div className="flex-1">
                         <div className="flex items-center gap-2 mb-1">
                            <h4 className="text-sm font-semibold text-white">{ward.name}</h4>
                            <span className="text-[10px] text-gray-500 uppercase tracking-wider px-2 py-0.5 bg-black/40 rounded">{ward.hospital}</span>
                         </div>
                         <div className="flex items-center gap-3 text-xs text-gray-400 mt-2">
                            <span className="flex items-center gap-1"><Bed className="w-3.5 h-3.5" /> {ward.beds} beds ({ward.pct}%)</span>
                            <span className="w-1 h-1 rounded-full bg-gray-600"></span>
                            <span className="flex items-center gap-1"><Stethoscope className="w-3.5 h-3.5" /> {ward.doc}</span>
                         </div>
                      </div>
                      <div className="w-16 h-16 shrink-0 relative flex items-center justify-center">
                         <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                            <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="3" />
                            <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" className={`stroke-current ${ward.colorClass}`} strokeWidth="3" strokeDasharray={`${ward.pct}, 100`} />
                         </svg>
                         <span className="absolute text-[10px] font-bold">{ward.pct}%</span>
                      </div>
                   </div>
                 ))}
              </div>
           </div>

           {/* Doctor Overview */}
           <div className="bg-[#18191C] border border-[#2A2B30] rounded-[2rem] p-8">
              <div className="flex items-center justify-between mb-8">
                <h3 className="text-white font-semibold text-lg">Doctor Status & Queues</h3>
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Live Roster</span>
              </div>
              
              <div className="space-y-4">
                 {(doctorWorkloads.length > 0 ? doctorWorkloads.map((workload: any) => ({
                   name: `Dr. ${workload.doctor.first_name} ${workload.doctor.last_name || ''}`.trim(),
                   spec: 'Clinical staff',
                   status: workload.availability === 'busy' ? 'Busy' : 'Free',
                   ward: workload.current_patient?.ward?.name || workload.waiting_patients?.[0]?.ward?.name || 'Ward assignment',
                   queue: workload.waiting_count ? `${workload.waiting_count} patients waiting` : 'No queue',
                   color: workload.availability === 'busy' ? 'text-red-400' : 'text-[#D6FF38]',
                   bg: workload.availability === 'busy' ? 'bg-red-500/10' : 'bg-[#D6FF38]/10',
                   img: `https://i.pravatar.cc/150?u=${workload.doctor.id}`,
                 })) : [
                   { name: 'Dr. Sarah Hayes', spec: 'Trauma Surgery', status: 'Assigned', ward: 'Trauma ICU', queue: '3 patients waiting', color: 'text-red-400', bg: 'bg-red-500/10', img: 'https://i.pravatar.cc/150?u=d1' },
                   { name: 'Dr. Marcus Kim', spec: 'Cardiology', status: 'Free', ward: 'Cardiology', queue: 'No queue', color: 'text-[#D6FF38]', bg: 'bg-[#D6FF38]/10', img: 'https://i.pravatar.cc/150?u=d2' },
                   { name: 'Dr. Elena Rivera', spec: 'Internal Medicine', status: 'Assigned', ward: 'General Med', queue: '1 patient assigned', color: 'text-white', bg: 'bg-white/10', img: 'https://i.pravatar.cc/150?u=d3' },
                   { name: 'Dr. Anil Patel', spec: 'Pediatrics', status: 'Free', ward: 'Pediatrics', queue: 'No queue', color: 'text-gray-400', bg: 'bg-white/5', img: 'https://i.pravatar.cc/150?u=d4' },
                 ]).map((doc, i) => (
                   <div key={i} className="flex items-center gap-4 bg-white/5 border border-white/5 rounded-xl p-4">
                      <img src={doc.img} alt={doc.name} className="w-12 h-12 rounded-full object-cover" />
                      <div className="flex-1">
                         <h4 className="text-sm font-semibold text-white">{doc.name}</h4>
                         <p className="text-[11px] text-gray-400 mt-0.5">{doc.spec} • {doc.ward}</p>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                         <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded ${doc.bg} ${doc.color}`}>
                           {doc.status}
                         </span>
                         <span className="text-[11px] text-gray-500 flex items-center gap-1"><Users className="w-3 h-3" /> {doc.queue}</span>
                      </div>
                   </div>
                 ))}
              </div>
           </div>
        </div>

        {/* Patient Directory */}
        <div className="bg-[#18191C] border border-[#2A2B30] rounded-[2rem] p-8 mb-8">
           <div className="flex items-center justify-between mb-8">
             <div className="flex items-center gap-3">
                <h3 className="text-white font-semibold text-lg">Patient Directory</h3>
                <span className="bg-white/10 text-gray-300 text-xs font-semibold px-2.5 py-1 rounded-full">142 Active</span>
             </div>
             <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <input type="text" placeholder="Search patients..." className="bg-black/20 border border-white/10 rounded-full pl-9 pr-4 py-2 text-sm text-white focus:outline-none focus:border-white/20 w-64" />
             </div>
           </div>
           
           <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                 <thead>
                    <tr className="border-b border-white/10">
                       <th className="pb-4 px-4 text-[10px] font-bold text-gray-500 uppercase tracking-wider">Patient</th>
                       <th className="pb-4 px-4 text-[10px] font-bold text-gray-500 uppercase tracking-wider">Location</th>
                       <th className="pb-4 px-4 text-[10px] font-bold text-gray-500 uppercase tracking-wider">Assigned Doctor</th>
                       <th className="pb-4 px-4 text-[10px] font-bold text-gray-500 uppercase tracking-wider">Progress</th>
                       <th className="pb-4 px-4 text-[10px] font-bold text-gray-500 uppercase tracking-wider">Billing / Ins.</th>
                       <th className="pb-4 px-4 text-[10px] font-bold text-gray-500 uppercase tracking-wider text-right">Actions</th>
                    </tr>
                 </thead>
                 <tbody className="text-sm">
                    {[
                      { name: 'Wade Warren', id: '#P-4921', loc: 'Central General', ward: 'Trauma ICU', doc: 'Dr. Hayes', prog: 85, bill: 'Pending', ins: 'BlueCross', status: 'critical' },
                      { name: 'Robert Fox', id: '#P-4922', loc: 'Westside Clinic', ward: 'General Med', doc: 'Dr. Rivera', prog: 40, bill: 'Cleared', ins: 'Medicare', status: 'stable' },
                      { name: 'Kristin Watson', id: '#P-4923', loc: 'Central General', ward: 'Cardiology', doc: 'Unassigned', prog: 15, bill: 'Processing', ins: 'Aetna', status: 'stable' },
                      { name: 'Jenny Wilson', id: '#P-4924', loc: 'Westside Clinic', ward: 'Pediatrics', doc: 'Dr. Patel', prog: 95, bill: 'Cleared', ins: 'Cigna', status: 'discharge' },
                    ].map((p, i) => (
                       <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors group">
                          <td className="py-4 px-4">
                             <div className="font-semibold text-white">{p.name}</div>
                             <div className="text-[11px] text-gray-500 font-mono mt-0.5">{p.id}</div>
                          </td>
                          <td className="py-4 px-4">
                             <div className="text-gray-300">{p.loc}</div>
                             <div className="text-[11px] text-gray-500 mt-0.5">{p.ward}</div>
                          </td>
                          <td className="py-4 px-4">
                             <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium ${p.doc === 'Unassigned' ? 'bg-red-500/10 text-red-400' : 'bg-white/5 text-gray-300'}`}>
                                {p.doc !== 'Unassigned' && <Stethoscope className="w-3 h-3 opacity-70" />}
                                {p.doc}
                             </span>
                          </td>
                          <td className="py-4 px-4">
                             <div className="flex items-center gap-3">
                                <div className="w-24 bg-white/10 rounded-full h-1.5 overflow-hidden">
                                   <div className={`h-full rounded-full ${p.status === 'critical' ? 'bg-red-500' : p.status === 'discharge' ? 'bg-[#D6FF38]' : 'bg-white'}`} style={{ width: `${p.prog}%` }}></div>
                                </div>
                                <span className="text-[11px] font-bold text-gray-400">{p.prog}%</span>
                             </div>
                          </td>
                          <td className="py-4 px-4">
                             <div className="text-gray-300 text-xs flex items-center gap-1.5"><FileText className="w-3.5 h-3.5 text-gray-500" /> {p.ins}</div>
                             <div className={`text-[10px] font-bold uppercase tracking-wider mt-1 ${p.bill === 'Cleared' ? 'text-[#D6FF38]' : p.bill === 'Pending' ? 'text-gray-400' : 'text-white'}`}>
                                {p.bill}
                             </div>
                          </td>
                          <td className="py-4 px-4 text-right">
                             <button className="text-[11px] font-semibold text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded transition-colors opacity-0 group-hover:opacity-100">
                               View Full Data
                             </button>
                          </td>
                       </tr>
                    ))}
                 </tbody>
              </table>
           </div>
        </div>

      </div>
    </div>
  );
}
