-- Migration 13: Seed Witcher 3 player profile referencing canonical catalog trophies

-- Ensure player 'ply_olliverw9_01' exists
INSERT INTO players (id, psn_id, email)
VALUES ('ply_olliverw9_01', 'olliverW9', 'olliverw9@platina.ai')
ON CONFLICT (psn_id) DO NOTHING;

-- Insert/update player_games 'pg_witcher3_01' for 'The Witcher 3: Wild Hunt'
INSERT INTO player_games (id, player_id, game_title, platform, total_trophies, unlocked_trophies, platinum_status)
VALUES ('pg_witcher3_01', 'ply_olliverw9_01', 'The Witcher 3: Wild Hunt', 'PS5', 79, 0, 'in_progress')
ON CONFLICT (player_id, game_title, platform)
DO UPDATE SET
    total_trophies = EXCLUDED.total_trophies,
    unlocked_trophies = EXCLUDED.unlocked_trophies,
    platinum_status = EXCLUDED.platinum_status;

-- Clean up any legacy manual seed entries for pg_witcher3_01
DELETE FROM player_trophies WHERE player_game_id = 'pg_witcher3_01';

-- Seed player_trophies for all 79 canonical trophies of 'the-witcher-3-wild-hunt'
INSERT INTO player_trophies (
    id,
    player_game_id,
    trophy_id,
    trophy_name,
    trophy_type,
    trophy_category,
    is_missable,
    is_unlocked,
    unlocked_at,
    chapter_or_location
)
SELECT
    'pt_' || t.id,
    'pg_witcher3_01',
    t.id,
    t.name,
    t.type,
    CASE WHEN t.missable THEN 'missable' ELSE 'standard' END,
    t.missable,
    false,
    NULL,
    t.location
FROM trophies t
WHERE t.game_id = 'the-witcher-3-wild-hunt'
ON CONFLICT (player_game_id, trophy_name)
DO UPDATE SET
    trophy_id = EXCLUDED.trophy_id,
    trophy_type = EXCLUDED.trophy_type,
    trophy_category = EXCLUDED.trophy_category,
    is_missable = EXCLUDED.is_missable,
    is_unlocked = EXCLUDED.is_unlocked,
    unlocked_at = EXCLUDED.unlocked_at,
    chapter_or_location = EXCLUDED.chapter_or_location;
