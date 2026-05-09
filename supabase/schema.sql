-- ============================================================================
-- TILLU Backend - Complete Supabase Schema
-- Real Architecture. Real Intelligence. Always Running.
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- User Profile: Living user model with personality parameters
CREATE TABLE IF NOT EXISTS user_profile (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE,
    email TEXT,
    name TEXT,
    timezone TEXT DEFAULT 'UTC',
    active_hours_start TIME DEFAULT '08:00:00',
    active_hours_end TIME DEFAULT '22:00:00',
    dnd_enabled BOOLEAN DEFAULT FALSE,
    dnd_start TIME DEFAULT '22:00:00',
    dnd_end TIME DEFAULT '08:00:00',
    interests JSONB DEFAULT '[]',
    behavioral_patterns JSONB DEFAULT '{}',
    personality_params JSONB DEFAULT '{
        "base": {
            "temperature": 0.75,
            "sarcasm": 0.70,
            "warmth": 0.65,
            "directness": 0.80,
            "humor_frequency": 0.55,
            "challenge_style": 0.70,
            "detail_level": 0.60,
            "proactivity_threshold": 6
        },
        "time_modifiers": {},
        "stress_modifiers": {},
        "topic_modifiers": {},
        "meta": {
            "last_evolved": null,
            "evolution_count": 0,
            "confidence": 0.78,
            "adaptation_version": 1
        }
    }',
    preference_history JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Interactions: Full log of every interaction with quality scores
CREATE TABLE IF NOT EXISTS interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    session_id UUID,
    interaction_type TEXT NOT NULL, -- text, audio, image, document, location
    
    -- Input
    input_text TEXT,
    input_metadata JSONB DEFAULT '{}',
    
    -- Processing metadata
    intent_class TEXT,
    emotion_scores JSONB DEFAULT '{}',
    stress_score FLOAT DEFAULT 0,
    
    -- Chain execution
    chain_used TEXT NOT NULL,
    model_used TEXT,
    latency_ms INTEGER,
    tokens_used INTEGER,
    
    -- Response
    response_text TEXT,
    response_metadata JSONB DEFAULT '{}',
    personality_mode TEXT,
    
    -- Quality scores (from self-critique)
    quality_accuracy_score FLOAT CHECK (quality_accuracy_score >= 0 AND quality_accuracy_score <= 1),
    quality_helpfulness_score FLOAT CHECK (quality_helpfulness_score >= 0 AND quality_helpfulness_score <= 1),
    quality_personality_fit_score FLOAT CHECK (quality_personality_fit_score >= 0 AND quality_personality_fit_score <= 1),
    
    -- Sources and context
    sources_used JSONB DEFAULT '[]',
    context_tiers JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Knowledge Base: Semantic knowledge store with pgvector embeddings
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    
    -- Content
    content TEXT NOT NULL,
    content_type TEXT NOT NULL, -- fact, preference, insight, pattern
    category TEXT, -- general, health, finance, work, relationships, etc.
    
    -- Source tracking
    source_interaction_id UUID REFERENCES interactions(id),
    source_type TEXT, -- interaction, research, external
    source_metadata JSONB DEFAULT '{}',
    
    -- Embedding for semantic search
    embedding VECTOR(768),
    
    -- Usage tracking
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    
    -- Quality
    confidence_score FLOAT DEFAULT 0.8 CHECK (confidence_score >= 0 AND confidence_score <= 1),
    quality_score FLOAT DEFAULT 0.8 CHECK (quality_score >= 0 AND quality_score <= 1),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- News Articles: Processed news with urgency scores and embeddings
