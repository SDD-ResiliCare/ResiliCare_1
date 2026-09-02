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
  aiOverview?: string;
  aiOverviewFactors?: Record<string, unknown>;
  allocation?: {
    hospital_id?: string;
    hospital_name?: string;
    suggested_ward?: { name: string; ward_code: string; id: string };
    primary_doctor?: { first_name: string; last_name: string; employee_code: string; id: string };
    allocation_overview?: string;
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

export interface DoctorWorkload {
  doctor: {
    id: string;
    employee_code: string;
    first_name: string;
    last_name?: string;
  };
  availability: string;
  current_patient?: {
    work_item_id: string;
    encounter_id: string;
    encounter_code: string;
    patient_id: string;
    patient_name: string;
    ward: {
      id: string;
      name: string;
      ward_code: string;
    };
    status: string;
    confirmed_esi: number;
    queue_position?: number;
    queued_at: string;
  };
  waiting_count: number;
  waiting_patients: Array<{
    work_item_id: string;
    encounter_id: string;
    encounter_code: string;
    patient_id: string;
    patient_name: string;
    ward: {
      id: string;
      name: string;
      ward_code: string;
    };
    status: string;
    confirmed_esi: number;
    queue_position?: number;
    queued_at: string;
  }>;
}
