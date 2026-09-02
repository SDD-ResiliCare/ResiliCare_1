-- Generated from src/db/models. Review before applying.

CREATE TABLE hospitals (
	hospital_code VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	facility_type VARCHAR(50) NOT NULL, 
	address JSONB NOT NULL, 
	timezone VARCHAR(64) NOT NULL, 
	phone VARCHAR(32), 
	email VARCHAR(320), 
	outbound_transfer_enabled BOOLEAN NOT NULL, 
	profile_image_path TEXT, 
	status VARCHAR(24) NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_hospitals PRIMARY KEY (id), 
	CONSTRAINT uq_hospitals_hospital_code UNIQUE (hospital_code)
);

CREATE TABLE wards (
	hospital_id UUID NOT NULL, 
	ward_code VARCHAR(50) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	ward_type VARCHAR(50) NOT NULL, 
	floor_label VARCHAR(50), 
	contact_extension VARCHAR(20), 
	capacity INTEGER, 
	status VARCHAR(24) NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_wards PRIMARY KEY (id), 
	CONSTRAINT uq_wards_hospital_id UNIQUE (hospital_id, ward_code), 
	CONSTRAINT fk_wards_hospital_id_hospitals FOREIGN KEY(hospital_id) REFERENCES hospitals (id)
);

CREATE TABLE staff (
	hospital_id UUID NOT NULL, 
	auth_user_id UUID, 
	employee_code VARCHAR(50) NOT NULL, 
	staff_type VARCHAR(32) NOT NULL, 
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100), 
	phone VARCHAR(32), 
	email VARCHAR(320), 
	profile_image_path TEXT, 
	employment_status VARCHAR(24) NOT NULL, 
	joined_on DATE NOT NULL, 
	left_on DATE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_staff PRIMARY KEY (id), 
	CONSTRAINT uq_staff_hospital_id UNIQUE (hospital_id, employee_code), 
	CONSTRAINT fk_staff_hospital_id_hospitals FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	CONSTRAINT uq_staff_auth_user_id UNIQUE (auth_user_id), 
	CONSTRAINT fk_staff_auth_user_id_users FOREIGN KEY(auth_user_id) REFERENCES auth.users (id) ON DELETE SET NULL
);

CREATE TABLE clinical_staff_profiles (
	staff_id UUID NOT NULL, 
	registration_number VARCHAR(100), 
	registration_authority VARCHAR(150), 
	qualification VARCHAR(200), 
	specialty VARCHAR(120), 
	practice_started_on DATE, 
	professional_grade VARCHAR(100), 
	bio TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_clinical_staff_profiles PRIMARY KEY (staff_id), 
	CONSTRAINT fk_clinical_staff_profiles_staff_id_staff FOREIGN KEY(staff_id) REFERENCES staff (id)
);

