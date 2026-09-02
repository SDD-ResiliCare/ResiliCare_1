-- Migration 009: Add dedicated ml_output column to triage_assessments table
-- Stores probabilistic multi-class distribution, TreeSHAP feature attributions, and clinical rationale.

ALTER TABLE triage_assessments ADD COLUMN IF NOT EXISTS ml_output JSONB;
