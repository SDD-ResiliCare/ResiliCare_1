import axios from 'axios';
import { Patient, QueueSnapshot, HospitalProfile, SurgeEvidence } from './types';

// Create an Axios instance pointing to the backend
const apiClient = axios.create({
  baseURL: (import.meta as any).env.VITE_API_URL || 'http://127.0.0.1:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && (error.response.status === 401 || error.response.status === 403)) {
      if (error.response.data?.detail === "Not authenticated" || error.response.data?.detail === "invalid or expired access token") {
        localStorage.removeItem('authToken');
        window.location.reload();
      }
    }
    return Promise.reject(error);
  }
);

// Mock Data
// Includes encounter_id and assessment_id to match backend expectations for certain actions
let mockQueue: Patient[] = [
  {
    id: 'p1', // maps to patient_id conceptually
    encounter_id: 'enc-1',
    assessment_id: 'assess-1',
    name: 'Wade Warren',
    age: 36,
    avatar: 'https://i.pravatar.cc/150?u=a042581f4e29026704d',
    complaint: 'Chest pain, shortness of breath',
    status: 'waiting',
    timeInQueue: '15m',
    aiSuggestion: {
      esi: 2,
      redFlags: ['Cardiac', 'Respiratory'],
      differential: ['Myocardial Infarction', 'Pulmonary Embolism'],
      needsConfirmation: true,
    },
    vitals: { heart_rate_bpm: 110, systolic_bp_mmhg: 140, diastolic_bp_mmhg: 90, spo2_percent: 92 },
  },
  {
    id: 'p2',
    encounter_id: 'enc-2',
    assessment_id: 'assess-2',
    name: 'Robert Fox',
    age: 34,
    avatar: 'https://i.pravatar.cc/150?u=a042581f4e29026704e',
    complaint: 'Severe abdominal pain',
    status: 'waiting',
    timeInQueue: '45m',
    aiSuggestion: {
      esi: 3,
      redFlags: ['Abdominal'],
      differential: ['Appendicitis', 'Kidney Stones'],
      needsConfirmation: true,
    },
    vitals: { heart_rate_bpm: 95, systolic_bp_mmhg: 120, diastolic_bp_mmhg: 80, spo2_percent: 98 },
  },
  {
    id: 'p3',
    encounter_id: 'enc-3',
    assessment_id: 'assess-3',
    name: 'Kristin Watson',
    age: 42,
    avatar: 'https://i.pravatar.cc/150?u=a042581f4e29026704f',
    complaint: 'Laceration on right arm',
    status: 'waiting',
    timeInQueue: '2h',
    aiSuggestion: {
      esi: 4,
      redFlags: [],
      differential: ['Laceration'],
      needsConfirmation: false,
    },
    vitals: { heart_rate_bpm: 80, systolic_bp_mmhg: 110, diastolic_bp_mmhg: 70, spo2_percent: 99 },
  },
];

let activeProfileId = 'prof_1';
const hospitalProfiles: HospitalProfile[] = [
  { id: 'prof_1', name: 'Level 1 Trauma Center', capabilities: ['Trauma', 'Surgery', 'ICU'], active: true },
  { id: 'prof_2', name: 'Standard ER', capabilities: ['General', 'Basic Labs'], active: false },
  { id: 'prof_3', name: 'Urgent Care Clinic', capabilities: ['Minor Injuries', 'Basic Meds'], active: false },
];

