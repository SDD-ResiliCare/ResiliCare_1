-- Versioned clinical recommendation explanations and confirmed allocation rationale.
alter table triage_assessments
  add column recommended_ward_id uuid references wards(id),
  add column ai_overview text,
  add column ai_overview_factors jsonb not null default '{}'::jsonb;

update triage_assessments ta
set recommended_ward_id = (
  select rule.ward_id
  from esi_care_area_rules rule
  where rule.operational_config_id = ta.operational_config_id
    and rule.esi_level = ta.recommended_esi
  order by rule.is_default desc, rule.priority
  limit 1
);

update triage_assessments
set
  ai_overview = format(
    'Recommended ESI %s from the recorded assessment inputs. Hospital routing was evaluated for this acuity; nurse or clinician confirmation is required before assignment.',
    recommended_esi
  ),
  ai_overview_factors = jsonb_build_object(
    'recommended_esi', recommended_esi,
    'possible_esi_levels', to_jsonb(possible_esi_levels),
    'confidence_label', uncertainty_label,
    'requires_senior_review', requires_senior_review,
    'matched_safety_rules', matched_safety_rules,
    'uncertainty_reasons', to_jsonb(missing_input_flags),
    'recommended_ward_id', recommended_ward_id,
    'method', 'MIGRATION_BACKFILL'
  )
where ai_overview is null;

alter table triage_assessments alter column ai_overview set not null;
create index ix_triage_assessments_recommended_ward on triage_assessments (recommended_ward_id);

alter table doctor_work_items
  add column allocation_overview text,
  add column allocation_overview_factors jsonb not null default '{}'::jsonb;

update doctor_work_items
set
  allocation_overview = format(
    'Ward and doctor assignment was confirmed by staff for ESI %s. Doctor work status at assignment: %s. Recorded reason: %s.',
    priority_esi,
    status,
    allocation_reason
  ),
  allocation_overview_factors = jsonb_build_object(
    'final_esi', priority_esi,
    'ward_id', ward_id,
    'doctor_staff_id', doctor_staff_id,
    'doctor_was_busy', status = 'waiting',
    'allocator_reason', allocation_reason,
    'method', 'MIGRATION_BACKFILL'
  )
where allocation_overview is null;

alter table doctor_work_items alter column allocation_overview set not null;
