import React, { useState, useRef } from 'react';
import { User, Mic, Send, AlertTriangle, ShieldCheck, Activity, Clock, Stethoscope, Building2, CreditCard, FileText, Bed, HeartPulse, Droplets, Thermometer, Wind, CheckCircle2, Star, StopCircle } from 'lucide-react';
import { api } from '../api';

export function PatientDashboard() {
  const [transcript, setTranscript] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<boolean>(false);
  const [showStatus, setShowStatus] = useState(false);
  const [visitCompleted, setVisitCompleted] = useState(false);
  const [reviewStatus, setReviewStatus] = useState<'idle' | 'rating' | 'submitted'>('idle');
  const [ratings, setRatings] = useState({ triage: 0, ward: 0, hospital: 0, doctor: 0 });
  const [reviewText, setReviewText] = useState('');
  const [qnaAnswers, setQnaAnswers] = useState<Record<number, boolean>>({});

  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioChunks = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.current = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      audioChunks.current = [];

      mediaRecorder.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.current.push(event.data);
        }
      };

      mediaRecorder.current.onstop = async () => {
        const audioBlob = new Blob(audioChunks.current, { type: 'audio/webm' });
        
        // Stop all tracks to release microphone
        stream.getTracks().forEach(track => track.stop());

        setIsProcessing(true);
        try {
          const result = await api.processKioskAudio(audioBlob);
          if (result && result.transcript) {
            setTranscript(result.transcript);
          }
        } catch (e) {
          console.error("Failed to process audio", e);
        } finally {
          setIsProcessing(false);
        }
      };

      mediaRecorder.current.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Error accessing microphone", err);
      alert("Could not access microphone.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && isRecording) {
      mediaRecorder.current.stop();
      setIsRecording(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsProcessing(true);
    setTimeout(() => {
      setResult(true);
      setIsProcessing(false);
    }, 1500);
  };

  if (showStatus) {
    return (
      <div className="flex flex-1 overflow-hidden h-full">
        <div className="flex-1 flex flex-col p-8 md:p-12 overflow-y-auto custom-scrollbar relative max-w-5xl mx-auto w-full">
          <header className="flex items-center justify-between mb-10">
            <div className="flex items-center gap-3">
              <button onClick={() => setShowStatus(false)} className="flex items-center gap-2 bg-white text-black px-4 py-2.5 rounded-full text-sm font-semibold shadow-sm">
                <User className="w-[18px] h-[18px]" /> Back to Intake
              </button>
              {!visitCompleted && (
                <button 
                  onClick={() => setVisitCompleted(true)} 
                  className="flex items-center gap-2 border border-white/20 text-white hover:bg-white/10 px-4 py-2.5 rounded-full text-sm font-semibold transition-colors"
                >
                  <CheckCircle2 className="w-[18px] h-[18px]" /> Complete Visit (Demo)
                </button>
              )}
            </div>
          </header>

          <div className="mb-8">
            <h1 className="text-[3rem] leading-tight font-light tracking-tight mb-2">Welcome back, Wade</h1>
            <p className="text-gray-400 text-lg">Your triage data has been received. Here is your current status.</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            {/* Queue Status Hero */}
            <div className={`lg:col-span-2 rounded-[2rem] p-8 flex flex-col justify-between transition-colors duration-500 ${visitCompleted ? 'bg-emerald-500 text-white shadow-[0_10px_30px_rgba(16,185,129,0.2)]' : 'bg-[#D6FF38] text-black shadow-[0_10px_30px_rgba(214,255,56,0.15)]'}`}>
              <div>
                <div className="flex items-center gap-2 mb-4 font-semibold opacity-80 uppercase tracking-wider text-sm">
                   {visitCompleted ? <CheckCircle2 className="w-5 h-5" /> : <Clock className="w-5 h-5" />} 
                   {visitCompleted ? 'Discharge Status' : 'Current Queue Status'}
                </div>
                <h2 className="text-5xl font-light tracking-tight mb-2">
                  {visitCompleted ? 'You are discharged' : 'You are #3 in line'}
                </h2>
                <p className="text-lg font-medium opacity-80 mb-6">
                  {visitCompleted ? 'All medical records have been updated.' : 'Estimated wait time: 15 mins'}
                </p>
              </div>
              <div className="flex items-center gap-6 mt-8 pt-6 border-t border-black/10">
                 <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-black/10 rounded-full flex items-center justify-center">
                       <Building2 className="w-5 h-5" />
                    </div>
                    <div>
                       <p className="text-xs font-bold uppercase tracking-wider opacity-60">Hospital</p>
                       <p className="font-semibold">Central General</p>
                    </div>
                 </div>
                 <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-black/10 rounded-full flex items-center justify-center">
                       <Bed className="w-5 h-5" />
                    </div>
                    <div>
                       <p className="text-xs font-bold uppercase tracking-wider opacity-60">Ward</p>
                       <p className="font-semibold">Trauma ICU</p>
                    </div>
                 </div>
              </div>
            </div>

            {/* Doctor Profile */}
            <div className="bg-[#18191C] border border-[#2A2B30] rounded-[2rem] p-8 flex flex-col items-center justify-center text-center">
               <div className="w-24 h-24 rounded-full overflow-hidden mb-4 border-4 border-white/5 relative">
                  <img src="https://i.pravatar.cc/150?u=d1" alt="Doctor" className="w-full h-full object-cover" />
                  <div className="absolute bottom-0 right-0 w-6 h-6 bg-emerald-500 rounded-full border-2 border-[#18191C] flex items-center justify-center">
                     <CheckCircle2 className="w-3 h-3 text-white" />
                  </div>
               </div>
               <h3 className="text-xl font-semibold text-white">Dr. Sarah Hayes</h3>
               <p className="text-sm text-gray-400 font-medium mb-4">Trauma Surgery</p>
               <div className="bg-white/5 rounded-xl px-4 py-3 flex items-center justify-center gap-2 w-full mb-2">
                  <Stethoscope className="w-4 h-4 text-emerald-400" />
                  <span className="text-sm font-semibold text-emerald-400">Assigned Provider</span>
               </div>

               {visitCompleted && reviewStatus === 'idle' && (
                 <div className="mt-2 pt-6 border-t border-white/10 w-full flex flex-col items-center animate-in fade-in zoom-in duration-500">
                    <p className="text-sm text-gray-300 mb-4">How was your experience today?</p>
                    <button onClick={() => setReviewStatus('rating')} className="bg-white text-black px-6 py-2.5 rounded-full text-sm font-semibold hover:bg-gray-200 transition-colors w-full">
                        Leave a Review
                    </button>
                 </div>
               )}


               {visitCompleted && reviewStatus === 'submitted' && (
                 <div className="mt-2 pt-6 border-t border-white/10 w-full flex flex-col items-center animate-in zoom-in duration-500">
                    <div className="w-12 h-12 bg-emerald-500/20 rounded-full flex items-center justify-center mb-3">
                        <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                    </div>
                    <p className="text-base text-white font-semibold">Thank you!</p>
                    <p className="text-xs text-gray-400 mt-1">Your feedback helps us improve.</p>
                 </div>
               )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
             {/* Clinical Summary */}
             <div className="bg-[#18191C] border border-[#2A2B30] rounded-[2rem] p-8">
                <h3 className="text-white font-semibold text-lg mb-6 flex items-center gap-2">
                   <Activity className="w-5 h-5 text-gray-500" /> Your Clinical Data
                </h3>
                
                <div className="mb-6">
                   <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-2">Chief Complaint</span>
                   <div className="bg-white/5 border border-white/5 rounded-xl p-4">
                      <p className="text-sm text-gray-300 leading-relaxed">Severe abdominal pain, nausea.</p>
                   </div>
                </div>

                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-2">Initial Vitals</span>
                <div className="grid grid-cols-2 gap-3">
                   <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col justify-between">
                     <div className="flex items-center gap-2 text-gray-500 mb-2">
                       <HeartPulse className="w-3.5 h-3.5" />
                       <span className="text-[10px] font-bold uppercase tracking-wider">HR</span>
                     </div>
                     <span className="text-xl font-bold leading-none text-white">95</span>
                   </div>
                   <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col justify-between">
                     <div className="flex items-center gap-2 text-gray-500 mb-2">
                       <Droplets className="w-3.5 h-3.5" />
                       <span className="text-[10px] font-bold uppercase tracking-wider">SpO₂</span>
                     </div>
                     <span className="text-xl font-bold leading-none text-white">98%</span>
                   </div>
                   <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col justify-between">
                     <div className="flex items-center gap-2 text-gray-500 mb-2">
                       <Activity className="w-3.5 h-3.5" />
                       <span className="text-[10px] font-bold uppercase tracking-wider">BP</span>
                     </div>
                     <span className="text-xl font-bold leading-none text-white">120/80</span>
                   </div>
                   <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col justify-between">
                     <div className="flex items-center gap-2 text-gray-500 mb-2">
                       <Thermometer className="w-3.5 h-3.5" />
                       <span className="text-[10px] font-bold uppercase tracking-wider">Temp</span>
                     </div>
                     <span className="text-xl font-bold leading-none text-white">101.2°</span>
                   </div>
                </div>
             </div>

             {/* Admin / Billing */}
             <div className="bg-[#18191C] border border-[#2A2B30] rounded-[2rem] p-8">
                <h3 className="text-white font-semibold text-lg mb-6 flex items-center gap-2">
                   <FileText className="w-5 h-5 text-gray-500" /> Administrative Info
                </h3>
                
                <div className="space-y-4">
                   <div className="bg-white/5 border border-white/5 rounded-xl p-4 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                         <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center shrink-0">
                            <ShieldCheck className="w-4 h-4 text-blue-400" />
                         </div>
                         <div>
                            <h4 className="text-sm font-semibold text-white">Aetna PPO</h4>
                            <p className="text-[11px] text-gray-500 mt-0.5">Primary Insurance</p>
                         </div>
                      </div>
                      <span className="text-xs font-bold text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded">Verified</span>
                   </div>

                   <div className="bg-white/5 border border-white/5 rounded-xl p-4 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                         <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center shrink-0">
                            <CreditCard className="w-4 h-4 text-amber-400" />
                         </div>
                         <div>
                            <h4 className="text-sm font-semibold text-white">Copay / Billing</h4>
                            <p className="text-[11px] text-gray-500 mt-0.5">$50.00 Expected</p>
                         </div>
                      </div>
                      <span className="text-xs font-bold text-amber-400 bg-amber-400/10 px-2 py-1 rounded">Pending</span>
                   </div>

                   <div className="bg-white/5 border border-white/5 rounded-xl p-4 flex items-center justify-between mt-8">
                      <div>
                         <h4 className="text-sm font-semibold text-white mb-1">Treatment Progress</h4>
                         <p className="text-[11px] text-gray-500">{visitCompleted ? 'Treatment complete. Discharged.' : 'Currently in triage phase.'}</p>
                      </div>
                      <span className="text-lg font-bold text-white">{visitCompleted ? '100%' : '85%'}</span>
                   </div>
                   <div className="w-full bg-white/10 rounded-full h-1.5 overflow-hidden">
                      <div className={`h-full rounded-full transition-all duration-1000 ${visitCompleted ? 'bg-emerald-500' : 'bg-[#D6FF38]'}`} style={{ width: visitCompleted ? '100%' : '85%' }}></div>
                   </div>
                </div>
             </div>
          </div>

          {visitCompleted && (
            <div className="bg-[#1C1D21] border border-white/10 rounded-[2rem] p-8 mb-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
               <h3 className="text-white font-semibold text-lg mb-6 flex items-center gap-2">
                  <Stethoscope className="w-5 h-5 text-[#D6FF38]" /> Doctor's Instructions & Prescriptions
               </h3>
               
               <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                 <div>
                   <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-2">Clinical Observations</span>
                   <div className="bg-black/20 border border-white/5 rounded-xl p-5 h-[120px] overflow-y-auto custom-scrollbar">
                     <p className="text-sm text-gray-300 leading-relaxed">
                       Patient presented with severe chest pain. ECG shows early signs of ischemia. Administered aspirin and oxygen. Monitored for 2 hours, symptoms subsided.
                     </p>
                   </div>
                 </div>
                 
                 <div>
                   <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-2">Prescription & Follow-up Plan</span>
                   <div className="bg-black/20 border border-white/5 rounded-xl p-5 h-[120px] overflow-y-auto custom-scrollbar">
                     <p className="text-sm text-gray-300 leading-relaxed">
                       - Nitroglycerin 0.4mg PRN for chest pain<br/>
                       - Follow up with cardiologist within 48 hours<br/>
                       - Strict bed rest for next 24 hours
                     </p>
                   </div>
                 </div>
               </div>
            </div>
          )}
        </div>

        {visitCompleted && reviewStatus === 'rating' && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-300">
            <div className="bg-[#18191C] border border-[#2A2B30] rounded-[2rem] p-8 w-full max-w-md shadow-2xl animate-in zoom-in-95 duration-300">
               <h3 className="text-2xl font-semibold text-white mb-6 text-center">Rate your experience</h3>
               
               <div className="space-y-4 mb-6">
                 {['triage', 'ward', 'hospital', 'doctor'].map(cat => (
                     <div key={cat} className="flex items-center justify-between">
                         <span className="text-sm text-gray-400 capitalize font-medium">{cat}</span>
                         <div className="flex gap-1.5">
                             {[1,2,3,4,5].map(star => (
                                 <Star 
                                   key={star} 
                                   className={`w-6 h-6 cursor-pointer transition-colors ${ratings[cat as keyof typeof ratings] >= star ? 'fill-[#D6FF38] text-[#D6FF38]' : 'text-gray-600 hover:text-gray-400'}`} 
                                   onClick={() => setRatings({...ratings, [cat]: star})} 
                                 />
                             ))}
                         </div>
                     </div>
                 ))}
               </div>

               <div className="mb-8">
                 <label className="text-sm text-gray-400 font-medium block mb-3">Additional Comments</label>
                 <textarea 
                   value={reviewText}
                   onChange={(e) => setReviewText(e.target.value)}
                   placeholder="Tell us about your visit..."
                   className="w-full bg-black/20 border border-white/10 rounded-xl p-4 text-sm text-white focus:outline-none focus:border-[#D6FF38]/50 min-h-[120px] resize-none"
                 />
               </div>

               <div className="flex gap-3">
                  <button 
                    onClick={() => setReviewStatus('idle')}
                    className="flex-1 px-4 py-3 rounded-full text-sm font-semibold border border-white/10 text-white hover:bg-white/5 transition-colors"
                  >
                     Cancel
                  </button>
                  <button 
                    onClick={() => setReviewStatus('submitted')} 
                    disabled={Object.values(ratings).some(v => v === 0)}
                    className="flex-1 bg-[#D6FF38] text-black px-4 py-3 rounded-full text-sm font-bold hover:bg-[#c2e633] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                      Submit Review
                  </button>
               </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      <div className="flex-1 flex flex-col p-8 md:p-12 overflow-y-auto custom-scrollbar relative max-w-5xl mx-auto">
        <header className="flex items-center justify-between mb-12">
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 bg-white text-black px-4 py-2.5 rounded-full text-sm font-semibold shadow-sm">
              <User className="w-[18px] h-[18px]" /> Patient Intake
            </button>
          </div>
        </header>

        <div className="mb-10">
          <h1 className="text-[3rem] leading-tight font-light tracking-tight mb-4">What brings you in today?</h1>
          <p className="text-gray-400 text-lg max-w-2xl">Please describe your symptoms, when they started, and any pain you are experiencing. Our AI assistant will pre-process your information for the triage nurse.</p>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          <div className="flex flex-col gap-6 xl:col-span-2">
            
            {/* Expanded Patient Form */}
            <form onSubmit={handleSubmit} className="flex flex-col gap-6">
               
               {/* Basic Info */}
               <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                 <div className="bg-[#18191C] border border-[#2A2B30] rounded-2xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                    <input type="text" placeholder="Full Name" className="w-full bg-transparent text-white px-5 py-3 outline-none placeholder:text-gray-600 text-sm" />
                 </div>
                 <div className="flex gap-4">
                    <div className="flex-1 bg-[#18191C] border border-[#2A2B30] rounded-2xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                       <input type="text" placeholder="Age" className="w-full bg-transparent text-white px-5 py-3 outline-none placeholder:text-gray-600 text-sm" />
                    </div>
                    <div className="flex-1 bg-[#18191C] border border-[#2A2B30] rounded-2xl p-1 focus-within:border-[#D6FF38]/50 transition-colors px-4 py-3">
                       <select className="w-full bg-transparent text-white outline-none appearance-none text-sm cursor-pointer">
                          <option value="" disabled selected className="text-gray-600">Age Group</option>
                          <option value="adult" className="bg-[#1C1D21]">Adult</option>
                          <option value="pediatric" className="bg-[#1C1D21]">Pediatric</option>
                          <option value="geriatric" className="bg-[#1C1D21]">Geriatric</option>
                       </select>
                    </div>
                 </div>
               </div>

               {/* Clinical Text */}
               <div className="bg-[#18191C] border border-[#2A2B30] rounded-2xl p-1 focus-within:border-[#D6FF38]/50 transition-colors relative">
                  <textarea 
                    value={transcript}
                    onChange={(e) => setTranscript(e.target.value)}
                    placeholder="Chief Complaint (What is the main reason for your visit?)"
                    className="w-full h-24 bg-transparent text-white p-5 resize-none outline-none placeholder:text-gray-600 text-sm custom-scrollbar"
                  />
                  <div className="absolute right-4 bottom-4">
                    {isRecording ? (
                      <button 
                        type="button"
                        onClick={stopRecording}
                        className="bg-red-500 hover:bg-red-600 text-white p-2.5 rounded-full shadow-lg transition-colors animate-pulse flex items-center justify-center"
                      >
                        <StopCircle className="w-5 h-5" />
                      </button>
                    ) : (
                      <button 
                        type="button"
                        onClick={startRecording}
                        className="bg-[#D6FF38] hover:bg-[#bceb15] text-black p-2.5 rounded-full shadow-[0_0_15px_rgba(214,255,56,0.2)] transition-colors flex items-center justify-center"
                      >
                        <Mic className="w-5 h-5" />
                      </button>
                    )}
                  </div>
               </div>
               
               <div className="bg-[#18191C] border border-[#2A2B30] rounded-2xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                  <textarea 
                    placeholder="Presenting Details (When did it start? How severe is it?)"
                    className="w-full h-24 bg-transparent text-white p-5 resize-none outline-none placeholder:text-gray-600 text-sm custom-scrollbar"
                  />
               </div>

               {/* Vitals Grid */}
               <div className="bg-[#1C1D21] border border-[#2A2B30] rounded-2xl p-6">
                 <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-4">Patient Vitals Entry</span>
                 <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                   <div className="bg-[#18191C] border border-[#2A2B30] rounded-xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                      <input type="text" placeholder="HR (bpm)" className="w-full bg-transparent text-white px-3 py-2 outline-none placeholder:text-gray-600 text-sm text-center" />
                   </div>
                   <div className="bg-[#18191C] border border-[#2A2B30] rounded-xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                      <input type="text" placeholder="RR" className="w-full bg-transparent text-white px-3 py-2 outline-none placeholder:text-gray-600 text-sm text-center" />
                   </div>
                   <div className="bg-[#18191C] border border-[#2A2B30] rounded-xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                      <input type="text" placeholder="SpO₂ (%)" className="w-full bg-transparent text-white px-3 py-2 outline-none placeholder:text-gray-600 text-sm text-center" />
                   </div>
                   <div className="bg-[#18191C] border border-[#2A2B30] rounded-xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                      <input type="text" placeholder="BP (mmHg)" className="w-full bg-transparent text-white px-3 py-2 outline-none placeholder:text-gray-600 text-sm text-center" />
                   </div>
                   <div className="bg-[#18191C] border border-[#2A2B30] rounded-xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                      <input type="text" placeholder="Temp (°F)" className="w-full bg-transparent text-white px-3 py-2 outline-none placeholder:text-gray-600 text-sm text-center" />
                   </div>
                 </div>
               </div>

               {/* History & Insurance */}
               <div className="bg-[#18191C] border border-[#2A2B30] rounded-2xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                  <textarea 
                    placeholder="Relevant Medical History (Past surgeries, chronic conditions)"
                    className="w-full h-20 bg-transparent text-white p-5 resize-none outline-none placeholder:text-gray-600 text-sm custom-scrollbar"
                  />
               </div>

               <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                 <div className="bg-[#18191C] border border-[#2A2B30] rounded-2xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                    <input type="text" placeholder="Insurance Provider" className="w-full bg-transparent text-white px-5 py-3 outline-none placeholder:text-gray-600 text-sm" />
                 </div>
                 <div className="bg-[#18191C] border border-[#2A2B30] rounded-2xl p-1 focus-within:border-[#D6FF38]/50 transition-colors">
                    <input type="text" placeholder="Insurance Plan Name" className="w-full bg-transparent text-white px-5 py-3 outline-none placeholder:text-gray-600 text-sm" />
                 </div>
               </div>

               {/* Actions */}
               <div className="flex justify-end gap-3 mt-2">
                 <button type="button" className="px-6 py-3 rounded-full bg-white/5 text-white font-medium hover:bg-white/10 transition-colors text-sm">
                    Clear Form
                 </button>
                 <button 
                    type="submit"
                    disabled={isProcessing}
                    className="px-8 py-3 rounded-full bg-[#D6FF38] text-black font-bold hover:bg-[#bceb15] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm shadow-[0_0_15px_rgba(214,255,56,0.3)]"
                 >
                    <Send className="w-4 h-4" /> Run AI Triage Assessment
                 </button>
               </div>
            </form>
          </div>

          <div className="flex flex-col gap-6 xl:col-span-1">
             {isProcessing ? (
               <div className="bg-[#1C1D21] border border-white/5 rounded-[2rem] p-8 flex flex-col items-center justify-center h-64 animate-pulse">
                 <div className="w-12 h-12 rounded-full border-4 border-[#D6FF38]/30 border-t-[#D6FF38] animate-spin mb-4" />
                 <p className="text-gray-400">Processing clinical data...</p>
               </div>
             ) : result ? (
               <div className="bg-[#1C1D21] border border-white/10 rounded-[2rem] p-8 flex flex-col h-full shadow-[0_10px_30px_rgba(0,0,0,0.2)] overflow-y-auto custom-scrollbar">
                 <h3 className="text-xl font-medium mb-4 flex items-center gap-2">
                   <Activity className="w-5 h-5 text-[#D6FF38]" /> AI Clinical Assessment
                 </h3>
                 <p className="text-sm text-gray-400 mb-6">Please answer the following questions to help us assess your condition.</p>
                 
                 <div className="space-y-4 flex-1">
                   {[
                     "Are you currently experiencing shortness of breath?",
                     "Is the pain radiating to your left arm or jaw?",
                     "Have you experienced any dizziness or fainting today?"
                   ].map((q, i) => (
                      <div key={i} className="bg-white/5 border border-white/10 rounded-xl p-5">
                         <p className="text-sm text-white font-medium mb-4">{q}</p>
                         <div className="flex gap-3">
                           <button 
                             onClick={() => setQnaAnswers({...qnaAnswers, [i]: true})}
                             className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-colors ${qnaAnswers[i] === true ? 'bg-[#D6FF38] text-black' : 'bg-white/5 text-white hover:bg-white/10 border border-white/10'}`}
                           >
                             Yes
                           </button>
                           <button 
                             onClick={() => setQnaAnswers({...qnaAnswers, [i]: false})}
                             className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-colors ${qnaAnswers[i] === false ? 'bg-[#D6FF38] text-black' : 'bg-white/5 text-white hover:bg-white/10 border border-white/10'}`}
                           >
                             No
                           </button>
                         </div>
                      </div>
                   ))}
                 </div>
                 
                 {Object.keys(qnaAnswers).length === 3 && (
                   <div className="mt-8 pt-6 border-t border-white/10 animate-in fade-in slide-in-from-bottom-4 duration-500 flex justify-end">
                     <button 
                       onClick={() => setShowStatus(true)}
                       className="px-8 py-3 rounded-full bg-[#D6FF38] text-black font-bold text-sm hover:bg-[#bceb15] transition-colors shadow-[0_0_15px_rgba(214,255,56,0.3)] flex items-center justify-center gap-2"
                     >
                       <CheckCircle2 className="w-4 h-4" /> Submit
                     </button>
                   </div>
                 )}
               </div>
             ) : (
               <div className="bg-transparent border border-dashed border-white/10 rounded-[2rem] p-8 flex flex-col items-center justify-center h-64 text-center">
                 <Activity className="w-8 h-8 text-gray-600 mb-4" />
                 <p className="text-gray-500 text-sm">Enter your symptoms on the left to receive preliminary AI triage assessment.</p>
               </div>
             )}
          </div>
        </div>
      </div>
    </div>
  );
}