CREATE TABLE IF NOT EXISTS news_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    
    -- Content
    title TEXT NOT NULL,
    summary TEXT,
    content_hash TEXT UNIQUE, -- For deduplication
    url TEXT,
    source_name TEXT,
    source_type TEXT, -- rss, api, scraped
    
    -- Processing
    original_text TEXT,
    bart_summary TEXT,
    entities JSONB DEFAULT '[]', -- NER extracted
    topics JSONB DEFAULT '[]', -- Zero-shot classified
    embedding VECTOR(768),
    
    -- Scoring
    urgency_score INTEGER CHECK (urgency_score >= 1 AND urgency_score <= 10),
    relevance_score FLOAT CHECK (relevance_score >= 0 AND relevance_score <= 1),
    interest_match JSONB DEFAULT '{}',
    
    -- Status
    processed BOOLEAN DEFAULT FALSE,
    delivered BOOLEAN DEFAULT FALSE,
    delivery_method TEXT, -- urgent, normal, digest
    
    -- Timestamps
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

-- Event Queue: Proactive events waiting for delivery
CREATE TABLE IF NOT EXISTS event_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    
    -- Event metadata
    event_type TEXT NOT NULL, -- breaking_news, financial_alert, pattern_alert, etc.
    urgency INTEGER NOT NULL CHECK (urgency >= 1 AND urgency <= 10),
    source_agent TEXT NOT NULL, -- daemon, engine, gateway, research_agent
    
    -- Content
    title TEXT NOT NULL,
    body TEXT,
    tillu_message TEXT, -- Personality-applied delivery text
    structured_data JSONB DEFAULT '{}',
    sources JSONB DEFAULT '[]',
    actions JSONB DEFAULT '["acknowledge", "dismiss"]',
    
    -- Personality
    personality_mode TEXT,
    
    -- Delivery
    deliver_after TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    require_ack BOOLEAN DEFAULT FALSE,
    target_client_id UUID,
    
    -- Status
    status TEXT DEFAULT 'pending', -- pending, delivered, acknowledged, expired
    delivered_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    
    -- Deduplication
    dedup_key TEXT,
    
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Research Sessions: Full research records with synthesis
CREATE TABLE IF NOT EXISTS research_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    
    -- Request
    query TEXT NOT NULL,
    research_plan JSONB DEFAULT '{}',
    
    -- Execution
    search_results JSONB DEFAULT '[]',
    scraped_content JSONB DEFAULT '[]',
    synthesis TEXT,
    critique JSONB DEFAULT '{}',
    iteration_count INTEGER DEFAULT 0,
    
    -- Output
    full_synthesis JSONB DEFAULT '{}',
    executive_summary TEXT,
    citations JSONB DEFAULT '[]',
    
    -- Embedding for semantic search
    embedding VECTOR(768),
    
    -- Status
    status TEXT DEFAULT 'pending', -- pending, searching, synthesizing, complete, failed
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Tasks & Goals: Tasks, goals, habits with probability scoring
CREATE TABLE IF NOT EXISTS tasks_goals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    
    -- Basic info
    title TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL, -- task, goal, habit, project
    category TEXT,
    
    -- Scheduling
    due_date TIMESTAMPTZ,
    start_date TIMESTAMPTZ,
    recurrence TEXT, -- daily, weekly, monthly, none
    
    -- Status
    status TEXT DEFAULT 'active', -- active, completed, archived, cancelled
    priority INTEGER DEFAULT 3 CHECK (priority >= 1 AND priority <= 5),
    
    -- Progress
    progress_percent INTEGER DEFAULT 0,
    completed_at TIMESTAMPTZ,
    
    -- AI-generated metrics
    probability_of_completion FLOAT DEFAULT 0.5 CHECK (probability_of_completion >= 0 AND probability_of_completion <= 1),
    estimated_effort_hours INTEGER,
    days_at_current_rate INTEGER,
    
    -- Nudging
    last_nudge_at TIMESTAMPTZ,
    nudge_count INTEGER DEFAULT 0,
    nudge_next_at TIMESTAMPTZ,
    
    -- Context
    related_knowledge_ids JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Emotion Log: Timestamped emotional state records
