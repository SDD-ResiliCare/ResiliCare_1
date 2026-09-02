from scripts.seed_prototype_dataset import build_seed_plan


def test_default_seed_contains_only_40_live_patients_and_related_encounters():
    plan = {table: rows for table, _, rows in build_seed_plan()}
    assert len(plan["hospitals"]) == 4
    assert len(plan["wards"]) == 20
    assert len(plan["staff"]) == 40
    assert len(plan["patients"]) == 40
    assert len(plan["encounters"]) == 40
    assert len(plan["vital_observations"]) == 46
    assert len(plan["symptom_responses"]) == 240
    assert len(plan["triage_assessments"]) == 40
    assert all(row["ai_overview"].strip() for row in plan["triage_assessments"])
    assert all(row["recommended_ward_id"] for row in plan["triage_assessments"])
    assert all(row["allocation_overview"].strip() for row in plan["doctor_work_items"])
    assert len(plan["invoices"]) == 40


def test_seed_ids_are_deterministic_and_unique_per_table():
    first = {table: rows for table, _, rows in build_seed_plan()}
    second = {table: rows for table, _, rows in build_seed_plan()}
    for table, rows in first.items():
        key = "staff_id" if table == "clinical_staff_profiles" else "id"
        ids = [row[key] for row in rows]
        assert len(ids) == len(set(ids))
        assert ids == [row[key] for row in second[table]]


def test_reserve_patient_profiles_are_opt_in():
    default = {table: rows for table, _, rows in build_seed_plan()}
    with_reserve = {table: rows for table, _, rows in build_seed_plan(include_reserve=True)}
    assert len(default["patients"]) == 40
    assert len(with_reserve["patients"]) == 100
    assert len(with_reserve["encounters"]) == 40
