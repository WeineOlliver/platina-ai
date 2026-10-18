-- Migration 05: Add trophy_category to player_trophies and index for fast category filtering
ALTER TABLE player_trophies 
ADD COLUMN IF NOT EXISTS trophy_category VARCHAR(32) DEFAULT 'standard';

CREATE INDEX IF NOT EXISTS idx_player_trophies_category 
ON player_trophies(trophy_category);
