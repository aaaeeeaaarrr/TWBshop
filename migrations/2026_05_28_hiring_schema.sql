--
-- PostgreSQL database dump
--

\restrict QTHSMa9hbFUXCymY0zbtznDiNl5I84we2ioSAlQexFP8xqheaPuGNfujxcoxIcV

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: hiring_answer_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_answer_events (
    id integer NOT NULL,
    answer_id integer,
    event_type text NOT NULL,
    telegram_message_id bigint,
    event_at timestamp with time zone DEFAULT now(),
    payload jsonb,
    CONSTRAINT hiring_answer_events_event_type_check CHECK ((event_type = ANY (ARRAY['question_sent'::text, 'answer_received'::text, 'answer_edited'::text, 'question_deleted'::text, 'timeout'::text, 'skipped'::text])))
);


--
-- Name: hiring_answer_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_answer_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_answer_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_answer_events_id_seq OWNED BY public.hiring_answer_events.id;


--
-- Name: hiring_candidates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_candidates (
    id integer NOT NULL,
    name text NOT NULL,
    candidate_type text DEFAULT 'applicant'::text NOT NULL,
    "position" text,
    quiz_date date,
    score_a integer,
    score_b integer,
    written_pct integer,
    overall_pct integer,
    classification text,
    red_flags jsonb,
    retest_questions jsonb,
    notes text,
    hired boolean,
    created_at timestamp with time zone DEFAULT now(),
    score_source_attempt_id integer,
    score_cache_updated_at timestamp with time zone,
    score_cache_method text,
    CONSTRAINT hiring_candidates_score_cache_method_check CHECK ((score_cache_method = ANY (ARRAY['auto_graded'::text, 'claude_scored'::text, 'human_scored'::text, 'manual_entry'::text])))
);


--
-- Name: hiring_candidates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_candidates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_candidates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_candidates_id_seq OWNED BY public.hiring_candidates.id;


--
-- Name: hiring_coaching_message_points; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_coaching_message_points (
    id integer NOT NULL,
    message_id integer,
    feedback_point_id integer,
    point_order integer NOT NULL
);


--
-- Name: hiring_coaching_message_points_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_coaching_message_points_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_coaching_message_points_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_coaching_message_points_id_seq OWNED BY public.hiring_coaching_message_points.id;


--
-- Name: hiring_coaching_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_coaching_messages (
    id integer NOT NULL,
    candidate_id integer,
    session_id integer,
    sent_at timestamp with time zone DEFAULT now(),
    message_type text,
    total_word_count integer,
    min_required_read_seconds integer,
    read_time_seconds integer,
    confirmation_text text,
    passed_read_check boolean,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT hiring_coaching_messages_message_type_check CHECK ((message_type = ANY (ARRAY['education'::text, 'feedback'::text, 'question'::text, 'confirmation'::text, 'offer'::text, 'warning'::text])))
);


--
-- Name: hiring_coaching_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_coaching_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_coaching_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_coaching_messages_id_seq OWNED BY public.hiring_coaching_messages.id;


--
-- Name: hiring_cv_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_cv_data (
    id integer NOT NULL,
    candidate_id integer,
    raw_cv_file_url text,
    parsed_json jsonb,
    claimed_salary text,
    current_job text,
    availability_summary text,
    date_precision_score integer,
    gap_risk_score integer,
    scoring_method text,
    scored_by text,
    scored_at timestamp with time zone,
    parsed_at timestamp with time zone DEFAULT now(),
    CONSTRAINT hiring_cv_data_date_precision_score_check CHECK (((date_precision_score >= 0) AND (date_precision_score <= 5))),
    CONSTRAINT hiring_cv_data_gap_risk_score_check CHECK (((gap_risk_score >= 0) AND (gap_risk_score <= 5))),
    CONSTRAINT hiring_cv_data_scoring_method_check CHECK ((scoring_method = ANY (ARRAY['rule'::text, 'claude'::text, 'human'::text])))
);


--
-- Name: hiring_cv_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_cv_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_cv_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_cv_data_id_seq OWNED BY public.hiring_cv_data.id;


--
-- Name: hiring_cv_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_cv_jobs (
    id integer NOT NULL,
    candidate_id integer,
    employer_name text,
    job_title text,
    start_date date,
    end_date date,
    start_precision text,
    end_precision text,
    duration_claimed text,
    reason_left text,
    salary_claimed text,
    source_text text,
    stability_score integer,
    red_flag_notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT hiring_cv_jobs_end_precision_check CHECK ((end_precision = ANY (ARRAY['day'::text, 'month'::text, 'year'::text, 'vague'::text, 'missing'::text]))),
    CONSTRAINT hiring_cv_jobs_stability_score_check CHECK (((stability_score >= 0) AND (stability_score <= 5))),
    CONSTRAINT hiring_cv_jobs_start_precision_check CHECK ((start_precision = ANY (ARRAY['day'::text, 'month'::text, 'year'::text, 'vague'::text, 'missing'::text])))
);