export const api = {
  // --- Nurse Interface ---
  getQueue: async (): Promise<QueueSnapshot> => {
    try {
      // Because we lack proper authentication tokens in the frontend for now,
      // this request might fail with a 403. We'll gracefully fallback to mock data.
      const response = await apiClient.get('/api/v1/queues/current/entries');
      const data = response.data;
      
      if (!data || !data.entries) {
        throw new Error("Invalid response format");
      }

      // Map data.entries to our Patient interface using the vitals already included in the response
      const patients: Patient[] = data.entries.map((entry: any) => {
        const vitals = entry.vitals || {};
        
        // Ensure vitals are integers as requested by user
        if (vitals.heart_rate_bpm != null) vitals.heart_rate_bpm = Math.round(Number(vitals.heart_rate_bpm));
        if (vitals.systolic_bp_mmhg != null) vitals.systolic_bp_mmhg = Math.round(Number(vitals.systolic_bp_mmhg));
        if (vitals.diastolic_bp_mmhg != null) vitals.diastolic_bp_mmhg = Math.round(Number(vitals.diastolic_bp_mmhg));
        if (vitals.spo2_percent != null) vitals.spo2_percent = Math.round(Number(vitals.spo2_percent));
        
        const patientName = `${entry.patient.first_name} ${entry.patient.last_name || ''}`.trim();
        
        let age = 0;
        if (entry.patient.estimated_age_years) {
            age = parseFloat(entry.patient.estimated_age_years);
        } else if (entry.patient.date_of_birth) {
            const dob = new Date(entry.patient.date_of_birth);
            const diff = Date.now() - dob.getTime();
            age = Math.floor(diff / (1000 * 60 * 60 * 24 * 365.25));
        }
        
        return {
          id: entry.patient.id,
          encounter_id: entry.encounter.id,
          assessment_id: undefined, // Needs to be fetched if required
          name: patientName,
          age: age,
          avatar: entry.patient.profile_image_path || `https://i.pravatar.cc/150?u=${entry.patient.id}`,
          complaint: entry.encounter.chief_complaint || 'No complaint recorded',
          status: entry.queue_entry.status,
          timeInQueue: entry.queue_entry.entered_at,
          esi: entry.final_esi,
          vitals: vitals,
          allocation: entry.allocation,
          aiSuggestion: {
            esi: entry.final_esi || 5,
            redFlags: entry.safety_alert ? ['Safety Alert'] : [],
            differential: [],
            needsConfirmation: false // Assumed confirmed or logic goes here
          }
        };
      });

      return {
        length: patients.length,
        loadMultiplier: 1.0, // Could be calculated based on entries
        patients: patients,
      };
    } catch (error) {
      console.warn("Failed to fetch real queue from backend, falling back to mock data.", error);
      return {
        length: mockQueue.length,
        loadMultiplier: 1.2,
        patients: [...mockQueue],
      };
    }
  },
  
  getHospitals: async (): Promise<any[]> => {
    try {
      const response = await apiClient.get('/api/v1/hospitals');
      return response.data?.items || [];
    } catch (error) {
      console.warn("Failed to fetch hospitals, returning mock");
      return [
        { id: 'mock-hospital', name: 'ResiliCare Central' },
        { id: 'mock-hospital-north', name: 'ResiliCare North' },
        { id: 'mock-hospital-east', name: 'ResiliCare East' }
      ];
    }
  },

  getWards: async (hospitalId: string): Promise<any[]> => {
    try {
      const response = await apiClient.get(`/api/v1/hospitals/${hospitalId}/wards`);
      return response.data?.items || [];
    } catch (error) {
      console.warn("Failed to fetch wards, returning mock");
      return [
        { id: 'mock-ward-1', name: 'Cardiac ICU' },
        { id: 'mock-ward-2', name: 'General Surgery' }
      ];
    }
  },

  getDoctors: async (wardId: string): Promise<any[]> => {
    try {
      const response = await apiClient.get(`/api/v1/staff?staff_type=doctor&ward_id=${wardId}`);
      return response.data?.items || [];
    } catch (error) {
      console.warn("Failed to fetch doctors, returning mock");
      return [
        { id: 'mock-dr-1', first_name: 'Sarah', last_name: 'Hayes' },
        { id: 'mock-dr-2', first_name: 'James', last_name: 'Wilson' }
      ];
    }
  },
  
  getSuggestions: async (): Promise<Patient[]> => {
    // Missing in backend.
    return mockQueue.filter(p => p.aiSuggestion?.needsConfirmation);
  },
  
  updateVitals: async (encounterId: string, vitals: any): Promise<void> => {
    // Adapted to backend schema (expects encounter_id).
    // Future: await apiClient.post(`/api/v1/encounters/${encounterId}/vitals`, vitals);
    // Since mock patients are not in the backend DB, we mock the success.
    const patient = mockQueue.find(p => p.encounter_id === encounterId || p.id === encounterId);
    if (patient) patient.vitals = vitals;
  },
  
  confirmSuggestion: async (assessmentId: string, clinicianId: string, role: string): Promise<void> => {
    // Adapted to backend schema (expects assessment_id).
    // Future: await apiClient.post(`/api/v1/assessments/${assessmentId}/decisions`, { ... });
    const patient = mockQueue.find(p => p.assessment_id === assessmentId || p.id === assessmentId);
    if (patient && patient.aiSuggestion) {
      patient.esi = patient.aiSuggestion.esi;
      patient.aiSuggestion.needsConfirmation = false;
    }
  },
  
  overrideSuggestion: async (assessmentId: string, esi: number, reasonCode: string, reasonText: string, clinicianId: string, role: string): Promise<void> => {
    // Adapted to backend schema (expects assessment_id).
    const patient = mockQueue.find(p => p.assessment_id === assessmentId || p.id === assessmentId);
    if (patient && patient.aiSuggestion) {
      patient.esi = esi;
      patient.aiSuggestion.needsConfirmation = false;
    }
  },

  getReasonCodes: async (): Promise<{id: string, label: string}[]> => {
    // Missing in backend.
    return [
      { id: 'r1', label: 'Patient condition worsening' },
      { id: 'r2', label: 'AI over-triaged (stable)' },
      { id: 'r3', label: 'Protocol exception' },
    ];
  },

  // --- Admin Interface ---
  getProfiles: async (): Promise<HospitalProfile[]> => {
    // Missing global listing endpoint in backend.
    return hospitalProfiles.map(p => ({ ...p, active: p.id === activeProfileId }));
  },

  setProfile: async (profileId: string): Promise<void> => {
    activeProfileId = profileId;
  },

  triggerSurge: async (): Promise<void> => {
    // Missing in backend.
    console.log("Surge protocol triggered");
  },

  getOverrideRates: async (): Promise<any> => {
    // Missing in backend.
    return [
      { name: 'Mon', confirm: 40, override: 10 },
      { name: 'Tue', confirm: 45, override: 8 },
      { name: 'Wed', confirm: 38, override: 12 },
      { name: 'Thu', confirm: 50, override: 5 },
      { name: 'Fri', confirm: 55, override: 15 },
    ];
  },

  // --- Patient Interface ---
  processKioskText: async (transcript: string): Promise<any> => {
    // Missing in backend.
    return {
      chiefComplaint: transcript,
      redFlags: transcript.toLowerCase().includes('pain') ? ['Pain identified'] : [],
      differential: ['Review needed'],
    };
  }
};
