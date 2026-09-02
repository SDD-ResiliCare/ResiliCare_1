export type Role = 'nurse' | 'patient' | 'admin';

export interface Patient {
  id: string; // patient_id
  encounter_id?: string;
  assessment_id?: string;
  name: string;
  age: number;
  avatar?: string;
  complaint?: string;
  esi?: number;
  status: 'waiting' | 'in-progress' | 'discharged';
  vitals?: {
    heart_rate_bpm?: number;
    respiratory_rate_bpm?: number;
    spo2_percent?: number;
    systolic_bp_mmhg?: number;
    diastolic_bp_mmhg?: number;
    temperature_c?: number;
    avpu?: string;
  };
  timeInQueue?: string;
  assignedTo?: string;
  allocation?: {
    hospital_name?: string;
    suggested_ward?: { name: string; ward_code: string; id: string };
    primary_doctor?: { first_name: string; last_name: string; employee_code: string; id: string };
  };
  aiSuggestion?: {
    esi: number;
    redFlags: string[];
    differential: string[];
    needsConfirmation: boolean;
  };
}

export interface QueueSnapshot {
  length: number;
  loadMultiplier: number;
  patients: Patient[];
}

export interface SurgeEvidence {
  before: QueueSnapshot;
  after: QueueSnapshot;
}

export interface HospitalProfile {
  id: string;
  name: string;
  capabilities: string[];
  active: boolean;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  action: string;
  actor: string;
  details: string;
}
