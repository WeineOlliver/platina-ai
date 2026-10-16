-- Seed a sample player profile for agent testing
INSERT INTO players (id, psn_id, email)
VALUES ('ply_hunter_01', 'OlliverHunter', 'hunter@platina.ai')
ON CONFLICT (psn_id) DO NOTHING;

-- Seed player games (Bloodborne and Elden Ring)
INSERT INTO player_games (id, player_id, game_title, platform, total_trophies, unlocked_trophies, platinum_status)
VALUES 
    ('pg_bb_01', 'ply_hunter_01', 'Bloodborne', 'PS4', 34, 28, 'in_progress'),
    ('pg_er_01', 'ply_hunter_01', 'Elden Ring', 'PS5', 42, 35, 'in_progress')
ON CONFLICT (player_id, game_title, platform) DO NOTHING;

-- Seed Bloodborne trophies (showing the player defeated Cleric Beast & Gascoigne, but Eileen is still pending!)
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_bb_01', 'pg_bb_01', 'Fera Clérigo', 'bronze', false, true, CURRENT_TIMESTAMP - INTERVAL '10 days', 'Central Yharnam'),
    ('tr_bb_02', 'pg_bb_01', 'Padre Gascoigne', 'bronze', false, true, CURRENT_TIMESTAMP - INTERVAL '9 days', 'Cemitério de Yharnam'),
    ('tr_bb_03', 'pg_bb_01', 'Vigário Amélia', 'bronze', false, true, CURRENT_TIMESTAMP - INTERVAL '7 days', 'Distrito da Catedral'),
    ('tr_bb_04', 'pg_bb_01', 'Amigo dos Corvos (Eileen the Crow)', 'bronze', true, false, NULL, 'Distrito da Catedral / Lua Vermelha'),
    ('tr_bb_05', 'pg_bb_01', 'Todos os Armamentos do Caçador', 'ouro', true, false, NULL, 'Diversas localizações'),
    ('tr_bb_06', 'pg_bb_01', 'Origem de Bloodborne (Platina)', 'platina', false, false, NULL, 'Geral')
ON CONFLICT (player_game_id, trophy_name) DO NOTHING;

-- Seed Elden Ring trophies (showing Bolt of Gransax still pending before Maliketh!)
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_er_01', 'pg_er_01', 'Margit, o Agouro Caído', 'bronze', false, true, CURRENT_TIMESTAMP - INTERVAL '15 days', 'Castelo Tempesvéu'),
    ('tr_er_02', 'pg_er_01', 'Godrick, o Enxertado', 'bronze', false, true, CURRENT_TIMESTAMP - INTERVAL '14 days', 'Castelo Tempesvéu'),
    ('tr_er_03', 'pg_er_01', 'Rennala, Rainha da Lua Cheia', 'bronze', false, true, CURRENT_TIMESTAMP - INTERVAL '12 days', 'Academia de Raya Lucaria'),
    ('tr_er_04', 'pg_er_01', 'Armamentos Lendários (Lança de Gransax)', 'ouro', true, false, NULL, 'Leyndell, Capital Real'),
    ('tr_er_05', 'pg_er_01', 'Lorde Prístino (Platina)', 'platina', false, false, NULL, 'Geral')
ON CONFLICT (player_game_id, trophy_name) DO NOTHING;
