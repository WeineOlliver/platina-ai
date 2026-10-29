-- Canonical Game & Trophy Catalog Schema
-- Table for canonical games metadata
CREATE TABLE IF NOT EXISTS games (
    id VARCHAR(100) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    np_communication_id VARCHAR(64),
    aliases TEXT[] DEFAULT '{}'::text[],
    difficulty NUMERIC,
    hours INT,
    playthroughs INT,
    metadata_source TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for canonical trophies metadata
CREATE TABLE IF NOT EXISTS trophies (
    id VARCHAR(128) PRIMARY KEY,
    game_id VARCHAR(100) NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    psn_trophy_id INT,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20) NOT NULL,
    description TEXT,
    dlc VARCHAR(100),
    location TEXT[],
    missable BOOLEAN DEFAULT FALSE,
    missable_sources TEXT[] DEFAULT '{}'::text[],
    aliases TEXT[] DEFAULT '{}'::text[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, name)
);

CREATE INDEX IF NOT EXISTS idx_trophies_game_id ON trophies(game_id);
CREATE INDEX IF NOT EXISTS idx_trophies_missable ON trophies(missable);
CREATE INDEX IF NOT EXISTS idx_trophies_dlc ON trophies(dlc);

-- Add canonical catalog foreign keys to guide_chunks
ALTER TABLE guide_chunks ADD COLUMN IF NOT EXISTS game_id VARCHAR(100) REFERENCES games(id) ON DELETE SET NULL;
ALTER TABLE guide_chunks ADD COLUMN IF NOT EXISTS trophy_id VARCHAR(128) REFERENCES trophies(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_guide_chunks_game_id ON guide_chunks(game_id);
CREATE INDEX IF NOT EXISTS idx_guide_chunks_trophy_id ON guide_chunks(trophy_id);

-- Add canonical trophy foreign key to player_trophies
ALTER TABLE player_trophies ADD COLUMN IF NOT EXISTS trophy_id VARCHAR(128) REFERENCES trophies(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_player_trophies_trophy_id ON player_trophies(trophy_id);
