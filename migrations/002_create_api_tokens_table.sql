-- API Token Storage Table
-- For caching external API authentication tokens

CREATE TABLE IF NOT EXISTS api_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service TEXT UNIQUE NOT NULL,  -- 'life360', 'google', etc.
    token_data JSONB NOT NULL,     -- Encrypted token information
    expires_at TIMESTAMPTZ,        -- When token expires
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for service lookup
CREATE INDEX IF NOT EXISTS idx_api_tokens_service ON api_tokens(service);

-- Index for expiration cleanup
CREATE INDEX IF NOT EXISTS idx_api_tokens_expires ON api_tokens(expires_at);

-- RLS policies
ALTER TABLE api_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage tokens" ON api_tokens
    FOR ALL TO service_role USING (true);

-- Auto-update timestamp trigger
CREATE TRIGGER update_api_tokens_updated_at 
    BEFORE UPDATE ON api_tokens 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Table documentation
COMMENT ON TABLE api_tokens IS 'Cached authentication tokens for external APIs';
COMMENT ON COLUMN api_tokens.service IS 'External service identifier (life360, google, etc.)';
COMMENT ON COLUMN api_tokens.token_data IS 'Encrypted token data including access_token, refresh_token, etc.';