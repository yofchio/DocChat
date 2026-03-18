-- User table
DEFINE TABLE user SCHEMAFULL;
DEFINE FIELD username ON TABLE user TYPE string;
DEFINE FIELD email ON TABLE user TYPE string;
DEFINE FIELD password_hash ON TABLE user TYPE string;
DEFINE FIELD created ON TABLE user TYPE option<datetime>;
DEFINE FIELD updated ON TABLE user TYPE option<datetime>;
DEFINE INDEX idx_user_username ON TABLE user COLUMNS username UNIQUE;
DEFINE INDEX idx_user_email ON TABLE user COLUMNS email UNIQUE;

-- Notebook table
DEFINE TABLE notebook SCHEMAFULL;
DEFINE FIELD user_id ON TABLE notebook TYPE string;
DEFINE FIELD name ON TABLE notebook TYPE string;
DEFINE FIELD description ON TABLE notebook TYPE string;
DEFINE FIELD archived ON TABLE notebook TYPE option<bool> DEFAULT false;
DEFINE FIELD created ON TABLE notebook TYPE option<datetime>;
DEFINE FIELD updated ON TABLE notebook TYPE option<datetime>;
DEFINE INDEX idx_notebook_user ON TABLE notebook COLUMNS user_id;

-- Source table
DEFINE TABLE source SCHEMALESS;
DEFINE FIELD user_id ON TABLE source TYPE string;
DEFINE FIELD title ON TABLE source TYPE option<string>;
DEFINE FIELD full_text ON TABLE source TYPE option<string>;
DEFINE FIELD asset ON TABLE source TYPE option<object>;
DEFINE FIELD topics ON TABLE source TYPE option<array>;
DEFINE FIELD created ON TABLE source TYPE option<datetime>;
DEFINE FIELD updated ON TABLE source TYPE option<datetime>;
DEFINE INDEX idx_source_user ON TABLE source COLUMNS user_id;

-- Note table
DEFINE TABLE note SCHEMALESS;
DEFINE FIELD user_id ON TABLE note TYPE string;
DEFINE FIELD title ON TABLE note TYPE option<string>;
DEFINE FIELD content ON TABLE note TYPE option<string>;
DEFINE FIELD note_type ON TABLE note TYPE option<string>;
DEFINE FIELD embedding ON TABLE note TYPE option<array>;
DEFINE FIELD created ON TABLE note TYPE option<datetime>;
DEFINE FIELD updated ON TABLE note TYPE option<datetime>;
DEFINE INDEX idx_note_user ON TABLE note COLUMNS user_id;

-- Chat session table
DEFINE TABLE chat_session SCHEMALESS;
DEFINE FIELD user_id ON TABLE chat_session TYPE string;
DEFINE FIELD title ON TABLE chat_session TYPE option<string>;
DEFINE FIELD model_override ON TABLE chat_session TYPE option<string>;
DEFINE FIELD created ON TABLE chat_session TYPE option<datetime>;
DEFINE FIELD updated ON TABLE chat_session TYPE option<datetime>;

-- Source embedding table (for vector search)
DEFINE TABLE source_embedding SCHEMALESS;
DEFINE FIELD source ON TABLE source_embedding TYPE record<source>;
DEFINE FIELD content ON TABLE source_embedding TYPE string;
DEFINE FIELD embedding ON TABLE source_embedding TYPE option<array>;
DEFINE FIELD created ON TABLE source_embedding TYPE option<datetime>;
DEFINE FIELD updated ON TABLE source_embedding TYPE option<datetime>;

-- Relationship tables
DEFINE TABLE reference SCHEMAFULL TYPE RELATION IN source OUT notebook;
DEFINE TABLE artifact SCHEMAFULL TYPE RELATION IN note OUT notebook;
DEFINE TABLE refers_to SCHEMAFULL TYPE RELATION IN chat_session OUT notebook;

-- Podcast tables
DEFINE TABLE episode_profile SCHEMALESS;
DEFINE FIELD user_id ON TABLE episode_profile TYPE string;
DEFINE FIELD name ON TABLE episode_profile TYPE string;
DEFINE FIELD description ON TABLE episode_profile TYPE option<string>;
DEFINE FIELD speaker_config ON TABLE episode_profile TYPE string;
DEFINE FIELD outline_llm ON TABLE episode_profile TYPE option<string>;
DEFINE FIELD transcript_llm ON TABLE episode_profile TYPE option<string>;
DEFINE FIELD language ON TABLE episode_profile TYPE option<string>;
DEFINE FIELD default_briefing ON TABLE episode_profile TYPE string;
DEFINE FIELD num_segments ON TABLE episode_profile TYPE int DEFAULT 5;
DEFINE FIELD created ON TABLE episode_profile TYPE option<datetime>;
DEFINE FIELD updated ON TABLE episode_profile TYPE option<datetime>;
DEFINE INDEX idx_ep_user ON TABLE episode_profile COLUMNS user_id;

DEFINE TABLE speaker_profile SCHEMALESS;
DEFINE FIELD user_id ON TABLE speaker_profile TYPE string;
DEFINE FIELD name ON TABLE speaker_profile TYPE string;
DEFINE FIELD description ON TABLE speaker_profile TYPE option<string>;
DEFINE FIELD voice_model ON TABLE speaker_profile TYPE option<string>;
DEFINE FIELD speakers ON TABLE speaker_profile TYPE array;
DEFINE FIELD created ON TABLE speaker_profile TYPE option<datetime>;
DEFINE FIELD updated ON TABLE speaker_profile TYPE option<datetime>;
DEFINE INDEX idx_sp_user ON TABLE speaker_profile COLUMNS user_id;

DEFINE TABLE episode SCHEMALESS;
DEFINE FIELD user_id ON TABLE episode TYPE string;
DEFINE FIELD name ON TABLE episode TYPE string;
DEFINE FIELD episode_profile ON TABLE episode TYPE object;
DEFINE FIELD speaker_profile ON TABLE episode TYPE object;
DEFINE FIELD briefing ON TABLE episode TYPE string;
DEFINE FIELD content ON TABLE episode TYPE string;
DEFINE FIELD audio_file ON TABLE episode TYPE option<string>;
DEFINE FIELD transcript ON TABLE episode TYPE option<object>;
DEFINE FIELD outline ON TABLE episode TYPE option<object>;
DEFINE FIELD status ON TABLE episode TYPE option<string> DEFAULT 'pending';
DEFINE FIELD error_message ON TABLE episode TYPE option<string>;
DEFINE FIELD created ON TABLE episode TYPE option<datetime>;
DEFINE FIELD updated ON TABLE episode TYPE option<datetime>;
DEFINE INDEX idx_episode_user ON TABLE episode COLUMNS user_id;

-- Migration tracking
DEFINE TABLE IF NOT EXISTS _sbl_migrations SCHEMAFULL;
DEFINE FIELD version ON TABLE _sbl_migrations TYPE int;
DEFINE FIELD applied_at ON TABLE _sbl_migrations TYPE datetime;

-- Record this migration
INSERT INTO _sbl_migrations { version: 1, applied_at: time::now() };
