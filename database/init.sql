-- Drop existing tables (recreate)
DROP TABLE IF EXISTS rule_comparisons CASCADE;
DROP TABLE IF EXISTS domain_packs CASCADE;
DROP TABLE IF EXISTS rules CASCADE;
DROP TABLE IF EXISTS clarifications CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS rule_suggestions CASCADE;
DROP TABLE IF EXISTS analysis_runs CASCADE;
DROP TABLE IF EXISTS feedback CASCADE;
DROP TABLE IF EXISTS dataset_versions CASCADE;
DROP TABLE IF EXISTS model_versions CASCADE;
DROP TABLE IF EXISTS workspaces CASCADE;

-- Create workspaces table
CREATE TABLE workspaces (
    workspace_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create feedback table
CREATE TABLE feedback (
    feedback_id VARCHAR(50) PRIMARY KEY,
    workspace_id VARCHAR(50) NOT NULL REFERENCES workspaces(workspace_id),
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create model_versions table
CREATE TABLE model_versions (
    model_version_id VARCHAR(50) PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    version_number VARCHAR(50) NOT NULL,
    model_path VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create dataset_versions table
CREATE TABLE dataset_versions (
    dataset_version_id VARCHAR(50) PRIMARY KEY,
    version_number VARCHAR(50) NOT NULL,
    record_count INT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create domain_packs table
CREATE TABLE domain_packs (
    pack_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    content JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create analysis_runs table
CREATE TABLE analysis_runs (
    analysis_run_id VARCHAR(50) PRIMARY KEY,
    feedback_id VARCHAR(50) NOT NULL REFERENCES feedback(feedback_id),
    workspace_id VARCHAR(50) NOT NULL REFERENCES workspaces(workspace_id),
    model_version_id VARCHAR(50),
    dataset_version_id VARCHAR(50),
    taxonomy_version VARCHAR(50),
    domain_pack_id VARCHAR(50),
    processing_mode VARCHAR(30) NOT NULL DEFAULT 'single',
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create rule_suggestions table
CREATE TABLE rule_suggestions (
    suggestion_id VARCHAR(50) PRIMARY KEY,
    workspace_id VARCHAR(50) NOT NULL REFERENCES workspaces(workspace_id),
    feedback_id VARCHAR(50) NOT NULL REFERENCES feedback(feedback_id),
    analysis_run_id VARCHAR(50) NOT NULL REFERENCES analysis_runs(analysis_run_id),
    feedback_type VARCHAR(100),
    rule_category VARCHAR(100),
    classification_result JSONB,
    extraction_result VARCHAR(30),
    schema_validation_status VARCHAR(30),
    duplicate_status VARCHAR(50),
    conflict_status VARCHAR(50),
    clarification_required BOOLEAN NOT NULL DEFAULT FALSE,
    review_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    suggested_rule JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create reviews table
CREATE TABLE reviews (
    review_id VARCHAR(50) PRIMARY KEY,
    suggestion_id VARCHAR(50) NOT NULL REFERENCES rule_suggestions(suggestion_id),
    reviewer_id VARCHAR(50),
    status VARCHAR(30) NOT NULL DEFAULT 'assigned',
    priority VARCHAR(30) DEFAULT 'normal',
    decision VARCHAR(50),
    notes TEXT,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create clarifications table
CREATE TABLE clarifications (
    clarification_id VARCHAR(50) PRIMARY KEY,
    feedback_id VARCHAR(50) NOT NULL REFERENCES feedback(feedback_id),
    questions JSONB,
    reason TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    response TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP
);

-- Create rules table
CREATE TABLE rules (
    rule_id VARCHAR(50) PRIMARY KEY,
    workspace_id VARCHAR(50) NOT NULL REFERENCES workspaces(workspace_id),
    suggestion_id VARCHAR(50) REFERENCES rule_suggestions(suggestion_id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    business_term VARCHAR(255),
    operation VARCHAR(50),
    conditions JSONB,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create rule_comparisons table
CREATE TABLE rule_comparisons (
    comparison_id VARCHAR(50) PRIMARY KEY,
    rule_a_id VARCHAR(50),
    rule_b_id VARCHAR(50),
    relationship VARCHAR(50),
    confidence FLOAT,
    details JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Insert default workspace
INSERT INTO workspaces (workspace_id, name, description, status) 
VALUES ('default', 'Default Workspace', 'Default workspace for testing', 'active') 
ON CONFLICT (workspace_id) DO NOTHING;
