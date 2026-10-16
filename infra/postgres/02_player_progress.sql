-- Table to track player profile and PSN metadata
CREATE TABLE IF NOT EXISTS players (
    id VARCHAR(64) PRIMARY KEY,
    psn_id VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to track games in a player's trophy catalog
CREATE TABLE IF NOT EXISTS player_games (
    id VARCHAR(64) PRIMARY KEY,
    player_id VARCHAR(64) REFERENCES players(id) ON DELETE CASCADE,
    game_title VARCHAR(100) NOT NULL,
    platform VARCHAR(20) DEFAULT 'PS5', -- PS5, PS4, PS3
    total_trophies INT NOT NULL DEFAULT 0,
    unlocked_trophies INT NOT NULL DEFAULT 0,
    platinum_status VARCHAR(20) DEFAULT 'in_progress', -- in_progress, completed, abandoned
    last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, game_title, platform)
);

-- Table tracking each specific trophy state for a player
CREATE TABLE IF NOT EXISTS player_trophies (
    id VARCHAR(64) PRIMARY KEY,
    player_game_id VARCHAR(64) REFERENCES player_games(id) ON DELETE CASCADE,
    trophy_name VARCHAR(255) NOT NULL,
    trophy_type VARCHAR(20) NOT NULL, -- bronze, silver, gold, platinum
    is_missable BOOLEAN DEFAULT FALSE,
    is_unlocked BOOLEAN DEFAULT FALSE,
    unlocked_at TIMESTAMP WITH TIME ZONE,
    chapter_or_location VARCHAR(255),
    UNIQUE(player_game_id, trophy_name)
);

-- Performance indexes for rapid agent lookups
CREATE INDEX IF NOT EXISTS idx_player_games_player ON player_games(player_id);
CREATE INDEX IF NOT EXISTS idx_player_trophies_unlocked ON player_trophies(player_game_id, is_unlocked);
CREATE INDEX IF NOT EXISTS idx_player_trophies_missable ON player_trophies(player_game_id, is_missable);
