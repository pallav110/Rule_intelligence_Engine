--
-- PostgreSQL database dump
--

\restrict ERD4TPYAvtGbAM8O8roge9CAVcvbFN7eYSs2YndKciQ1Fqmp0zaD8ntCcEQzGU3

-- Dumped from database version 18.6 (Debian 18.6-1.pgdg12+2)
-- Dumped by pg_dump version 18.6 (Debian 18.6-1.pgdg12+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: analysis_runs; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.analysis_runs (
    analysis_run_id character varying(50) NOT NULL,
    feedback_id character varying(50) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    model_version_id character varying(100),
    dataset_version_id character varying(100),
    taxonomy_version character varying(50),
    domain_pack_id character varying(50),
    threshold_configuration json,
    processing_mode character varying(30) NOT NULL,
    status character varying(30) NOT NULL,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.analysis_runs OWNER TO rie_user;

--
-- Name: audit_history; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.audit_history (
    audit_id character varying(50) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    actor_id character varying(100),
    action character varying(100) NOT NULL,
    entity_type character varying(100) NOT NULL,
    entity_id character varying(100) NOT NULL,
    details json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.audit_history OWNER TO rie_user;

--
-- Name: background_jobs; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.background_jobs (
    job_id character varying(100) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    job_type character varying(50) NOT NULL,
    status character varying(30) NOT NULL,
    progress integer NOT NULL,
    idempotency_key character varying(100) NOT NULL,
    created_at timestamp without time zone NOT NULL,
    completed_at timestamp without time zone
);


ALTER TABLE public.background_jobs OWNER TO rie_user;

--
-- Name: clarifications; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.clarifications (
    clarification_id character varying(50) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    suggestion_id character varying(50),
    feedback_id character varying(50),
    analysis_run_id character varying(50),
    clarification_question text NOT NULL,
    questions json,
    reason text,
    clarification_response text,
    responded_by character varying(100),
    responded_at timestamp without time zone,
    processing_status character varying(30) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.clarifications OWNER TO rie_user;

--
-- Name: dataset_versions; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.dataset_versions (
    dataset_version_id character varying(100) NOT NULL,
    dataset_name character varying(100) NOT NULL,
    version character varying(50) NOT NULL,
    description text,
    num_samples integer,
    domain_pack_id character varying(50),
    domain_pack_version character varying(50) NOT NULL,
    annotation_version character varying(50) NOT NULL,
    source character varying(50) NOT NULL,
    path character varying(255) NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.dataset_versions OWNER TO rie_user;

--
-- Name: domain_packs; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.domain_packs (
    pack_id character varying(50) NOT NULL,
    workspace_id character varying(50),
    name character varying(100) NOT NULL,
    version character varying(50) NOT NULL,
    schema_metadata json,
    business_glossary json,
    configuration json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.domain_packs OWNER TO rie_user;

--
-- Name: evaluation_metrics; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.evaluation_metrics (
    metric_id character varying(100) NOT NULL,
    evaluation_run_id character varying(100) NOT NULL,
    metric_name character varying(100) NOT NULL,
    metric_value double precision NOT NULL,
    metric_details json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.evaluation_metrics OWNER TO rie_user;

--
-- Name: evaluation_runs; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.evaluation_runs (
    evaluation_run_id character varying(100) NOT NULL,
    model_version_id character varying(100) NOT NULL,
    dataset_version_id character varying(100) NOT NULL,
    domain_pack_id character varying(50),
    status character varying(30) NOT NULL,
    classification_accuracy double precision,
    classification_f1 json,
    complete_rule_accuracy double precision,
    duplicate_f1 double precision,
    conflict_f1 double precision,
    calibration_error double precision,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.evaluation_runs OWNER TO rie_user;

--
-- Name: extracted_rules; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.extracted_rules (
    extracted_rule_id character varying(50) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    feedback_id character varying(50) NOT NULL,
    analysis_run_id character varying(50) NOT NULL,
    suggestion_id character varying(50),
    rule_family_id character varying(100),
    business_term character varying(255),
    operation character varying(100),
    conditions json,
    scope json,
    time_window json,
    affected_tables json,
    affected_columns json,
    extraction_confidence double precision,
    schema_validation_status character varying(30),
    rule_data json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.extracted_rules OWNER TO rie_user;

--
-- Name: feedback; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.feedback (
    feedback_id character varying(50) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    feedback_text text NOT NULL,
    submitted_by character varying(100),
    processing_status character varying(30) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.feedback OWNER TO rie_user;

--
-- Name: model_versions; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.model_versions (
    model_version_id character varying(100) NOT NULL,
    model_name character varying(100) NOT NULL,
    version character varying(50) NOT NULL,
    description text,
    artifact_path character varying(255) NOT NULL,
    dataset_version_id character varying(100),
    status character varying(20) NOT NULL,
    metrics json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.model_versions OWNER TO rie_user;

--
-- Name: reviews; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.reviews (
    review_id character varying(50) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    suggestion_id character varying(50) NOT NULL,
    reviewer_id character varying(100),
    status character varying(30) NOT NULL,
    priority character varying(30) NOT NULL,
    decision character varying(30),
    notes text,
    assigned_at timestamp without time zone NOT NULL,
    completed_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.reviews OWNER TO rie_user;

--
-- Name: rule_comparisons; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.rule_comparisons (
    comparison_id character varying(50) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    extracted_rule_id character varying(50),
    suggestion_id character varying(50),
    comparison_type character varying(30) NOT NULL,
    relationship character varying(50) NOT NULL,
    compared_rule_id character varying(50),
    matching_rule_id character varying(50),
    conflicting_rule_id character varying(50),
    confidence double precision,
    details json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.rule_comparisons OWNER TO rie_user;

--
-- Name: rule_embeddings; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.rule_embeddings (
    embedding_id character varying(50) NOT NULL,
    rule_id character varying(50) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    embedding public.vector(384) NOT NULL,
    embedding_model character varying(100) NOT NULL,
    embedding_dimension integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.rule_embeddings OWNER TO rie_user;

--
-- Name: rule_suggestions; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.rule_suggestions (
    suggestion_id character varying(50) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    feedback_id character varying(50) NOT NULL,
    analysis_run_id character varying(50) NOT NULL,
    feedback_type character varying(100),
    rule_category character varying(100),
    classification_result json,
    extraction_result character varying(30),
    schema_validation_status character varying(30),
    duplicate_status character varying(50),
    conflict_status character varying(50),
    clarification_required boolean NOT NULL,
    review_status character varying(30) NOT NULL,
    suggested_rule json,
    created_at timestamp without time zone NOT NULL,
    preprocessing_result jsonb
);


ALTER TABLE public.rule_suggestions OWNER TO rie_user;

--
-- Name: rules; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.rules (
    rule_id character varying(50) NOT NULL,
    workspace_id character varying(50) NOT NULL,
    domain_id character varying(100),
    suggestion_id character varying(50),
    rule_name character varying(255),
    business_term character varying(255),
    rule_category character varying(100) NOT NULL,
    operation character varying(50) NOT NULL,
    conditions json NOT NULL,
    scope json,
    threshold json,
    time_window json,
    affected_tables json NOT NULL,
    affected_columns json NOT NULL,
    affected_entities json NOT NULL,
    rule_definition json,
    status character varying(20) NOT NULL,
    activated_by character varying(100),
    activated_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.rules OWNER TO rie_user;

--
-- Name: suggestion_audit; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.suggestion_audit (
    audit_id character varying(50) NOT NULL,
    suggestion_id character varying(50) NOT NULL,
    from_status character varying(50) NOT NULL,
    to_status character varying(50) NOT NULL,
    transitioned_by character varying(100) NOT NULL,
    transition_reason character varying(500),
    audit_metadata json NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.suggestion_audit OWNER TO rie_user;

--
-- Name: workspaces; Type: TABLE; Schema: public; Owner: rie_user
--

CREATE TABLE public.workspaces (
    workspace_id character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    status character varying(30) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.workspaces OWNER TO rie_user;

--
-- Name: analysis_runs analysis_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.analysis_runs
    ADD CONSTRAINT analysis_runs_pkey PRIMARY KEY (analysis_run_id);


--
-- Name: audit_history audit_history_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.audit_history
    ADD CONSTRAINT audit_history_pkey PRIMARY KEY (audit_id);


--
-- Name: background_jobs background_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.background_jobs
    ADD CONSTRAINT background_jobs_pkey PRIMARY KEY (job_id);


--
-- Name: clarifications clarifications_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.clarifications
    ADD CONSTRAINT clarifications_pkey PRIMARY KEY (clarification_id);


--
-- Name: dataset_versions dataset_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.dataset_versions
    ADD CONSTRAINT dataset_versions_pkey PRIMARY KEY (dataset_version_id);


--
-- Name: domain_packs domain_packs_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.domain_packs
    ADD CONSTRAINT domain_packs_pkey PRIMARY KEY (pack_id);


--
-- Name: evaluation_metrics evaluation_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.evaluation_metrics
    ADD CONSTRAINT evaluation_metrics_pkey PRIMARY KEY (metric_id);


--
-- Name: evaluation_runs evaluation_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.evaluation_runs
    ADD CONSTRAINT evaluation_runs_pkey PRIMARY KEY (evaluation_run_id);


--
-- Name: extracted_rules extracted_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.extracted_rules
    ADD CONSTRAINT extracted_rules_pkey PRIMARY KEY (extracted_rule_id);


--
-- Name: feedback feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.feedback
    ADD CONSTRAINT feedback_pkey PRIMARY KEY (feedback_id);


--
-- Name: model_versions model_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.model_versions
    ADD CONSTRAINT model_versions_pkey PRIMARY KEY (model_version_id);


--
-- Name: reviews reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_pkey PRIMARY KEY (review_id);


--
-- Name: rule_comparisons rule_comparisons_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_comparisons
    ADD CONSTRAINT rule_comparisons_pkey PRIMARY KEY (comparison_id);


--
-- Name: rule_embeddings rule_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_embeddings
    ADD CONSTRAINT rule_embeddings_pkey PRIMARY KEY (embedding_id);


--
-- Name: rule_suggestions rule_suggestions_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_suggestions
    ADD CONSTRAINT rule_suggestions_pkey PRIMARY KEY (suggestion_id);


--
-- Name: rules rules_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rules
    ADD CONSTRAINT rules_pkey PRIMARY KEY (rule_id);


--
-- Name: suggestion_audit suggestion_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.suggestion_audit
    ADD CONSTRAINT suggestion_audit_pkey PRIMARY KEY (audit_id);


--
-- Name: background_jobs uq_background_jobs_workspace_idempotency; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.background_jobs
    ADD CONSTRAINT uq_background_jobs_workspace_idempotency UNIQUE (workspace_id, idempotency_key);


--
-- Name: dataset_versions uq_dataset_versions_name_version; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.dataset_versions
    ADD CONSTRAINT uq_dataset_versions_name_version UNIQUE (dataset_name, version);


--
-- Name: model_versions uq_model_versions_name_version; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.model_versions
    ADD CONSTRAINT uq_model_versions_name_version UNIQUE (model_name, version);


--
-- Name: workspaces workspaces_pkey; Type: CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_pkey PRIMARY KEY (workspace_id);


--
-- Name: ix_rule_embeddings_rule_id; Type: INDEX; Schema: public; Owner: rie_user
--

CREATE INDEX ix_rule_embeddings_rule_id ON public.rule_embeddings USING btree (rule_id);


--
-- Name: ix_rule_embeddings_workspace_id; Type: INDEX; Schema: public; Owner: rie_user
--

CREATE INDEX ix_rule_embeddings_workspace_id ON public.rule_embeddings USING btree (workspace_id);


--
-- Name: ix_suggestion_audit_suggestion_id; Type: INDEX; Schema: public; Owner: rie_user
--

CREATE INDEX ix_suggestion_audit_suggestion_id ON public.suggestion_audit USING btree (suggestion_id);


--
-- Name: analysis_runs analysis_runs_dataset_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.analysis_runs
    ADD CONSTRAINT analysis_runs_dataset_version_id_fkey FOREIGN KEY (dataset_version_id) REFERENCES public.dataset_versions(dataset_version_id);


--
-- Name: analysis_runs analysis_runs_domain_pack_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.analysis_runs
    ADD CONSTRAINT analysis_runs_domain_pack_id_fkey FOREIGN KEY (domain_pack_id) REFERENCES public.domain_packs(pack_id);


--
-- Name: analysis_runs analysis_runs_feedback_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.analysis_runs
    ADD CONSTRAINT analysis_runs_feedback_id_fkey FOREIGN KEY (feedback_id) REFERENCES public.feedback(feedback_id);


--
-- Name: analysis_runs analysis_runs_model_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.analysis_runs
    ADD CONSTRAINT analysis_runs_model_version_id_fkey FOREIGN KEY (model_version_id) REFERENCES public.model_versions(model_version_id);


--
-- Name: analysis_runs analysis_runs_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.analysis_runs
    ADD CONSTRAINT analysis_runs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: audit_history audit_history_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.audit_history
    ADD CONSTRAINT audit_history_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: background_jobs background_jobs_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.background_jobs
    ADD CONSTRAINT background_jobs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: clarifications clarifications_analysis_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.clarifications
    ADD CONSTRAINT clarifications_analysis_run_id_fkey FOREIGN KEY (analysis_run_id) REFERENCES public.analysis_runs(analysis_run_id);


--
-- Name: clarifications clarifications_feedback_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.clarifications
    ADD CONSTRAINT clarifications_feedback_id_fkey FOREIGN KEY (feedback_id) REFERENCES public.feedback(feedback_id);


--
-- Name: clarifications clarifications_suggestion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.clarifications
    ADD CONSTRAINT clarifications_suggestion_id_fkey FOREIGN KEY (suggestion_id) REFERENCES public.rule_suggestions(suggestion_id);


--
-- Name: clarifications clarifications_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.clarifications
    ADD CONSTRAINT clarifications_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: dataset_versions dataset_versions_domain_pack_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.dataset_versions
    ADD CONSTRAINT dataset_versions_domain_pack_id_fkey FOREIGN KEY (domain_pack_id) REFERENCES public.domain_packs(pack_id);


--
-- Name: domain_packs domain_packs_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.domain_packs
    ADD CONSTRAINT domain_packs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: evaluation_metrics evaluation_metrics_evaluation_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.evaluation_metrics
    ADD CONSTRAINT evaluation_metrics_evaluation_run_id_fkey FOREIGN KEY (evaluation_run_id) REFERENCES public.evaluation_runs(evaluation_run_id);


--
-- Name: evaluation_runs evaluation_runs_dataset_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.evaluation_runs
    ADD CONSTRAINT evaluation_runs_dataset_version_id_fkey FOREIGN KEY (dataset_version_id) REFERENCES public.dataset_versions(dataset_version_id);


--
-- Name: evaluation_runs evaluation_runs_domain_pack_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.evaluation_runs
    ADD CONSTRAINT evaluation_runs_domain_pack_id_fkey FOREIGN KEY (domain_pack_id) REFERENCES public.domain_packs(pack_id);


--
-- Name: evaluation_runs evaluation_runs_model_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.evaluation_runs
    ADD CONSTRAINT evaluation_runs_model_version_id_fkey FOREIGN KEY (model_version_id) REFERENCES public.model_versions(model_version_id);


--
-- Name: extracted_rules extracted_rules_analysis_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.extracted_rules
    ADD CONSTRAINT extracted_rules_analysis_run_id_fkey FOREIGN KEY (analysis_run_id) REFERENCES public.analysis_runs(analysis_run_id);


--
-- Name: extracted_rules extracted_rules_feedback_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.extracted_rules
    ADD CONSTRAINT extracted_rules_feedback_id_fkey FOREIGN KEY (feedback_id) REFERENCES public.feedback(feedback_id);


--
-- Name: extracted_rules extracted_rules_suggestion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.extracted_rules
    ADD CONSTRAINT extracted_rules_suggestion_id_fkey FOREIGN KEY (suggestion_id) REFERENCES public.rule_suggestions(suggestion_id);


--
-- Name: extracted_rules extracted_rules_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.extracted_rules
    ADD CONSTRAINT extracted_rules_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: feedback feedback_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.feedback
    ADD CONSTRAINT feedback_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: model_versions model_versions_dataset_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.model_versions
    ADD CONSTRAINT model_versions_dataset_version_id_fkey FOREIGN KEY (dataset_version_id) REFERENCES public.dataset_versions(dataset_version_id);


--
-- Name: reviews reviews_suggestion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_suggestion_id_fkey FOREIGN KEY (suggestion_id) REFERENCES public.rule_suggestions(suggestion_id);


--
-- Name: reviews reviews_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: rule_comparisons rule_comparisons_compared_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_comparisons
    ADD CONSTRAINT rule_comparisons_compared_rule_id_fkey FOREIGN KEY (compared_rule_id) REFERENCES public.rules(rule_id);


--
-- Name: rule_comparisons rule_comparisons_conflicting_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_comparisons
    ADD CONSTRAINT rule_comparisons_conflicting_rule_id_fkey FOREIGN KEY (conflicting_rule_id) REFERENCES public.rules(rule_id);


--
-- Name: rule_comparisons rule_comparisons_extracted_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_comparisons
    ADD CONSTRAINT rule_comparisons_extracted_rule_id_fkey FOREIGN KEY (extracted_rule_id) REFERENCES public.extracted_rules(extracted_rule_id);


--
-- Name: rule_comparisons rule_comparisons_matching_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_comparisons
    ADD CONSTRAINT rule_comparisons_matching_rule_id_fkey FOREIGN KEY (matching_rule_id) REFERENCES public.rules(rule_id);


--
-- Name: rule_comparisons rule_comparisons_suggestion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_comparisons
    ADD CONSTRAINT rule_comparisons_suggestion_id_fkey FOREIGN KEY (suggestion_id) REFERENCES public.rule_suggestions(suggestion_id);


--
-- Name: rule_comparisons rule_comparisons_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_comparisons
    ADD CONSTRAINT rule_comparisons_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: rule_embeddings rule_embeddings_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_embeddings
    ADD CONSTRAINT rule_embeddings_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.rules(rule_id) ON DELETE CASCADE;


--
-- Name: rule_embeddings rule_embeddings_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_embeddings
    ADD CONSTRAINT rule_embeddings_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id) ON DELETE CASCADE;


--
-- Name: rule_suggestions rule_suggestions_analysis_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_suggestions
    ADD CONSTRAINT rule_suggestions_analysis_run_id_fkey FOREIGN KEY (analysis_run_id) REFERENCES public.analysis_runs(analysis_run_id);


--
-- Name: rule_suggestions rule_suggestions_feedback_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_suggestions
    ADD CONSTRAINT rule_suggestions_feedback_id_fkey FOREIGN KEY (feedback_id) REFERENCES public.feedback(feedback_id);


--
-- Name: rule_suggestions rule_suggestions_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rule_suggestions
    ADD CONSTRAINT rule_suggestions_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: rules rules_suggestion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rules
    ADD CONSTRAINT rules_suggestion_id_fkey FOREIGN KEY (suggestion_id) REFERENCES public.rule_suggestions(suggestion_id);


--
-- Name: rules rules_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.rules
    ADD CONSTRAINT rules_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(workspace_id);


--
-- Name: suggestion_audit suggestion_audit_suggestion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: rie_user
--

ALTER TABLE ONLY public.suggestion_audit
    ADD CONSTRAINT suggestion_audit_suggestion_id_fkey FOREIGN KEY (suggestion_id) REFERENCES public.rule_suggestions(suggestion_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict ERD4TPYAvtGbAM8O8roge9CAVcvbFN7eYSs2YndKciQ1Fqmp0zaD8ntCcEQzGU3