CREATE TABLE IF NOT EXISTS emotion_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    
    -- Emotion detection
    joy FLOAT DEFAULT 0,
    sadness FLOAT DEFAULT 0,
    anger FLOAT DEFAULT 0,
    fear FLOAT DEFAULT 0,
    surprise FLOAT DEFAULT 0,
    disgust FLOAT DEFAULT 0,
    neutral FLOAT DEFAULT 0,
    
    -- Aggregated
    dominant_emotion TEXT,
    emotion_intensity FLOAT,
    stress_level TEXT, -- high, medium, low
    
    -- Context
    interaction_id UUID REFERENCES interactions(id),
    context TEXT,
    
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Financial Tracking: Asset tracking with price history
CREATE TABLE IF NOT EXISTS financial_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    
    -- Asset info
    asset_type TEXT NOT NULL, -- crypto, stock, forex, commodity
    symbol TEXT NOT NULL,
    name TEXT,
    
    -- Tracking
    current_price FLOAT,
    price_currency TEXT DEFAULT 'USD',
    
    -- History
    price_history JSONB DEFAULT '[]', -- [{timestamp, price, change_pct}]
    
    -- Alerts
    alert_threshold_pct FLOAT DEFAULT 2.0,
    last_alert_at TIMESTAMPTZ,
    alert_count INTEGER DEFAULT 0,
    
    -- Portfolio
    quantity_held FLOAT DEFAULT 0,
    cost_basis FLOAT,
    
    -- Metadata
    source TEXT DEFAULT 'coingecko', -- coingecko, yahoo, alpha_vantage
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, symbol, asset_type)
);

-- Web Monitors: Registered URL watchers with state
CREATE TABLE IF NOT EXISTS web_monitors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    
    -- Target
    url TEXT NOT NULL,
    name TEXT,
    description TEXT,
    
    -- Monitoring config
    check_interval_minutes INTEGER DEFAULT 30,
    css_selector TEXT, -- Element to monitor
    content_type TEXT DEFAULT 'text', -- text, html, screenshot
    
    -- State
    last_content TEXT,
    last_content_hash TEXT,
    last_checked_at TIMESTAMPTZ,
    last_changed_at TIMESTAMPTZ,
    change_count INTEGER DEFAULT 0,
    
    -- Alerting
    alert_threshold FLOAT DEFAULT 0.1, -- Content change threshold
    notify_on_change BOOLEAN DEFAULT TRUE,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_error TEXT,
    consecutive_errors INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- People Knowledge: Relationship intelligence with embeddings
CREATE TABLE IF NOT EXISTS people_knowledge (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    
    -- Person info
    name TEXT NOT NULL,
    relationship_type TEXT, -- family, friend, colleague, etc.
    contact_info JSONB DEFAULT '{}',
    
    -- Context
    notes TEXT,
    preferences JSONB DEFAULT '{}',
    conversation_history JSONB DEFAULT '[]',
    
    -- Relationship tracking
    last_interaction_at TIMESTAMPTZ,
    interaction_frequency TEXT, -- daily, weekly, monthly, rare
    relationship_health_score FLOAT DEFAULT 0.8,
    
    -- Important dates
    birthday DATE,
    anniversary DATE,
    other_dates JSONB DEFAULT '[]',
    
    -- Embedding
    embedding VECTOR(768),
    
    -- Maintenance
    needs_attention BOOLEAN DEFAULT FALSE,
    suggested_actions JSONB DEFAULT '[]',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- System Analytics: Per-hour operational metrics
CREATE TABLE IF NOT EXISTS system_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Time bucket
    hour_bucket TIMESTAMPTZ NOT NULL,
    
    -- API usage by provider
    groq_requests INTEGER DEFAULT 0,
    groq_tokens INTEGER DEFAULT 0,
    cerebras_requests INTEGER DEFAULT 0,
    openrouter_requests INTEGER DEFAULT 0,
    gemini_requests INTEGER DEFAULT 0,
    cohere_requests INTEGER DEFAULT 0,
    
    -- HF API usage
    hf_embedding_requests INTEGER DEFAULT 0,
    hf_emotion_requests INTEGER DEFAULT 0,
    hf_intent_requests INTEGER DEFAULT 0,
    hf_ner_requests INTEGER DEFAULT 0,
    hf_summarizer_requests INTEGER DEFAULT 0,
    
    -- External API usage
    newsapi_requests INTEGER DEFAULT 0,
    brave_requests INTEGER DEFAULT 0,
    coingecko_requests INTEGER DEFAULT 0,
    
    -- System metrics
    total_interactions INTEGER DEFAULT 0,
    avg_latency_ms FLOAT,
    error_count INTEGER DEFAULT 0,
    error_rate FLOAT,
    
    -- Storage
    supabase_storage_mb FLOAT,
    redis_memory_mb FLOAT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(hour_bucket)
);