--
-- Name: hiring_cv_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_cv_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_cv_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_cv_jobs_id_seq OWNED BY public.hiring_cv_jobs.id;


--
-- Name: hiring_feedback_points; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_feedback_points (
    id integer NOT NULL,
    candidate_id integer,
    quiz_answer_id integer,
    version text DEFAULT 'v1.0'::text,
    source_type text,
    source_ref text,
    answer_summary text,
    trait_detected text,
    severity text,
    principle_tag text,
    evidence_status text DEFAULT 'draft_unlinked'::text,
    specificity_score integer DEFAULT 1,
    contradiction_score integer DEFAULT 0,
    point_number integer,
    english_text text NOT NULL,
    khmer_text text NOT NULL,
    generated_by text,
    reviewed_by text,
    reviewed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    last_updated timestamp with time zone DEFAULT now(),
    CONSTRAINT hiring_feedback_points_contradiction_score_check CHECK (((contradiction_score >= 0) AND (contradiction_score <= 3))),
    CONSTRAINT hiring_feedback_points_evidence_status_check CHECK ((evidence_status = ANY (ARRAY['draft_unlinked'::text, 'linked'::text, 'verified'::text, 'obsolete'::text]))),
    CONSTRAINT hiring_feedback_points_severity_check CHECK ((severity = ANY (ARRAY['strength_high'::text, 'strength_medium'::text, 'gap_minor'::text, 'gap_medium'::text, 'gap_critical'::text, 'risk_critical'::text]))),
    CONSTRAINT hiring_feedback_points_source_type_check CHECK ((source_type = ANY (ARRAY['quiz'::text, 'cv'::text, 'observation'::text, 'trial'::text, 'draft'::text]))),
    CONSTRAINT hiring_feedback_points_specificity_score_check CHECK (((specificity_score >= 0) AND (specificity_score <= 3)))
);


--
-- Name: hiring_feedback_points_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_feedback_points_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_feedback_points_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_feedback_points_id_seq OWNED BY public.hiring_feedback_points.id;


