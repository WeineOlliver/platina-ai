-- Migration 08: Synchronize complete canonical community missables across all games in catalog

-- 1. The Witcher 3: Wild Hunt (10 canonical missables)
-- Insert missing missable trophies for pg_witcher3_01
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_tw3_m_even_odds', 'pg_witcher3_01', 'Even Odds', 'silver', 'missable', true, false, NULL, 'Contratos de Bruxo'),
    ('tr_tw3_m_fast_furious', 'pg_witcher3_01', 'Fast and Furious', 'bronze', 'missable', true, false, NULL, 'Corridas de Cavalos'),
    ('tr_tw3_m_friends_benefits', 'pg_witcher3_01', 'Friends With Benefits', 'bronze', 'missable', true, false, NULL, 'Velen - Keira Metz'),
    ('tr_tw3_m_gwent_master', 'pg_witcher3_01', 'Gwent Master', 'bronze', 'missable', true, false, NULL, 'Novigrad - Passiflora'),
    ('tr_tw3_m_kingmaker', 'pg_witcher3_01', 'Kingmaker', 'bronze', 'missable', true, false, NULL, 'Skellige - Sucessão'),
    ('tr_tw3_m_woodland_spirit', 'pg_witcher3_01', 'Woodland Spirit', 'bronze', 'missable', true, false, NULL, 'Skellige - Contrato de Bruxo')
ON CONFLICT (player_game_id, trophy_name)
DO UPDATE SET trophy_category = EXCLUDED.trophy_category, is_missable = EXCLUDED.is_missable;

-- Set is_missable = true and trophy_category = 'missable' for all 10 canonical Witcher 3 missables
UPDATE player_trophies
SET is_missable = true, trophy_category = 'missable'
WHERE player_game_id = 'pg_witcher3_01'
  AND trophy_name IN (
    'Assassin of Kings',
    'Card Collector',
    'Even Odds',
    'Fast and Furious',
    'Friends With Benefits',
    'Full Crew',
    'Gwent Master',
    'Kingmaker',
    'The Doppler Effect',
    'Woodland Spirit'
  );

-- Synchronize total_trophies count in player_games for Witcher 3
UPDATE player_games
SET total_trophies = (SELECT COUNT(*) FROM player_trophies WHERE player_game_id = 'pg_witcher3_01')
WHERE id = 'pg_witcher3_01';


-- 2. Grand Theft Auto V (canonical missables)
UPDATE player_trophies
SET is_missable = true, trophy_category = 'missable'
WHERE player_game_id = 'pg_gtav_01'
  AND trophy_name IN (
    'Kifflom! e o Programa Epsilon',
    'Kifflom!',
    'A Lot of Cheddar',
    'Red Mist',
    'Show Off',
    'San Andreas Sightseer',
    'Three Man Army',
    'Three-Man Army'
  );


-- 3. Bloodborne (canonical missables)
UPDATE player_trophies
SET is_missable = true, trophy_category = 'missable'
WHERE trophy_name IN (
    'Hunter''s Essence',
    'Childhood''s Beginning',
    'Yharnam Sunrise',
    'Honoring Wishes'
);


-- 4. Elden Ring (canonical missables)
UPDATE player_trophies
SET is_missable = true, trophy_category = 'missable'
WHERE trophy_name IN (
    'Legendary Armaments',
    'Age of the Stars',
    'Lord of Frenzied Flame',
    'Elden Lord'
);
