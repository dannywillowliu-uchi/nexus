-- 001_initial.sql
-- Initial Nexus database schema for Supabase (PostgreSQL + RLS)

-- Profiles (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS profiles (
	id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
	email TEXT NOT NULL,
	full_name TEXT,
	avatar_url TEXT,
	role TEXT NOT NULL DEFAULT 'user',
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
	ON profiles FOR SELECT
	USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
	ON profiles FOR UPDATE
	USING (auth.uid() = id);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
	query TEXT NOT NULL,
	disease_area TEXT NOT NULL,
	start_entity TEXT NOT NULL,
	start_type TEXT NOT NULL,
	target_types TEXT[] NOT NULL DEFAULT '{}',
	status TEXT NOT NULL DEFAULT 'pending',
	pipeline_step TEXT NOT NULL DEFAULT 'init',
	reasoning_depth TEXT NOT NULL DEFAULT 'quick',
	max_hypotheses INT NOT NULL DEFAULT 10,
	max_pivots INT NOT NULL DEFAULT 3,
	max_hops INT NOT NULL DEFAULT 2,
	pivot_count INT NOT NULL DEFAULT 0,
	branch_count INT NOT NULL DEFAULT 0,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own sessions"
	ON sessions FOR SELECT
	USING (auth.uid() = user_id);

CREATE POLICY "Users can create sessions"
	ON sessions FOR INSERT
	WITH CHECK (auth.uid() = user_id);

-- Hypotheses
CREATE TABLE IF NOT EXISTS hypotheses (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
	title TEXT NOT NULL,
	description TEXT NOT NULL,
	disease_area TEXT NOT NULL,
	hypothesis_type TEXT NOT NULL,
	novelty_score DOUBLE PRECISION NOT NULL DEFAULT 0,
	evidence_score DOUBLE PRECISION NOT NULL DEFAULT 0,
	validation_score DOUBLE PRECISION,
	overall_score DOUBLE PRECISION NOT NULL DEFAULT 0,
	abc_path JSONB NOT NULL DEFAULT '{}',
	evidence_chain JSONB NOT NULL DEFAULT '[]',
	research_brief JSONB,
	validation_result JSONB,
	visualization_url TEXT,
	is_public BOOLEAN NOT NULL DEFAULT false,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE hypotheses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own hypotheses"
	ON hypotheses FOR SELECT
	USING (
		EXISTS (
			SELECT 1 FROM sessions s
			WHERE s.id = hypotheses.session_id AND s.user_id = auth.uid()
		)
	);

CREATE POLICY "Public hypotheses are viewable by all"
	ON hypotheses FOR SELECT
	USING (is_public = true);

CREATE POLICY "Users can create hypotheses for own sessions"
	ON hypotheses FOR INSERT
	WITH CHECK (
		EXISTS (
			SELECT 1 FROM sessions s
			WHERE s.id = hypotheses.session_id AND s.user_id = auth.uid()
		)
	);

-- Feed entries
CREATE TABLE IF NOT EXISTS feed_entries (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
	disease_area TEXT NOT NULL,
	published_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE feed_entries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Feed entries are public"
	ON feed_entries FOR SELECT
	USING (true);

-- Subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
	disease_area TEXT NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	UNIQUE(user_id, disease_area)
);

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own subscriptions"
	ON subscriptions FOR SELECT
	USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own subscriptions"
	ON subscriptions FOR INSERT
	WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own subscriptions"
	ON subscriptions FOR DELETE
	USING (auth.uid() = user_id);

-- Experiments
CREATE TABLE IF NOT EXISTS experiments (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
	provider TEXT NOT NULL DEFAULT 'strateos',
	status TEXT NOT NULL DEFAULT 'pending',
	protocol JSONB,
	result JSONB,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE experiments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own experiments"
	ON experiments FOR SELECT
	USING (
		EXISTS (
			SELECT 1 FROM hypotheses h
			JOIN sessions s ON s.id = h.session_id
			WHERE h.id = experiments.hypothesis_id AND s.user_id = auth.uid()
		)
	);

CREATE POLICY "Users can create experiments for own hypotheses"
	ON experiments FOR INSERT
	WITH CHECK (
		EXISTS (
			SELECT 1 FROM hypotheses h
			JOIN sessions s ON s.id = h.session_id
			WHERE h.id = experiments.hypothesis_id AND s.user_id = auth.uid()
		)
	);

-- Session events (audit log)
CREATE TABLE IF NOT EXISTS session_events (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
	event_type TEXT NOT NULL,
	payload JSONB NOT NULL DEFAULT '{}',
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE session_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own session events"
	ON session_events FOR SELECT
	USING (
		EXISTS (
			SELECT 1 FROM sessions s
			WHERE s.id = session_events.session_id AND s.user_id = auth.uid()
		)
	);

-- API keys
CREATE TABLE IF NOT EXISTS api_keys (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
	name TEXT NOT NULL,
	key_hash TEXT NOT NULL,
	last_used_at TIMESTAMPTZ,
	expires_at TIMESTAMPTZ,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own API keys"
	ON api_keys FOR SELECT
	USING (auth.uid() = user_id);

CREATE POLICY "Users can create own API keys"
	ON api_keys FOR INSERT
	WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own API keys"
	ON api_keys FOR DELETE
	USING (auth.uid() = user_id);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_hypotheses_session_id ON hypotheses(session_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_disease_area ON hypotheses(disease_area);
CREATE INDEX IF NOT EXISTS idx_hypotheses_is_public ON hypotheses(is_public);
CREATE INDEX IF NOT EXISTS idx_hypotheses_overall_score ON hypotheses(overall_score DESC);
CREATE INDEX IF NOT EXISTS idx_feed_entries_disease_area ON feed_entries(disease_area);
CREATE INDEX IF NOT EXISTS idx_feed_entries_published_at ON feed_entries(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_experiments_hypothesis_id ON experiments(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_session_events_session_id ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
