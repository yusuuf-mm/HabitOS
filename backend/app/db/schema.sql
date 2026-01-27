-- PostgreSQL Schema for Behavioral Optimization Platform
-- Created: 2026-01-27

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enums
CREATE TYPE user_status AS ENUM ('active', 'inactive', 'suspended');
CREATE TYPE behavior_category AS ENUM ('health', 'productivity', 'learning', 'wellness', 'social');
CREATE TYPE time_slot AS ENUM ('morning', 'afternoon', 'evening', 'night', 'flexible');
CREATE TYPE objective_type AS ENUM ('health', 'productivity', 'learning', 'wellness', 'social');
CREATE TYPE constraint_type AS ENUM (
    'time_budget',
    'frequency',
    'duration_bounds',
    'precedence',
    'mutual_exclusion'
);
CREATE TYPE optimization_status AS ENUM ('pending', 'running', 'completed', 'failed');
CREATE TYPE solver_type AS ENUM ('linear', 'nonlinear', 'heuristic', 'evolutionary');

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    status user_status DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    CONSTRAINT valid_email CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_username ON users (username);

-- Behaviors table
CREATE TABLE behaviors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category behavior_category NOT NULL,
    min_duration INT NOT NULL,
    typical_duration INT NOT NULL,
    max_duration INT NOT NULL,
    energy_cost FLOAT DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    preferred_time_slots time_slot[] DEFAULT ARRAY['flexible'],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Impact on objectives (0-1 scale)
    impact_on_health FLOAT DEFAULT 0.0,
    impact_on_productivity FLOAT DEFAULT 0.0,
    impact_on_learning FLOAT DEFAULT 0.0,
    impact_on_wellness FLOAT DEFAULT 0.0,
    impact_on_social FLOAT DEFAULT 0.0,
    CONSTRAINT positive_durations CHECK (min_duration > 0 AND typical_duration >= min_duration AND max_duration >= typical_duration),
    CONSTRAINT valid_energy_cost CHECK (energy_cost > 0),
    CONSTRAINT valid_impacts CHECK (
        impact_on_health >= 0 AND impact_on_health <= 1 AND
        impact_on_productivity >= 0 AND impact_on_productivity <= 1 AND
        impact_on_learning >= 0 AND impact_on_learning <= 1 AND
        impact_on_wellness >= 0 AND impact_on_wellness <= 1 AND
        impact_on_social >= 0 AND impact_on_social <= 1
    )
);

CREATE INDEX idx_behaviors_user_id ON behaviors (user_id);
CREATE INDEX idx_behaviors_category ON behaviors (category);
CREATE INDEX idx_behaviors_is_active ON behaviors (is_active);

-- Objectives table
CREATE TABLE objectives (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    type objective_type NOT NULL,
    weight FLOAT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_objective UNIQUE (user_id, type),
    CONSTRAINT valid_weight CHECK (weight >= 0 AND weight <= 1)
);

CREATE INDEX idx_objectives_user_id ON objectives (user_id);
CREATE INDEX idx_objectives_type ON objectives (type);

-- Constraints table
CREATE TABLE constraints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    type constraint_type NOT NULL,
    parameters JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_constraints_user_id ON constraints (user_id);
CREATE INDEX idx_constraints_type ON constraints (type);

-- Optimization Runs table
CREATE TABLE optimization_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    status optimization_status DEFAULT 'pending',
    solver solver_type NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    time_periods INT NOT NULL,
    results JSONB,
    diagnostics JSONB,
    total_objective_value FLOAT,
    execution_time_seconds FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_date_range CHECK (start_date <= end_date)
);

CREATE INDEX idx_optimization_runs_user_id ON optimization_runs (user_id);
CREATE INDEX idx_optimization_runs_status ON optimization_runs (status);
CREATE INDEX idx_optimization_runs_created_at ON optimization_runs (created_at DESC);

-- Scheduled Behaviors table (results of optimization)
CREATE TABLE scheduled_behaviors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    optimization_run_id UUID NOT NULL REFERENCES optimization_runs (id) ON DELETE CASCADE,
    behavior_id UUID NOT NULL REFERENCES behaviors (id) ON DELETE CASCADE,
    time_period INT NOT NULL,
    scheduled_duration INT NOT NULL,
    is_scheduled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_time_period CHECK (time_period > 0),
    CONSTRAINT valid_duration CHECK (scheduled_duration > 0)
);

CREATE INDEX idx_scheduled_behaviors_optimization_run_id ON scheduled_behaviors (optimization_run_id);
CREATE INDEX idx_scheduled_behaviors_behavior_id ON scheduled_behaviors (behavior_id);

-- Completion Logs table (tracking actual completions)
CREATE TABLE completion_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    behavior_id UUID NOT NULL REFERENCES behaviors (id) ON DELETE CASCADE,
    optimization_run_id UUID REFERENCES optimization_runs (id) ON DELETE SET NULL,
    actual_duration INT NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    satisfaction_score INT,
    notes TEXT,
    context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_satisfaction CHECK (satisfaction_score IS NULL OR (satisfaction_score >= 1 AND satisfaction_score <= 5)),
    CONSTRAINT valid_duration CHECK (actual_duration > 0)
);

CREATE INDEX idx_completion_logs_user_id ON completion_logs (user_id);
CREATE INDEX idx_completion_logs_behavior_id ON completion_logs (behavior_id);
CREATE INDEX idx_completion_logs_completed_at ON completion_logs (completed_at DESC);
CREATE INDEX idx_completion_logs_optimization_run_id ON completion_logs (optimization_run_id);

-- Views for Analytics
CREATE VIEW behavior_statistics AS
SELECT
    b.id,
    b.user_id,
    b.name,
    COUNT(cl.id) as total_completions,
    AVG(cl.actual_duration) as avg_duration,
    AVG(COALESCE(cl.satisfaction_score, 0)) as avg_satisfaction,
    MAX(cl.completed_at) as last_completed,
    COALESCE(SUM(cl.actual_duration), 0) as total_duration
FROM behaviors b
LEFT JOIN completion_logs cl ON b.id = cl.behavior_id
GROUP BY b.id, b.user_id, b.name;

CREATE VIEW optimization_summary AS
SELECT
    o.id,
    o.user_id,
    o.status,
    o.solver,
    o.start_date,
    o.end_date,
    COUNT(sb.id) as behaviors_scheduled,
    SUM(sb.scheduled_duration) as total_scheduled_duration,
    o.total_objective_value,
    o.execution_time_seconds,
    o.created_at
FROM optimization_runs o
LEFT JOIN scheduled_behaviors sb ON o.id = sb.optimization_run_id
GROUP BY o.id, o.user_id, o.status, o.solver, o.start_date, o.end_date, o.total_objective_value, o.execution_time_seconds, o.created_at;

-- Triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at_trigger BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER behaviors_updated_at_trigger BEFORE UPDATE ON behaviors FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER objectives_updated_at_trigger BEFORE UPDATE ON objectives FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER constraints_updated_at_trigger BEFORE UPDATE ON constraints FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER optimization_runs_updated_at_trigger BEFORE UPDATE ON optimization_runs FOR EACH ROW EXECUTE FUNCTION update_updated_at();
