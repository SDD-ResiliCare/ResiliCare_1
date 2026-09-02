-- Durable per-doctor work queues derived from nurse/receptionist allocation.
create table doctor_work_items (
  id uuid primary key default gen_random_uuid(),
  hospital_id uuid not null references hospitals(id),
  encounter_id uuid not null references encounters(id),
  doctor_staff_id uuid not null references staff(id),
  ward_id uuid not null references wards(id),
  status varchar(24) not null,
  priority_esi smallint not null,
  queued_at timestamptz not null,
  started_at timestamptz,
  completed_at timestamptz,
  assigned_by_staff_id uuid not null references staff(id),
  allocation_reason text not null,
  end_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ck_doctor_work_items_status check (
    status in ('waiting', 'in_service', 'completed', 'transferred', 'cancelled')
  ),
  constraint ck_doctor_work_items_priority_esi check (priority_esi between 1 and 5),
  constraint ck_doctor_work_items_timestamps check (
    (started_at is null or started_at >= queued_at)
    and (completed_at is null or started_at is not null)
    and (completed_at is null or completed_at >= started_at)
  )
);

create unique index uq_doctor_work_items_active_encounter
  on doctor_work_items (encounter_id)
  where status in ('waiting', 'in_service');

create unique index uq_doctor_work_items_current_doctor
  on doctor_work_items (doctor_staff_id)
  where status = 'in_service';

create index ix_doctor_work_items_doctor_status_queue
  on doctor_work_items (doctor_staff_id, status, priority_esi, queued_at);

create trigger set_doctor_work_items_updated_at
before update on doctor_work_items
for each row execute function public.set_updated_at();

alter table doctor_work_items enable row level security;
revoke all on table doctor_work_items from anon, authenticated;
