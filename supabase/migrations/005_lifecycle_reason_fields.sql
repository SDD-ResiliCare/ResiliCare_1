-- Preserve operational and financial lifecycle reasons instead of discarding them.
alter table queue_entries add column exit_reason text;

alter table invoices
  add column voided_at timestamptz,
  add column void_reason text,
  add column voided_by_staff_id uuid references staff(id);