--
-- Name: hiring_feedback_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_feedback_templates (
    id integer NOT NULL,
    candidate_id integer,
    candidate_name text,
    score_range text,
    topic text,
    point_number integer,
    english_text text NOT NULL,
    khmer_text text NOT NULL,
    is_generic boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: hiring_feedback_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_feedback_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_feedback_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_feedback_templates_id_seq OWNED BY public.hiring_feedback_templates.id;


--
-- Name: hiring_observations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_observations (
    id integer NOT NULL,
    candidate_id integer,
    observer_name text,
    observed_at timestamp with time zone DEFAULT now(),
    phase text,
    observation_type text,
    severity text,
    notes text,
    linked_question_id text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT hiring_observations_phase_check CHECK ((phase = ANY (ARRAY['arrival'::text, 'waiting'::text, 'test'::text, 'interview'::text, 'offer'::text, 'first_day'::text, 'trial'::text, 'other'::text]))),
    CONSTRAINT hiring_observations_severity_check CHECK ((severity = ANY (ARRAY['strength'::text, 'neutral'::text, 'minor_gap'::text, 'medium_risk'::text, 'critical_risk'::text])))
);


--
-- Name: hiring_observations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_observations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_observations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_observations_id_seq OWNED BY public.hiring_observations.id;


--
-- Name: hiring_quiz_answers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_quiz_answers (
    id integer NOT NULL,
    attempt_id integer,
    question_id text,
    raw_answer text,
    normalized_answer text,
    is_correct boolean,
    completeness_score integer,
    contradiction_score integer DEFAULT 0,
    time_spent_seconds integer,
    skipped boolean DEFAULT false,
    graded_by text,
    graded_at timestamp with time zone,
    grader_notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT hiring_quiz_answers_completeness_score_check CHECK (((completeness_score >= 0) AND (completeness_score <= 3))),
    CONSTRAINT hiring_quiz_answers_contradiction_score_check CHECK (((contradiction_score >= 0) AND (contradiction_score <= 3)))
);


--
-- Name: hiring_quiz_answers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_quiz_answers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_quiz_answers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_quiz_answers_id_seq OWNED BY public.hiring_quiz_answers.id;


--
-- Name: hiring_quiz_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_quiz_attempts (
    id integer NOT NULL,
    candidate_id integer,
    session_id integer,
    quiz_version_id integer,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    total_duration_seconds integer,
    started_by_staff text,
    interview_location text,
    arrival_status text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT hiring_quiz_attempts_arrival_status_check CHECK ((arrival_status = ANY (ARRAY['on_time'::text, 'late'::text, 'no_show'::text, 'unknown'::text])))
);


--
-- Name: hiring_quiz_attempts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_quiz_attempts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_quiz_attempts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_quiz_attempts_id_seq OWNED BY public.hiring_quiz_attempts.id;


--
-- Name: hiring_quiz_questions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_quiz_questions (
    id text NOT NULL,
    quiz_version_id integer,
    part text NOT NULL,
    section text,
    display_order integer,
    question_text_en text,
    question_text_km text,
    answer_type text NOT NULL,
    options jsonb,
    correct_answer jsonb,
    trait_tags text[],
    severity_if_wrong text,
    requires_verbal_retest boolean DEFAULT false,
    active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT hiring_quiz_questions_answer_type_check CHECK ((answer_type = ANY (ARRAY['yes_no_not_sure'::text, 'single_choice'::text, 'free_text'::text, 'ranking'::text, 'rewrite'::text]))),
    CONSTRAINT hiring_quiz_questions_severity_if_wrong_check CHECK ((severity_if_wrong = ANY (ARRAY['critical'::text, 'moderate'::text, 'minor'::text])))
);


--
-- Name: hiring_quiz_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_quiz_versions (
    id integer NOT NULL,
    version_name text NOT NULL,
    description text,
    active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: hiring_quiz_versions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_quiz_versions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_quiz_versions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_quiz_versions_id_seq OWNED BY public.hiring_quiz_versions.id;


--
-- Name: hiring_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_sessions (
    id integer NOT NULL,
    token_hash text NOT NULL,
    candidate_id integer,
    created_by_staff text,
    telegram_user_id bigint,
    telegram_username text,
    expires_at timestamp with time zone NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    abandoned_at timestamp with time zone,
    abandoned_at_question_id text,
    used_at timestamp with time zone,
    status text DEFAULT 'created'::text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT hiring_sessions_status_check CHECK ((status = ANY (ARRAY['created'::text, 'started'::text, 'completed'::text, 'expired'::text, 'abandoned'::text, 'cancelled'::text])))
);


--
-- Name: hiring_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_sessions_id_seq OWNED BY public.hiring_sessions.id;


--
-- Name: hiring_trial_outcomes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hiring_trial_outcomes (
    id integer NOT NULL,
    candidate_id integer,
    observed_at date,
    day_mark integer,
    observer_name text,
    punctuality text,
    attitude text,
    accuracy text,
    team_behavior text,
    honesty_incidents text,
    instruction_memory text,
    phone_discipline text,
    customer_behavior text,
    overall_rating integer,
    notes text,
    prediction_matched boolean,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT hiring_trial_outcomes_day_mark_check CHECK ((day_mark = ANY (ARRAY[1, 3, 7, 14, 30, 90]))),
    CONSTRAINT hiring_trial_outcomes_overall_rating_check CHECK (((overall_rating >= 1) AND (overall_rating <= 5)))
);


--
-- Name: hiring_trial_outcomes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hiring_trial_outcomes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hiring_trial_outcomes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hiring_trial_outcomes_id_seq OWNED BY public.hiring_trial_outcomes.id;


--
-- Name: hiring_answer_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_answer_events ALTER COLUMN id SET DEFAULT nextval('public.hiring_answer_events_id_seq'::regclass);


--
-- Name: hiring_candidates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_candidates ALTER COLUMN id SET DEFAULT nextval('public.hiring_candidates_id_seq'::regclass);


--
-- Name: hiring_coaching_message_points id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_coaching_message_points ALTER COLUMN id SET DEFAULT nextval('public.hiring_coaching_message_points_id_seq'::regclass);


--
-- Name: hiring_coaching_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_coaching_messages ALTER COLUMN id SET DEFAULT nextval('public.hiring_coaching_messages_id_seq'::regclass);


--
-- Name: hiring_cv_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_cv_data ALTER COLUMN id SET DEFAULT nextval('public.hiring_cv_data_id_seq'::regclass);


--
-- Name: hiring_cv_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_cv_jobs ALTER COLUMN id SET DEFAULT nextval('public.hiring_cv_jobs_id_seq'::regclass);


--
-- Name: hiring_feedback_points id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_feedback_points ALTER COLUMN id SET DEFAULT nextval('public.hiring_feedback_points_id_seq'::regclass);


--
-- Name: hiring_feedback_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_feedback_templates ALTER COLUMN id SET DEFAULT nextval('public.hiring_feedback_templates_id_seq'::regclass);


--
-- Name: hiring_observations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_observations ALTER COLUMN id SET DEFAULT nextval('public.hiring_observations_id_seq'::regclass);


--
-- Name: hiring_quiz_answers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_answers ALTER COLUMN id SET DEFAULT nextval('public.hiring_quiz_answers_id_seq'::regclass);


--
-- Name: hiring_quiz_attempts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_attempts ALTER COLUMN id SET DEFAULT nextval('public.hiring_quiz_attempts_id_seq'::regclass);


--
-- Name: hiring_quiz_versions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_versions ALTER COLUMN id SET DEFAULT nextval('public.hiring_quiz_versions_id_seq'::regclass);


--
-- Name: hiring_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_sessions ALTER COLUMN id SET DEFAULT nextval('public.hiring_sessions_id_seq'::regclass);


--
-- Name: hiring_trial_outcomes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_trial_outcomes ALTER COLUMN id SET DEFAULT nextval('public.hiring_trial_outcomes_id_seq'::regclass);


--
-- Name: hiring_answer_events hiring_answer_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_answer_events
    ADD CONSTRAINT hiring_answer_events_pkey PRIMARY KEY (id);


--
-- Name: hiring_candidates hiring_candidates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_candidates
    ADD CONSTRAINT hiring_candidates_pkey PRIMARY KEY (id);


--
-- Name: hiring_coaching_message_points hiring_coaching_message_points_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_coaching_message_points
    ADD CONSTRAINT hiring_coaching_message_points_pkey PRIMARY KEY (id);


--
-- Name: hiring_coaching_messages hiring_coaching_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_coaching_messages
    ADD CONSTRAINT hiring_coaching_messages_pkey PRIMARY KEY (id);


--
-- Name: hiring_cv_data hiring_cv_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_cv_data
    ADD CONSTRAINT hiring_cv_data_pkey PRIMARY KEY (id);


--
-- Name: hiring_cv_jobs hiring_cv_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_cv_jobs
    ADD CONSTRAINT hiring_cv_jobs_pkey PRIMARY KEY (id);


--
-- Name: hiring_feedback_points hiring_feedback_points_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_feedback_points
    ADD CONSTRAINT hiring_feedback_points_pkey PRIMARY KEY (id);


--
-- Name: hiring_feedback_templates hiring_feedback_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_feedback_templates
    ADD CONSTRAINT hiring_feedback_templates_pkey PRIMARY KEY (id);


--
-- Name: hiring_observations hiring_observations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_observations
    ADD CONSTRAINT hiring_observations_pkey PRIMARY KEY (id);


--
-- Name: hiring_quiz_answers hiring_quiz_answers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_answers
    ADD CONSTRAINT hiring_quiz_answers_pkey PRIMARY KEY (id);


--
-- Name: hiring_quiz_attempts hiring_quiz_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_attempts
    ADD CONSTRAINT hiring_quiz_attempts_pkey PRIMARY KEY (id);


--
-- Name: hiring_quiz_questions hiring_quiz_questions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_questions
    ADD CONSTRAINT hiring_quiz_questions_pkey PRIMARY KEY (id);


--
-- Name: hiring_quiz_versions hiring_quiz_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_versions
    ADD CONSTRAINT hiring_quiz_versions_pkey PRIMARY KEY (id);


--
-- Name: hiring_quiz_versions hiring_quiz_versions_version_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_versions
    ADD CONSTRAINT hiring_quiz_versions_version_name_key UNIQUE (version_name);


--
-- Name: hiring_sessions hiring_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_sessions
    ADD CONSTRAINT hiring_sessions_pkey PRIMARY KEY (id);


--
-- Name: hiring_sessions hiring_sessions_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_sessions
    ADD CONSTRAINT hiring_sessions_token_hash_key UNIQUE (token_hash);


--
-- Name: hiring_trial_outcomes hiring_trial_outcomes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_trial_outcomes
    ADD CONSTRAINT hiring_trial_outcomes_pkey PRIMARY KEY (id);


--
-- Name: hiring_answer_events hiring_answer_events_answer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_answer_events
    ADD CONSTRAINT hiring_answer_events_answer_id_fkey FOREIGN KEY (answer_id) REFERENCES public.hiring_quiz_answers(id);


--
-- Name: hiring_candidates hiring_candidates_score_source_attempt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_candidates
    ADD CONSTRAINT hiring_candidates_score_source_attempt_id_fkey FOREIGN KEY (score_source_attempt_id) REFERENCES public.hiring_quiz_attempts(id);


--
-- Name: hiring_coaching_message_points hiring_coaching_message_points_feedback_point_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_coaching_message_points
    ADD CONSTRAINT hiring_coaching_message_points_feedback_point_id_fkey FOREIGN KEY (feedback_point_id) REFERENCES public.hiring_feedback_points(id);


--
-- Name: hiring_coaching_message_points hiring_coaching_message_points_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_coaching_message_points
    ADD CONSTRAINT hiring_coaching_message_points_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.hiring_coaching_messages(id) ON DELETE CASCADE;


--
-- Name: hiring_coaching_messages hiring_coaching_messages_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_coaching_messages
    ADD CONSTRAINT hiring_coaching_messages_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.hiring_candidates(id);


--
-- Name: hiring_coaching_messages hiring_coaching_messages_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_coaching_messages
    ADD CONSTRAINT hiring_coaching_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.hiring_sessions(id);


--
-- Name: hiring_cv_data hiring_cv_data_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_cv_data
    ADD CONSTRAINT hiring_cv_data_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.hiring_candidates(id);


--
-- Name: hiring_cv_jobs hiring_cv_jobs_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_cv_jobs
    ADD CONSTRAINT hiring_cv_jobs_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.hiring_candidates(id);


--
-- Name: hiring_feedback_points hiring_feedback_points_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_feedback_points
    ADD CONSTRAINT hiring_feedback_points_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.hiring_candidates(id);


--
-- Name: hiring_feedback_points hiring_feedback_points_quiz_answer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_feedback_points
    ADD CONSTRAINT hiring_feedback_points_quiz_answer_id_fkey FOREIGN KEY (quiz_answer_id) REFERENCES public.hiring_quiz_answers(id);


--
-- Name: hiring_feedback_templates hiring_feedback_templates_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_feedback_templates
    ADD CONSTRAINT hiring_feedback_templates_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.hiring_candidates(id);


--
-- Name: hiring_observations hiring_observations_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_observations
    ADD CONSTRAINT hiring_observations_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.hiring_candidates(id);


--
-- Name: hiring_observations hiring_observations_linked_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_observations
    ADD CONSTRAINT hiring_observations_linked_question_id_fkey FOREIGN KEY (linked_question_id) REFERENCES public.hiring_quiz_questions(id);


--
-- Name: hiring_quiz_answers hiring_quiz_answers_attempt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_answers
    ADD CONSTRAINT hiring_quiz_answers_attempt_id_fkey FOREIGN KEY (attempt_id) REFERENCES public.hiring_quiz_attempts(id);


--
-- Name: hiring_quiz_answers hiring_quiz_answers_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_answers
    ADD CONSTRAINT hiring_quiz_answers_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.hiring_quiz_questions(id);


--
-- Name: hiring_quiz_attempts hiring_quiz_attempts_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_attempts
    ADD CONSTRAINT hiring_quiz_attempts_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.hiring_candidates(id);


--
-- Name: hiring_quiz_attempts hiring_quiz_attempts_quiz_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_attempts
    ADD CONSTRAINT hiring_quiz_attempts_quiz_version_id_fkey FOREIGN KEY (quiz_version_id) REFERENCES public.hiring_quiz_versions(id);


--
-- Name: hiring_quiz_attempts hiring_quiz_attempts_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_attempts
    ADD CONSTRAINT hiring_quiz_attempts_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.hiring_sessions(id);


--
-- Name: hiring_quiz_questions hiring_quiz_questions_quiz_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_quiz_questions
    ADD CONSTRAINT hiring_quiz_questions_quiz_version_id_fkey FOREIGN KEY (quiz_version_id) REFERENCES public.hiring_quiz_versions(id);


--
-- Name: hiring_sessions hiring_sessions_abandoned_at_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_sessions
    ADD CONSTRAINT hiring_sessions_abandoned_at_question_id_fkey FOREIGN KEY (abandoned_at_question_id) REFERENCES public.hiring_quiz_questions(id);


--
-- Name: hiring_sessions hiring_sessions_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_sessions
    ADD CONSTRAINT hiring_sessions_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.hiring_candidates(id);


--
-- Name: hiring_trial_outcomes hiring_trial_outcomes_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hiring_trial_outcomes
    ADD CONSTRAINT hiring_trial_outcomes_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.hiring_candidates(id);


--
-- PostgreSQL database dump complete
--

\unrestrict QTHSMa9hbFUXCymY0zbtznDiNl5I84we2ioSAlQexFP8xqheaPuGNfujxcoxIcV

