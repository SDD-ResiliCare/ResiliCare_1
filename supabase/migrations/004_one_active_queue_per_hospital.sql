-- V1 exposes one operational patient queue per hospital.
create unique index uq_queues_active_hospital
  on queues (hospital_id)
  where status = 'active';
