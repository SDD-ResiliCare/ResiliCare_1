-- An encounter can occupy only one current ward/bed location at a time.
create unique index uq_encounter_active_location
  on encounter_location_history (encounter_id)
  where exited_at is null;
