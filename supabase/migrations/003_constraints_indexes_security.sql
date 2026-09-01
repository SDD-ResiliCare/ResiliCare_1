-- Domain constraints that are clearer and safer in PostgreSQL than in application code.
alter table esi_care_area_rules add constraint ck_esi_care_area_rules_level check (esi_level between 1 and 5);
alter table triage_assessments add constraint ck_triage_assessments_proposed_esi check (proposed_esi between 1 and 5);
alter table triage_assessments add constraint ck_triage_assessments_recommended_esi check (recommended_esi between 1 and 5);
alter table triage_assessments add constraint ck_triage_assessments_maximum_esi check (maximum_allowed_esi is null or maximum_allowed_esi between 1 and 5);
alter table clinician_decisions add constraint ck_clinician_decisions_final_esi check (final_esi between 1 and 5);
alter table reviews add constraint ck_reviews_rating check (overall_rating between 1 and 5);
alter table feedback_submissions add constraint ck_feedback_rating check (rating is null or rating between 1 and 5);
alter table reviews add constraint ck_reviews_target check (
  (review_target = 'hospital' and reviewed_staff_id is null)
  or (review_target = 'doctor' and reviewed_staff_id is not null)
);
alter table vital_observations add constraint ck_vitals_avpu check (avpu is null or avpu in ('A', 'V', 'P', 'U'));
alter table vital_observations add constraint ck_vitals_gcs_eye check (gcs_eye is null or gcs_eye between 1 and 4);
alter table vital_observations add constraint ck_vitals_gcs_verbal check (gcs_verbal is null or gcs_verbal between 1 and 5);
alter table vital_observations add constraint ck_vitals_gcs_motor check (gcs_motor is null or gcs_motor between 1 and 6);
alter table vital_observations add constraint ck_vitals_gcs_total check (gcs_total is null or gcs_total between 3 and 15);
alter table vital_observations add constraint ck_vitals_pain_score check (pain_score is null or pain_score between 0 and 10);
alter table invoices add constraint ck_invoices_nonnegative_totals check (
  subtotal >= 0 and discount_total >= 0 and tax_total >= 0 and grand_total >= 0 and amount_paid >= 0 and balance_due >= 0
);
alter table invoice_items add constraint ck_invoice_items_nonnegative check (
  quantity > 0 and unit_price >= 0 and discount_amount >= 0 and tax_amount >= 0 and line_total >= 0
);
alter table payments add constraint ck_payments_positive check (amount > 0);
alter table feedback_invites add constraint ck_feedback_invite_usage check (max_uses > 0 and used_count >= 0 and used_count <= max_uses);
alter table hospital_operational_configs add constraint ck_operational_config_period check (
  effective_until is null or effective_until > effective_from
);
alter table staff add constraint ck_staff_employment_period check (left_on is null or left_on >= joined_on);
alter table patient_identifiers add constraint ck_patient_identifier_period check (valid_until is null or valid_until >= valid_from);
alter table facility_scheme_terms add constraint ck_facility_scheme_period check (valid_until is null or valid_until >= valid_from);

create unique index uq_hospital_active_operational_config
  on hospital_operational_configs (hospital_id) where is_active;
create unique index uq_hospital_review_per_encounter
  on reviews (encounter_id) where review_target = 'hospital';
create unique index uq_doctor_review_per_encounter
  on reviews (encounter_id, reviewed_staff_id) where review_target = 'doctor';

create index ix_encounters_patient_arrived on encounters (patient_id, arrived_at desc);
create index ix_encounters_hospital_status on encounters (hospital_id, status);
create index ix_queue_entries_queue_status on queue_entries (queue_id, status, entered_at);
create index ix_vital_observations_encounter_observed on vital_observations (encounter_id, observed_at desc);
create index ix_triage_assessments_encounter_number on triage_assessments (encounter_id, assessment_number desc);
create index ix_audit_events_resource on audit_events (resource_type, resource_id, occurred_at desc);
create index ix_audit_events_hospital_time on audit_events (hospital_id, occurred_at desc);

-- Maintain updated_at consistently even for writes outside FastAPI.
do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'hospitals','wards','staff','clinical_staff_profiles','staff_ward_assignments',
    'hospital_operational_configs','esi_care_area_rules','escalation_routes','referral_facilities',
    'facility_scheme_terms','patients','patient_identifiers','patient_access_links','patient_allergies',
    'patient_conditions','queues','encounters','queue_entries','encounter_location_history',
    'encounter_participants','encounter_coverages','routing_recommendations','vital_observations',
    'questionnaires','questionnaire_questions','symptom_interviews','symptom_responses',
    'triage_assessments','assessment_safety_actions','clinician_decisions','encounter_diagnoses',
    'encounter_closures','prescriptions','prescription_items','invoices','invoice_items','payments',
    'feedback_invites','reviews','feedback_submissions'
  ] loop
    execute format(
      'create trigger set_%I_updated_at before update on public.%I for each row execute function public.set_updated_at()',
      table_name, table_name
    );
  end loop;
end;
$$;

create or replace function public.reject_audit_mutation()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  raise exception 'audit_events are append-only';
end;
$$;

create trigger audit_events_no_update
before update or delete on audit_events
for each row execute function public.reject_audit_mutation();

-- Clinical access goes through FastAPI. Browser roles receive no direct table access.
do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'hospitals','wards','staff','clinical_staff_profiles','staff_ward_assignments',
    'hospital_operational_configs','esi_care_area_rules','escalation_routes','referral_facilities',
    'facility_scheme_terms','patients','patient_identifiers','patient_access_links','patient_allergies',
    'patient_conditions','queues','encounters','queue_entries','encounter_location_history',
    'encounter_participants','encounter_coverages','routing_recommendations','vital_observations',
    'questionnaires','questionnaire_questions','symptom_interviews','symptom_responses',
    'triage_assessments','assessment_safety_actions','clinician_decisions','encounter_diagnoses',
    'encounter_closures','prescriptions','prescription_items','invoices','invoice_items','payments',
    'feedback_invites','reviews','feedback_submissions','audit_events'
  ] loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('revoke all on table public.%I from anon, authenticated', table_name);
  end loop;
end;
$$;
