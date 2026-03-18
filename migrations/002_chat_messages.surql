-- Chat message table for persisting conversation history
DEFINE TABLE chat_message SCHEMALESS;
DEFINE FIELD session_id ON TABLE chat_message TYPE string;
DEFINE FIELD role ON TABLE chat_message TYPE string;
DEFINE FIELD content ON TABLE chat_message TYPE string;
DEFINE FIELD references_data ON TABLE chat_message TYPE option<string>;
DEFINE FIELD user_id ON TABLE chat_message TYPE string;
DEFINE FIELD created ON TABLE chat_message TYPE option<datetime>;
DEFINE FIELD updated ON TABLE chat_message TYPE option<datetime>;
DEFINE INDEX idx_chatmsg_session ON TABLE chat_message COLUMNS session_id;

-- Add source_id and notebook_id to chat_session for direct linking
DEFINE FIELD source_id ON TABLE chat_session TYPE option<string>;
DEFINE FIELD notebook_id ON TABLE chat_session TYPE option<string>;
DEFINE INDEX idx_chatsession_source ON TABLE chat_session COLUMNS source_id;
DEFINE INDEX idx_chatsession_notebook ON TABLE chat_session COLUMNS notebook_id;

-- Record this migration
INSERT INTO _sbl_migrations { version: 2, applied_at: time::now() };
