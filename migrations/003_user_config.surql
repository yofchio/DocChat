-- Per-user AI configuration (default provider/model + optional API keys)
DEFINE TABLE user_config SCHEMALESS;
DEFINE FIELD user_id ON TABLE user_config TYPE string;
DEFINE FIELD default_provider ON TABLE user_config TYPE option<string>;
DEFINE FIELD default_model ON TABLE user_config TYPE option<string>;
DEFINE FIELD google_api_key ON TABLE user_config TYPE option<string>;
DEFINE FIELD openai_api_key ON TABLE user_config TYPE option<string>;
DEFINE FIELD created ON TABLE user_config TYPE option<datetime>;
DEFINE FIELD updated ON TABLE user_config TYPE option<datetime>;

-- Record this migration
INSERT INTO _sbl_migrations { version: 3, applied_at: time::now() };