-- Daemon Monitor State: Daemon loop health tracking
CREATE TABLE IF NOT EXISTS monitor_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    loop_name TEXT NOT NULL UNIQUE,
    is_running BOOLEAN DEFAULT TRUE,
    last_execution_at TIMESTAMPTZ,
    next_execution_at TIMESTAMPTZ,
    execution_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    avg_execution_time_ms FLOAT,
    
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Archived Index: Pointers to GitHub-archived old data
CREATE TABLE IF NOT EXISTS archived_index (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    archive_type TEXT NOT NULL, -- interactions, news, events
    date_range_start TIMESTAMPTZ NOT NULL,
    date_range_end TIMESTAMPTZ NOT NULL,
    
    -- Archive location
    github_repo TEXT,
    github_path TEXT,
    github_commit_hash TEXT,
    
    -- Metadata
    record_count INTEGER,
    file_size_bytes INTEGER,
    compressed BOOLEAN DEFAULT TRUE,
    
    archived_at TIMESTAMPTZ DEFAULT NOW()
);

-- Client Registry: Registered clients with capabilities
CREATE TABLE IF NOT EXISTS client_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),
    
    -- Client info
    client_name TEXT NOT NULL,
    client_type TEXT NOT NULL, -- whatsapp, web, mobile, api
    
    -- Capabilities
    supports_text BOOLEAN DEFAULT TRUE,
    supports_audio BOOLEAN DEFAULT FALSE,
    supports_image BOOLEAN DEFAULT FALSE,
    supports_document BOOLEAN DEFAULT FALSE,
    supports_location BOOLEAN DEFAULT FALSE,
    supports_sse BOOLEAN DEFAULT FALSE,
    supports_websocket BOOLEAN DEFAULT FALSE,
    
    -- Preferences
    preferences JSONB DEFAULT '{}',
    
    -- Connection
    is_connected BOOLEAN DEFAULT FALSE,
    last_connected_at TIMESTAMPTZ,
    connection_metadata JSONB DEFAULT '{}',
    
    -- Auth
    api_key_hash TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Interactions
CREATE INDEX IF NOT EXISTS idx_interactions_user_id ON interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_session_id ON interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON interactions(created_at);
CREATE INDEX IF NOT EXISTS idx_interactions_intent_class ON interactions(intent_class);