CREATE TABLE staff_ward_assignments (
	staff_id UUID NOT NULL, 
	ward_id UUID NOT NULL, 
	role_in_ward VARCHAR(80) NOT NULL, 
	is_primary_ward BOOLEAN NOT NULL, 
	assigned_from TIMESTAMP WITH TIME ZONE NOT NULL, 
	assigned_until TIMESTAMP WITH TIME ZONE, 
	assigned_by_staff_id UUID, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_staff_ward_assignments PRIMARY KEY (id), 
	CONSTRAINT fk_staff_ward_assignments_staff_id_staff FOREIGN KEY(staff_id) REFERENCES staff (id), 
	CONSTRAINT fk_staff_ward_assignments_ward_id_wards FOREIGN KEY(ward_id) REFERENCES wards (id), 
	CONSTRAINT fk_staff_ward_assignments_assigned_by_staff_id_staff FOREIGN KEY(assigned_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE hospital_operational_configs (
	hospital_id UUID NOT NULL, 
	version INTEGER NOT NULL, 
	queue_warning_threshold INTEGER NOT NULL, 
	surge_threshold INTEGER NOT NULL, 
	transfer_first_for_unsupported BOOLEAN NOT NULL, 
	effective_from TIMESTAMP WITH TIME ZONE NOT NULL, 
	effective_until TIMESTAMP WITH TIME ZONE, 
	created_by_staff_id UUID, 
	is_active BOOLEAN NOT NULL, 
	config_hash VARCHAR(64) NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_hospital_operational_configs PRIMARY KEY (id), 
	CONSTRAINT uq_hospital_operational_configs_hospital_id UNIQUE (hospital_id, version), 
	CONSTRAINT fk_hospital_operational_configs_hospital_id_hospitals FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	CONSTRAINT fk_hospital_operational_configs_created_by_staff_id_staff FOREIGN KEY(created_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE esi_care_area_rules (
	operational_config_id UUID NOT NULL, 
	esi_level SMALLINT NOT NULL, 
	ward_id UUID NOT NULL, 
	priority INTEGER NOT NULL, 
	is_default BOOLEAN NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_esi_care_area_rules PRIMARY KEY (id), 
	CONSTRAINT uq_esi_care_area_rules_operational_config_id UNIQUE (operational_config_id, esi_level, ward_id), 
	CONSTRAINT fk_esi_care_area_rules_operational_config_id_hospital_o_8237 FOREIGN KEY(operational_config_id) REFERENCES hospital_operational_configs (id), 
	CONSTRAINT fk_esi_care_area_rules_ward_id_wards FOREIGN KEY(ward_id) REFERENCES wards (id)
);

CREATE TABLE escalation_routes (
	operational_config_id UUID NOT NULL, 
	trigger_code VARCHAR(100) NOT NULL, 
	contact_staff_id UUID, 
	contact_ward_id UUID, 
	fallback_contact_name VARCHAR(150), 
	phone_extension VARCHAR(20), 
	priority INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_escalation_routes PRIMARY KEY (id), 
	CONSTRAINT fk_escalation_routes_operational_config_id_hospital_ope_3bb1 FOREIGN KEY(operational_config_id) REFERENCES hospital_operational_configs (id), 
	CONSTRAINT fk_escalation_routes_contact_staff_id_staff FOREIGN KEY(contact_staff_id) REFERENCES staff (id), 
	CONSTRAINT fk_escalation_routes_contact_ward_id_wards FOREIGN KEY(contact_ward_id) REFERENCES wards (id)
);

CREATE TABLE referral_facilities (
	facility_code VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	facility_type VARCHAR(50) NOT NULL, 
	address JSONB NOT NULL, 
	latitude NUMERIC(9, 6), 
	longitude NUMERIC(9, 6), 
	phone VARCHAR(32), 
	supported_specialties JSONB NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	last_verified_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_referral_facilities PRIMARY KEY (id), 
	CONSTRAINT uq_referral_facilities_facility_code UNIQUE (facility_code)
);

CREATE TABLE facility_scheme_terms (
	facility_id UUID NOT NULL, 
	scheme_code VARCHAR(80) NOT NULL, 
	cashless_available BOOLEAN NOT NULL, 
	room_rent_cap NUMERIC(12, 2), 
	notes TEXT, 
	valid_from DATE NOT NULL, 
	valid_until DATE, 
	verified_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	verified_by_staff_id UUID, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_facility_scheme_terms PRIMARY KEY (id), 
	CONSTRAINT uq_facility_scheme_terms_facility_id UNIQUE (facility_id, scheme_code, valid_from), 
	CONSTRAINT fk_facility_scheme_terms_facility_id_referral_facilities FOREIGN KEY(facility_id) REFERENCES referral_facilities (id), 
	CONSTRAINT fk_facility_scheme_terms_verified_by_staff_id_staff FOREIGN KEY(verified_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE patients (
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100), 
	date_of_birth DATE, 
	estimated_age_years NUMERIC(5, 2), 
	sex_at_birth VARCHAR(30), 
	gender_identity VARCHAR(50), 
	phone VARCHAR(32), 
	email VARCHAR(320), 
	address JSONB, 
	preferred_language VARCHAR(20), 
	profile_image_path TEXT, 
	deceased_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(24) NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_patients PRIMARY KEY (id)
);

CREATE TABLE patient_identifiers (
	patient_id UUID NOT NULL, 
	hospital_id UUID NOT NULL, 
	identifier_type VARCHAR(40) NOT NULL, 
	identifier_value VARCHAR(120) NOT NULL, 
	valid_from DATE NOT NULL, 
	valid_until DATE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_patient_identifiers PRIMARY KEY (id), 
	CONSTRAINT uq_patient_identifiers_hospital_id UNIQUE (hospital_id, identifier_type, identifier_value), 
	CONSTRAINT fk_patient_identifiers_patient_id_patients FOREIGN KEY(patient_id) REFERENCES patients (id), 
	CONSTRAINT fk_patient_identifiers_hospital_id_hospitals FOREIGN KEY(hospital_id) REFERENCES hospitals (id)
);

CREATE TABLE patient_access_links (
	patient_id UUID NOT NULL, 
	auth_user_id UUID NOT NULL, 
	relationship VARCHAR(30) NOT NULL, 
	access_level VARCHAR(30) NOT NULL, 
	identity_verified_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	granted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(24) NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_patient_access_links PRIMARY KEY (id), 
	CONSTRAINT uq_patient_access_links_patient_id UNIQUE (patient_id, auth_user_id), 
	CONSTRAINT fk_patient_access_links_patient_id_patients FOREIGN KEY(patient_id) REFERENCES patients (id), 
	CONSTRAINT fk_patient_access_links_auth_user_id_users FOREIGN KEY(auth_user_id) REFERENCES auth.users (id) ON DELETE CASCADE
);

CREATE TABLE patient_allergies (
	patient_id UUID NOT NULL, 
	substance VARCHAR(200) NOT NULL, 
	reaction TEXT, 
	severity VARCHAR(24), 
	verification_status VARCHAR(24) NOT NULL, 
	recorded_by_staff_id UUID, 
	recorded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_patient_allergies PRIMARY KEY (id), 
	CONSTRAINT fk_patient_allergies_patient_id_patients FOREIGN KEY(patient_id) REFERENCES patients (id), 
	CONSTRAINT fk_patient_allergies_recorded_by_staff_id_staff FOREIGN KEY(recorded_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE patient_conditions (
	patient_id UUID NOT NULL, 
	condition_code VARCHAR(80), 
	condition_name VARCHAR(200) NOT NULL, 
	clinical_status VARCHAR(24) NOT NULL, 
	verification_status VARCHAR(24) NOT NULL, 
	onset_at TIMESTAMP WITH TIME ZONE, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	recorded_by_staff_id UUID NOT NULL, 
	notes TEXT, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_patient_conditions PRIMARY KEY (id), 
	CONSTRAINT fk_patient_conditions_patient_id_patients FOREIGN KEY(patient_id) REFERENCES patients (id), 
	CONSTRAINT fk_patient_conditions_recorded_by_staff_id_staff FOREIGN KEY(recorded_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE queues (
	hospital_id UUID NOT NULL, 
	ward_id UUID, 
	queue_code VARCHAR(50) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	queue_type VARCHAR(40) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_queues PRIMARY KEY (id), 
	CONSTRAINT uq_queues_hospital_id UNIQUE (hospital_id, queue_code), 
	CONSTRAINT fk_queues_hospital_id_hospitals FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	CONSTRAINT fk_queues_ward_id_wards FOREIGN KEY(ward_id) REFERENCES wards (id)
);

CREATE TABLE encounters (
	hospital_id UUID NOT NULL, 
	patient_id UUID NOT NULL, 
	encounter_code VARCHAR(80) NOT NULL, 
	encounter_type VARCHAR(40) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	arrival_mode VARCHAR(40), 
	arrived_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	triaged_at TIMESTAMP WITH TIME ZONE, 
	care_started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	current_ward_id UUID, 
	chief_complaint TEXT NOT NULL, 
	presenting_details TEXT, 
	symptom_onset_at TIMESTAMP WITH TIME ZONE, 
	symptom_onset_precision VARCHAR(24) NOT NULL, 
	data_quality_notes TEXT, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_encounters PRIMARY KEY (id), 
	CONSTRAINT uq_encounters_hospital_id UNIQUE (hospital_id, encounter_code), 
	CONSTRAINT fk_encounters_hospital_id_hospitals FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	CONSTRAINT fk_encounters_patient_id_patients FOREIGN KEY(patient_id) REFERENCES patients (id), 
	CONSTRAINT fk_encounters_current_ward_id_wards FOREIGN KEY(current_ward_id) REFERENCES wards (id)
);

CREATE TABLE queue_entries (
	queue_id UUID NOT NULL, 
	encounter_id UUID NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	entered_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	called_at TIMESTAMP WITH TIME ZONE, 
	exited_at TIMESTAMP WITH TIME ZONE, 
	priority_boost INTEGER NOT NULL, 
	priority_boost_reason TEXT, 
	priority_boost_expires_at TIMESTAMP WITH TIME ZONE, 
	boosted_by_staff_id UUID, 
	reassessment_due_at TIMESTAMP WITH TIME ZONE, 
	last_ranked_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_queue_entries PRIMARY KEY (id), 
	CONSTRAINT fk_queue_entries_queue_id_queues FOREIGN KEY(queue_id) REFERENCES queues (id), 
	CONSTRAINT fk_queue_entries_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_queue_entries_boosted_by_staff_id_staff FOREIGN KEY(boosted_by_staff_id) REFERENCES staff (id)
);

CREATE UNIQUE INDEX uq_queue_entries_active_encounter ON queue_entries (encounter_id) WHERE exited_at IS NULL;

CREATE TABLE encounter_location_history (
	encounter_id UUID NOT NULL, 
	ward_id UUID NOT NULL, 
	bed_label VARCHAR(50), 
	entered_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	exited_at TIMESTAMP WITH TIME ZONE, 
	transfer_reason TEXT, 
	moved_by_staff_id UUID NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_encounter_location_history PRIMARY KEY (id), 
	CONSTRAINT fk_encounter_location_history_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_encounter_location_history_ward_id_wards FOREIGN KEY(ward_id) REFERENCES wards (id), 
	CONSTRAINT fk_encounter_location_history_moved_by_staff_id_staff FOREIGN KEY(moved_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE encounter_participants (
	encounter_id UUID NOT NULL, 
	staff_id UUID NOT NULL, 
	role VARCHAR(40) NOT NULL, 
	assigned_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	ended_at TIMESTAMP WITH TIME ZONE, 
	assigned_by_staff_id UUID, 
	assignment_reason TEXT, 
	end_reason TEXT, 
	transferred_from_participant_id UUID, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_encounter_participants PRIMARY KEY (id), 
	CONSTRAINT fk_encounter_participants_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_encounter_participants_staff_id_staff FOREIGN KEY(staff_id) REFERENCES staff (id), 
	CONSTRAINT fk_encounter_participants_assigned_by_staff_id_staff FOREIGN KEY(assigned_by_staff_id) REFERENCES staff (id), 
	CONSTRAINT fk_encounter_participants_transferred_from_participant__cd36 FOREIGN KEY(transferred_from_participant_id) REFERENCES encounter_participants (id)
);

CREATE UNIQUE INDEX uq_encounter_active_primary_doctor ON encounter_participants (encounter_id) WHERE role = 'primary_doctor' AND ended_at IS NULL;

CREATE TABLE encounter_coverages (
	encounter_id UUID NOT NULL, 
	scheme_code VARCHAR(80) NOT NULL, 
	payer_name VARCHAR(200), 
	member_reference VARCHAR(120), 
	coverage_status VARCHAR(30) NOT NULL, 
	cashless_status VARCHAR(30), 
	verified_at TIMESTAMP WITH TIME ZONE, 
	verified_by_staff_id UUID, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_encounter_coverages PRIMARY KEY (id), 
	CONSTRAINT fk_encounter_coverages_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_encounter_coverages_verified_by_staff_id_staff FOREIGN KEY(verified_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE vital_observations (
	encounter_id UUID NOT NULL, 
	recorded_by_staff_id UUID, 
	source VARCHAR(30) NOT NULL, 
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	heart_rate_bpm NUMERIC(6, 2), 
	respiratory_rate_bpm NUMERIC(6, 2), 
	spo2_percent NUMERIC(5, 2), 
	systolic_bp_mmhg NUMERIC(6, 2), 
	diastolic_bp_mmhg NUMERIC(6, 2), 
	temperature_c NUMERIC(5, 2), 
	avpu VARCHAR(1), 
	gcs_eye SMALLINT, 
	gcs_verbal SMALLINT, 
	gcs_motor SMALLINT, 
	gcs_total SMALLINT, 
	pain_score SMALLINT, 
	pain_scale VARCHAR(30), 
	pain_location VARCHAR(150), 
	pain_reported_by VARCHAR(30), 
	oxygen_support VARCHAR(100), 
	quality_notes TEXT, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_vital_observations PRIMARY KEY (id), 
	CONSTRAINT fk_vital_observations_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_vital_observations_recorded_by_staff_id_staff FOREIGN KEY(recorded_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE questionnaires (
	code VARCHAR(80) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	complaint_category VARCHAR(100) NOT NULL, 
	version INTEGER NOT NULL, 
	language_code VARCHAR(20) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_questionnaires PRIMARY KEY (id), 
	CONSTRAINT uq_questionnaires_code UNIQUE (code, version, language_code)
);

CREATE TABLE questionnaire_questions (
	questionnaire_id UUID NOT NULL, 
	parent_question_id UUID, 
	question_code VARCHAR(80) NOT NULL, 
	question_text TEXT NOT NULL, 
	answer_type VARCHAR(30) NOT NULL, 
	allowed_options JSONB, 
	validation_rules JSONB, 
	show_when JSONB, 
	display_order INTEGER NOT NULL, 
	clinical_rationale TEXT, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_questionnaire_questions PRIMARY KEY (id), 
	CONSTRAINT uq_questionnaire_questions_questionnaire_id UNIQUE (questionnaire_id, question_code), 
	CONSTRAINT fk_questionnaire_questions_questionnaire_id_questionnaires FOREIGN KEY(questionnaire_id) REFERENCES questionnaires (id), 
	CONSTRAINT fk_questionnaire_questions_parent_question_id_questionn_a60c FOREIGN KEY(parent_question_id) REFERENCES questionnaire_questions (id)
);

CREATE TABLE symptom_interviews (
	encounter_id UUID NOT NULL, 
	questionnaire_id UUID NOT NULL, 
	interview_number INTEGER NOT NULL, 
	respondent_type VARCHAR(30) NOT NULL, 
	conducted_by_staff_id UUID, 
	language_code VARCHAR(20) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_symptom_interviews PRIMARY KEY (id), 
	CONSTRAINT uq_symptom_interviews_encounter_id UNIQUE (encounter_id, interview_number), 
	CONSTRAINT fk_symptom_interviews_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_symptom_interviews_questionnaire_id_questionnaires FOREIGN KEY(questionnaire_id) REFERENCES questionnaires (id), 
	CONSTRAINT fk_symptom_interviews_conducted_by_staff_id_staff FOREIGN KEY(conducted_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE symptom_responses (
	interview_id UUID NOT NULL, 
	question_id UUID, 
	question_text_snapshot TEXT NOT NULL, 
	answer_value JSONB, 
	answer_source VARCHAR(30) NOT NULL, 
	unable_to_answer BOOLEAN NOT NULL, 
	notes TEXT, 
	answered_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_symptom_responses PRIMARY KEY (id), 
	CONSTRAINT fk_symptom_responses_interview_id_symptom_interviews FOREIGN KEY(interview_id) REFERENCES symptom_interviews (id), 
	CONSTRAINT fk_symptom_responses_question_id_questionnaire_questions FOREIGN KEY(question_id) REFERENCES questionnaire_questions (id)
);

CREATE TABLE triage_assessments (
	encounter_id UUID NOT NULL, 
	assessment_number INTEGER NOT NULL, 
	latest_vital_observation_id UUID, 
	source_interview_id UUID, 
	operational_config_id UUID NOT NULL, 
	assessment_status VARCHAR(30) NOT NULL, 
	proposed_esi SMALLINT NOT NULL, 
	maximum_allowed_esi SMALLINT, 
	recommended_esi SMALLINT NOT NULL, 
	possible_esi_levels SMALLINT[] NOT NULL, 
	uncertainty_label VARCHAR(40) NOT NULL, 
	requires_senior_review BOOLEAN NOT NULL, 
	matched_safety_rules JSONB NOT NULL, 
	matched_clinical_pathways JSONB NOT NULL, 
	missing_input_flags VARCHAR[] NOT NULL, 
	input_snapshot JSONB NOT NULL, 
	input_hash VARCHAR(64) NOT NULL, 
	score_source VARCHAR(40) NOT NULL, 
	engine_version VARCHAR(80) NOT NULL, 
	confirmation_due_at TIMESTAMP WITH TIME ZONE, 
	created_by_staff_id UUID, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_triage_assessments PRIMARY KEY (id), 
	CONSTRAINT uq_triage_assessments_encounter_id UNIQUE (encounter_id, assessment_number), 
	CONSTRAINT fk_triage_assessments_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_triage_assessments_latest_vital_observation_id_vital_d718 FOREIGN KEY(latest_vital_observation_id) REFERENCES vital_observations (id), 
	CONSTRAINT fk_triage_assessments_source_interview_id_symptom_interviews FOREIGN KEY(source_interview_id) REFERENCES symptom_interviews (id), 
	CONSTRAINT fk_triage_assessments_operational_config_id_hospital_op_9401 FOREIGN KEY(operational_config_id) REFERENCES hospital_operational_configs (id), 
	CONSTRAINT fk_triage_assessments_created_by_staff_id_staff FOREIGN KEY(created_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE routing_recommendations (
	encounter_id UUID NOT NULL, 
	assessment_id UUID NOT NULL, 
	referral_facility_id UUID, 
	recommendation_type VARCHAR(40) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	clinical_priority_unchanged BOOLEAN NOT NULL, 
	reasoning JSONB NOT NULL, 
	blocked_reasons VARCHAR[] NOT NULL, 
	confirmed_by_staff_id UUID, 
	confirmed_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_routing_recommendations PRIMARY KEY (id), 
	CONSTRAINT fk_routing_recommendations_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_routing_recommendations_assessment_id_triage_assessments FOREIGN KEY(assessment_id) REFERENCES triage_assessments (id), 
	CONSTRAINT fk_routing_recommendations_referral_facility_id_referra_cc14 FOREIGN KEY(referral_facility_id) REFERENCES referral_facilities (id), 
	CONSTRAINT fk_routing_recommendations_confirmed_by_staff_id_staff FOREIGN KEY(confirmed_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE assessment_safety_actions (
	assessment_id UUID NOT NULL, 
	action_code VARCHAR(100) NOT NULL, 
	instruction TEXT NOT NULL, 
	severity VARCHAR(24) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	due_at TIMESTAMP WITH TIME ZONE, 
	acknowledged_by_staff_id UUID, 
	acknowledged_at TIMESTAMP WITH TIME ZONE, 
	completed_by_staff_id UUID, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	completion_notes TEXT, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_assessment_safety_actions PRIMARY KEY (id), 
	CONSTRAINT fk_assessment_safety_actions_assessment_id_triage_assessments FOREIGN KEY(assessment_id) REFERENCES triage_assessments (id), 
	CONSTRAINT fk_assessment_safety_actions_acknowledged_by_staff_id_staff FOREIGN KEY(acknowledged_by_staff_id) REFERENCES staff (id), 
	CONSTRAINT fk_assessment_safety_actions_completed_by_staff_id_staff FOREIGN KEY(completed_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE clinician_decisions (
	assessment_id UUID NOT NULL, 
	decision_type VARCHAR(24) NOT NULL, 
	final_esi SMALLINT NOT NULL, 
	decided_by_staff_id UUID NOT NULL, 
	reason_code VARCHAR(100) NOT NULL, 
	reason_text TEXT, 
	decided_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	supersedes_decision_id UUID, 
	superseded_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_clinician_decisions PRIMARY KEY (id), 
	CONSTRAINT fk_clinician_decisions_assessment_id_triage_assessments FOREIGN KEY(assessment_id) REFERENCES triage_assessments (id), 
	CONSTRAINT fk_clinician_decisions_decided_by_staff_id_staff FOREIGN KEY(decided_by_staff_id) REFERENCES staff (id), 
	CONSTRAINT fk_clinician_decisions_supersedes_decision_id_clinician_d7c7 FOREIGN KEY(supersedes_decision_id) REFERENCES clinician_decisions (id)
);

CREATE TABLE encounter_diagnoses (
	encounter_id UUID NOT NULL, 
	diagnosis_code VARCHAR(80), 
	diagnosis_name VARCHAR(200) NOT NULL, 
	diagnosis_type VARCHAR(30) NOT NULL, 
	clinical_status VARCHAR(30) NOT NULL, 
	diagnosed_by_staff_id UUID NOT NULL, 
	diagnosed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	notes TEXT, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_encounter_diagnoses PRIMARY KEY (id), 
	CONSTRAINT fk_encounter_diagnoses_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_encounter_diagnoses_diagnosed_by_staff_id_staff FOREIGN KEY(diagnosed_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE encounter_closures (
	encounter_id UUID NOT NULL, 
	disposition VARCHAR(40) NOT NULL, 
	medication_decision VARCHAR(40) NOT NULL, 
	clinical_summary TEXT NOT NULL, 
	follow_up_instructions TEXT, 
	closed_by_staff_id UUID NOT NULL, 
	closed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_encounter_closures PRIMARY KEY (id), 
	CONSTRAINT uq_encounter_closures_encounter_id UNIQUE (encounter_id), 
	CONSTRAINT fk_encounter_closures_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_encounter_closures_closed_by_staff_id_staff FOREIGN KEY(closed_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE prescriptions (
	encounter_id UUID NOT NULL, 
	prescriber_participant_id UUID NOT NULL, 
	prescription_number VARCHAR(80) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	revision_number INTEGER NOT NULL, 
	diagnosis_summary TEXT, 
	general_instructions TEXT, 
	issued_at TIMESTAMP WITH TIME ZONE, 
	signed_at TIMESTAMP WITH TIME ZONE, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	cancellation_reason TEXT, 
	supersedes_prescription_id UUID, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_prescriptions PRIMARY KEY (id), 
	CONSTRAINT uq_prescriptions_encounter_id UNIQUE (encounter_id, prescription_number, revision_number), 
	CONSTRAINT fk_prescriptions_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_prescriptions_prescriber_participant_id_encounter_pa_3178 FOREIGN KEY(prescriber_participant_id) REFERENCES encounter_participants (id), 
	CONSTRAINT fk_prescriptions_supersedes_prescription_id_prescriptions FOREIGN KEY(supersedes_prescription_id) REFERENCES prescriptions (id)
);

CREATE TABLE prescription_items (
	prescription_id UUID NOT NULL, 
	generic_name VARCHAR(200) NOT NULL, 
	brand_name VARCHAR(200), 
	dosage_form VARCHAR(80) NOT NULL, 
	strength VARCHAR(80) NOT NULL, 
	dose VARCHAR(80) NOT NULL, 
	route VARCHAR(50) NOT NULL, 
	frequency VARCHAR(100) NOT NULL, 
	duration_value INTEGER, 
	duration_unit VARCHAR(30), 
	quantity NUMERIC(10, 2), 
	is_prn BOOLEAN NOT NULL, 
	prn_reason TEXT, 
	instructions TEXT NOT NULL, 
	start_date DATE, 
	end_date DATE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_prescription_items PRIMARY KEY (id), 
	CONSTRAINT fk_prescription_items_prescription_id_prescriptions FOREIGN KEY(prescription_id) REFERENCES prescriptions (id)
);

CREATE TABLE invoices (
	encounter_id UUID NOT NULL, 
	invoice_number VARCHAR(80) NOT NULL, 
	invoice_version INTEGER NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	currency_code VARCHAR(3) NOT NULL, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	discount_total NUMERIC(12, 2) NOT NULL, 
	tax_total NUMERIC(12, 2) NOT NULL, 
	grand_total NUMERIC(12, 2) NOT NULL, 
	amount_paid NUMERIC(12, 2) NOT NULL, 
	balance_due NUMERIC(12, 2) NOT NULL, 
	issued_at TIMESTAMP WITH TIME ZONE, 
	due_at TIMESTAMP WITH TIME ZONE, 
	created_by_staff_id UUID NOT NULL, 
	supersedes_invoice_id UUID, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_invoices PRIMARY KEY (id), 
	CONSTRAINT uq_invoices_invoice_number UNIQUE (invoice_number, invoice_version), 
	CONSTRAINT fk_invoices_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_invoices_created_by_staff_id_staff FOREIGN KEY(created_by_staff_id) REFERENCES staff (id), 
	CONSTRAINT fk_invoices_supersedes_invoice_id_invoices FOREIGN KEY(supersedes_invoice_id) REFERENCES invoices (id)
);

CREATE TABLE invoice_items (
	invoice_id UUID NOT NULL, 
	service_code VARCHAR(80) NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	description TEXT NOT NULL, 
	quantity NUMERIC(10, 2) NOT NULL, 
	unit_price NUMERIC(12, 2) NOT NULL, 
	discount_amount NUMERIC(12, 2) NOT NULL, 
	tax_amount NUMERIC(12, 2) NOT NULL, 
	line_total NUMERIC(12, 2) NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_invoice_items PRIMARY KEY (id), 
	CONSTRAINT fk_invoice_items_invoice_id_invoices FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE TABLE payments (
	invoice_id UUID NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	payment_method VARCHAR(40) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	external_transaction_reference VARCHAR(200), 
	received_by_staff_id UUID, 
	paid_at TIMESTAMP WITH TIME ZONE, 
	refunded_at TIMESTAMP WITH TIME ZONE, 
	notes TEXT, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_payments PRIMARY KEY (id), 
	CONSTRAINT fk_payments_invoice_id_invoices FOREIGN KEY(invoice_id) REFERENCES invoices (id), 
	CONSTRAINT fk_payments_received_by_staff_id_staff FOREIGN KEY(received_by_staff_id) REFERENCES staff (id)
);

CREATE TABLE feedback_invites (
	encounter_id UUID NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	max_uses INTEGER NOT NULL, 
	used_count INTEGER NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_feedback_invites PRIMARY KEY (id), 
	CONSTRAINT fk_feedback_invites_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT uq_feedback_invites_token_hash UNIQUE (token_hash)
);

CREATE TABLE reviews (
	encounter_id UUID NOT NULL, 
	review_target VARCHAR(20) NOT NULL, 
	reviewed_staff_id UUID, 
	overall_rating SMALLINT NOT NULL, 
	dimension_ratings JSONB NOT NULL, 
	would_recommend BOOLEAN, 
	review_text TEXT, 
	is_anonymous_publicly BOOLEAN NOT NULL, 
	moderation_status VARCHAR(24) NOT NULL, 
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_reviews PRIMARY KEY (id), 
	CONSTRAINT fk_reviews_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_reviews_reviewed_staff_id_staff FOREIGN KEY(reviewed_staff_id) REFERENCES staff (id)
);

CREATE TABLE feedback_submissions (
	encounter_id UUID, 
	hospital_id UUID NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	rating SMALLINT, 
	message TEXT NOT NULL, 
	contact_permission BOOLEAN NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	assigned_to_staff_id UUID, 
	resolution_notes TEXT, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_feedback_submissions PRIMARY KEY (id), 
	CONSTRAINT fk_feedback_submissions_encounter_id_encounters FOREIGN KEY(encounter_id) REFERENCES encounters (id), 
	CONSTRAINT fk_feedback_submissions_hospital_id_hospitals FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	CONSTRAINT fk_feedback_submissions_assigned_to_staff_id_staff FOREIGN KEY(assigned_to_staff_id) REFERENCES staff (id)
);

CREATE TABLE audit_events (
	hospital_id UUID NOT NULL, 
	actor_auth_user_id UUID, 
	actor_staff_id UUID, 
	action VARCHAR(100) NOT NULL, 
	resource_type VARCHAR(80) NOT NULL, 
	resource_id UUID, 
	request_id VARCHAR(100) NOT NULL, 
	event_metadata JSONB NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	CONSTRAINT pk_audit_events PRIMARY KEY (id), 
	CONSTRAINT fk_audit_events_hospital_id_hospitals FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	CONSTRAINT fk_audit_events_actor_staff_id_staff FOREIGN KEY(actor_staff_id) REFERENCES staff (id)
);
