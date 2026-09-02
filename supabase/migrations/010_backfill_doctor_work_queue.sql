-- Reconcile legacy active primary-doctor assignments into the durable work queue.
-- The backfill is idempotent and only creates work for clinician-confirmed encounters.
with latest_assessments as (
  select distinct on (ta.encounter_id)
    ta.encounter_id,
    coalesce(cd.final_esi, ta.recommended_esi) as final_esi
  from triage_assessments ta
  left join clinician_decisions cd
    on cd.assessment_id = ta.id and cd.superseded_at is null
  where ta.assessment_status in ('confirmed', 'overridden')
  order by ta.encounter_id, ta.assessment_number desc, cd.decided_at desc nulls last
), candidates as (
  select
    e.hospital_id,
    e.id as encounter_id,
    ep.staff_id as doctor_staff_id,
    e.current_ward_id as ward_id,
    la.final_esi,
    ep.assigned_at,
    coalesce(
      ep.assigned_by_staff_id,
      (
        select fallback.id
        from staff fallback
        where fallback.hospital_id = e.hospital_id
          and fallback.staff_type in ('nurse', 'receptionist', 'reception_staff')
          and fallback.employment_status = 'active'
        order by fallback.id
        limit 1
      )
    ) as assigned_by_staff_id,
    row_number() over (
      partition by ep.staff_id
      order by la.final_esi, ep.assigned_at, e.id
    ) as doctor_rank,
    exists (
      select 1 from doctor_work_items existing
      where existing.doctor_staff_id = ep.staff_id
        and existing.status in ('waiting', 'in_service')
    ) as doctor_already_busy
  from encounter_participants ep
  join encounters e on e.id = ep.encounter_id
  join latest_assessments la on la.encounter_id = e.id
  where ep.role = 'primary_doctor'
    and ep.ended_at is null
    and e.current_ward_id is not null
    and e.status not in ('completed', 'cancelled', 'entered_in_error')
    and not exists (
      select 1 from doctor_work_items existing_encounter
      where existing_encounter.encounter_id = e.id
        and existing_encounter.status in ('waiting', 'in_service')
    )
)
insert into doctor_work_items (
  hospital_id, encounter_id, doctor_staff_id, ward_id, status, priority_esi,
  queued_at, started_at, assigned_by_staff_id, allocation_reason,
  allocation_overview, allocation_overview_factors
)
select
  c.hospital_id,
  c.encounter_id,
  c.doctor_staff_id,
  c.ward_id,
  case when not c.doctor_already_busy and c.doctor_rank = 1 then 'in_service' else 'waiting' end,
  c.final_esi,
  c.assigned_at,
  case when not c.doctor_already_busy and c.doctor_rank = 1 then c.assigned_at else null end,
  c.assigned_by_staff_id,
  'Backfilled from legacy active primary-doctor assignment',
  format(
    'Legacy ward and doctor assignment reconciled for confirmed ESI %s. Doctor workload was reconstructed from active assignments; queue ordering uses ESI and assignment time.',
    c.final_esi
  ),
  jsonb_build_object(
    'backfill', true,
    'final_esi', c.final_esi,
    'ward_id', c.ward_id,
    'doctor_staff_id', c.doctor_staff_id,
    'doctor_rank', c.doctor_rank,
    'doctor_already_busy', c.doctor_already_busy,
    'method', 'LEGACY_ASSIGNMENT_RECONCILIATION'
  )
from candidates c;