-- Knowledge Base (with vector similarity)
CREATE INDEX IF NOT EXISTS idx_knowledge_base_user_id ON knowledge_base(user_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_category ON knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding ON knowledge_base 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- News Articles
CREATE INDEX IF NOT EXISTS idx_news_articles_user_id ON news_articles(user_id);
CREATE INDEX IF NOT EXISTS idx_news_articles_urgency ON news_articles(urgency_score);
CREATE INDEX IF NOT EXISTS idx_news_articles_fetched ON news_articles(fetched_at);
CREATE INDEX IF NOT EXISTS idx_news_articles_embedding ON news_articles
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Event Queue
CREATE INDEX IF NOT EXISTS idx_event_queue_user_id ON event_queue(user_id);
CREATE INDEX IF NOT EXISTS idx_event_queue_status ON event_queue(status);
CREATE INDEX IF NOT EXISTS idx_event_queue_urgency ON event_queue(urgency);
CREATE INDEX IF NOT EXISTS idx_event_queue_deliver_after ON event_queue(deliver_after);

-- Research Sessions
CREATE INDEX IF NOT EXISTS idx_research_sessions_user_id ON research_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_research_sessions_embedding ON research_sessions
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Tasks & Goals
CREATE INDEX IF NOT EXISTS idx_tasks_goals_user_id ON tasks_goals(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_goals_status ON tasks_goals(status);
CREATE INDEX IF NOT EXISTS idx_tasks_goals_due_date ON tasks_goals(due_date);

-- Emotion Log
CREATE INDEX IF NOT EXISTS idx_emotion_log_user_id ON emotion_log(user_id);
CREATE INDEX IF NOT EXISTS idx_emotion_log_recorded ON emotion_log(recorded_at);

-- Financial Tracking
CREATE INDEX IF NOT EXISTS idx_financial_tracking_user_id ON financial_tracking(user_id);
CREATE INDEX IF NOT EXISTS idx_financial_tracking_symbol ON financial_tracking(symbol);

-- Web Monitors
CREATE INDEX IF NOT EXISTS idx_web_monitors_user_id ON web_monitors(user_id);
CREATE INDEX IF NOT EXISTS idx_web_monitors_active ON web_monitors(is_active);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_user_profile_updated_at BEFORE UPDATE ON user_profile
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_knowledge_base_updated_at BEFORE UPDATE ON knowledge_base
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_goals_updated_at BEFORE UPDATE ON tasks_goals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_financial_tracking_updated_at BEFORE UPDATE ON financial_tracking
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_web_monitors_updated_at BEFORE UPDATE ON web_monitors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_people_knowledge_updated_at BEFORE UPDATE ON people_knowledge
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_client_registry_updated_at BEFORE UPDATE ON client_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Access count increment function
CREATE OR REPLACE FUNCTION increment_access_count(knowledge_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE knowledge_base
    SET access_count = access_count + 1,
        last_accessed = NOW()
    WHERE id = knowledge_id;
END;
$$ LANGUAGE plpgsql;

-- Similarity search function
CREATE OR REPLACE FUNCTION search_knowledge(
    query_embedding VECTOR(768),
    user_uuid UUID,
    similarity_threshold FLOAT DEFAULT 0.75,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    content_type TEXT,
    category TEXT,
    confidence_score FLOAT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        kb.id,
        kb.content,
        kb.content_type,
        kb.category,
        kb.confidence_score,
        1 - (kb.embedding <=> query_embedding) as similarity
    FROM knowledge_base kb
    WHERE kb.user_id = user_uuid
        AND 1 - (kb.embedding <=> query_embedding) > similarity_threshold
    ORDER BY kb.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Search news articles function
CREATE OR REPLACE FUNCTION search_news(
    query_embedding VECTOR(768),
    user_uuid UUID,
    min_urgency INTEGER DEFAULT 1,
    similarity_threshold FLOAT DEFAULT 0.70,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    summary TEXT,
    urgency_score INTEGER,
    relevance_score FLOAT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        na.id,
        na.title,
        na.summary,
        na.urgency_score,
        na.relevance_score,
        1 - (na.embedding <=> query_embedding) as similarity
    FROM news_articles na
    WHERE na.user_id = user_uuid
        AND na.urgency_score >= min_urgency
        AND 1 - (na.embedding <=> query_embedding) > similarity_threshold
    ORDER BY na.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE user_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE news_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks_goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE emotion_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE web_monitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE people_knowledge ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_registry ENABLE ROW LEVEL SECURITY;

-- Create policies (users can only access their own data)
CREATE POLICY user_profile_isolation ON user_profile
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY interactions_isolation ON interactions
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY knowledge_base_isolation ON knowledge_base
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY news_articles_isolation ON news_articles
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY event_queue_isolation ON event_queue
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY research_sessions_isolation ON research_sessions
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY tasks_goals_isolation ON tasks_goals
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY emotion_log_isolation ON emotion_log
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY financial_tracking_isolation ON financial_tracking
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY web_monitors_isolation ON web_monitors
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY people_knowledge_isolation ON people_knowledge
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY client_registry_isolation ON client_registry
    FOR ALL USING (user_id = auth.uid());

-- Service role bypass (for backend processes)
CREATE POLICY service_role_bypass_user_profile ON user_profile
    FOR ALL
    TO service_role
    USING (true);

CREATE POLICY service_role_bypass_interactions ON interactions
    FOR ALL
    TO service_role
    USING (true);

CREATE POLICY service_role_bypass_knowledge_base ON knowledge_base
    FOR ALL
    TO service_role
    USING (true);

-- (Additional service role policies for other tables as needed)

-- ============================================================================
-- EMAILS TABLE (Phase 5 - Email Intelligence)
-- ============================================================================

CREATE TABLE IF NOT EXISTS emails (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profile(user_id),

    -- Gmail metadata
    email_id TEXT UNIQUE,
    thread_id TEXT,

    -- Content
    sender TEXT,
    subject TEXT,
    summary TEXT,
    body_preview TEXT,

    -- Analysis
    importance_score INTEGER DEFAULT 5 CHECK (importance_score >= 1 AND importance_score <= 10),
    sentiment TEXT DEFAULT 'neutral',
    stress_level TEXT DEFAULT 'low',
    entities JSONB DEFAULT '[]',

    -- Action
    requires_response BOOLEAN DEFAULT FALSE,
    suggested_response TEXT,

    -- Status
    analyzed BOOLEAN DEFAULT FALSE,
    responded BOOLEAN DEFAULT FALSE,

    -- Timestamps
    received_at TIMESTAMPTZ,
    analyzed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emails_user_id ON emails(user_id);
CREATE INDEX IF NOT EXISTS idx_emails_importance ON emails(importance_score);
CREATE INDEX IF NOT EXISTS idx_emails_received ON emails(received_at);

ALTER TABLE emails ENABLE ROW LEVEL SECURITY;
CREATE POLICY emails_isolation ON emails FOR ALL USING (user_id = auth.uid());
CREATE POLICY service_role_bypass_emails ON emails FOR ALL TO service_role USING (true);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Count interactions for a user/session (used by CombinedMemory)
CREATE OR REPLACE FUNCTION count_interactions(
    p_user_id UUID,
    p_session_id UUID DEFAULT NULL
)
RETURNS INTEGER AS $$
DECLARE
    cnt INTEGER;
BEGIN
    IF p_session_id IS NOT NULL THEN
        SELECT COUNT(*) INTO cnt
        FROM interactions
        WHERE user_id = p_user_id AND session_id = p_session_id;
    ELSE
        SELECT COUNT(*) INTO cnt
        FROM interactions
        WHERE user_id = p_user_id;
    END IF;
    RETURN cnt;
END;
$$ LANGUAGE plpgsql;

-- Service role bypass for emails and system tables
CREATE POLICY service_role_bypass_event_queue ON event_queue
    FOR ALL TO service_role USING (true);

CREATE POLICY service_role_bypass_news_articles ON news_articles
    FOR ALL TO service_role USING (true);

CREATE POLICY service_role_bypass_research_sessions ON research_sessions
    FOR ALL TO service_role USING (true);

CREATE POLICY service_role_bypass_tasks_goals ON tasks_goals
    FOR ALL TO service_role USING (true);

CREATE POLICY service_role_bypass_emotion_log ON emotion_log
    FOR ALL TO service_role USING (true);

CREATE POLICY service_role_bypass_financial_tracking ON financial_tracking
    FOR ALL TO service_role USING (true);

CREATE POLICY service_role_bypass_web_monitors ON web_monitors
    FOR ALL TO service_role USING (true);

CREATE POLICY service_role_bypass_people_knowledge ON people_knowledge
    FOR ALL TO service_role USING (true);

CREATE POLICY service_role_bypass_client_registry ON client_registry
    FOR ALL TO service_role USING (true);
