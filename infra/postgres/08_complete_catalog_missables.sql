-- Migration 08: Synchronize complete canonical community missables across all games in catalog

-- 1. Grand Theft Auto V (canonical missables)
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


-- 2. Bloodborne (canonical missables)
UPDATE player_trophies
SET is_missable = true, trophy_category = 'missable'
WHERE trophy_name IN (
    'Hunter''s Essence',
    'Childhood''s Beginning',
    'Yharnam Sunrise',
    'Honoring Wishes'
);


-- 3. Elden Ring (canonical missables)
UPDATE player_trophies
SET is_missable = true, trophy_category = 'missable'
WHERE trophy_name IN (
    'Legendary Armaments',
    'Age of the Stars',
    'Lord of Frenzied Flame',
    'Elden Lord'
);
