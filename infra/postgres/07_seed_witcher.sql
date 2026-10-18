-- Seed player game The Witcher 3: Wild Hunt for olliverW9 (0% completion, 35 unearned trophies)
INSERT INTO players (id, psn_id, email)
VALUES ('ply_olliverw9_01', 'olliverW9', 'olliverw9@platina.ai')
ON CONFLICT (psn_id) DO NOTHING;

INSERT INTO player_games (id, player_id, game_title, platform, total_trophies, unlocked_trophies, platinum_status)
VALUES ('pg_witcher3_01', 'ply_olliverw9_01', 'The Witcher 3: Wild Hunt', 'PS5', 35, 0, 'in_progress')
ON CONFLICT (player_id, game_title, platform) 
DO UPDATE SET total_trophies = EXCLUDED.total_trophies, unlocked_trophies = EXCLUDED.unlocked_trophies, platinum_status = EXCLUDED.platinum_status;

-- Seed Missable Trophies (missable = true, trophy_category = 'missable')
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_tw3_m_01', 'pg_witcher3_01', 'Card Collector', 'silver', 'missable', true, false, NULL, 'Gwent / Velen, Novigrad e Skellige'),
    ('tr_tw3_m_02', 'pg_witcher3_01', 'Full Crew', 'bronze', 'missable', true, false, NULL, 'Kaer Morhen'),
    ('tr_tw3_m_03', 'pg_witcher3_01', 'Assassin of Kings', 'bronze', 'missable', true, false, NULL, 'Novigrad')
ON CONFLICT (player_game_id, trophy_name)
DO UPDATE SET trophy_category = EXCLUDED.trophy_category, is_missable = EXCLUDED.is_missable, is_unlocked = EXCLUDED.is_unlocked;

-- Seed Natural Grind Trophies (trophy_category = 'natural_grind')
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_tw3_ng_01', 'pg_witcher3_01', 'Humpty Dumpty', 'bronze', 'natural_grind', false, false, NULL, 'Velen - Fossa do Diabo'),
    ('tr_tw3_ng_02', 'pg_witcher3_01', 'That Is the Evilest Thing', 'bronze', 'natural_grind', false, false, NULL, 'Geral - Igni + Sonho do Dragão')
ON CONFLICT (player_game_id, trophy_name)
DO UPDATE SET trophy_category = EXCLUDED.trophy_category, is_missable = EXCLUDED.is_missable, is_unlocked = EXCLUDED.is_unlocked;

-- Seed Quick Cleanup Trophies (trophy_category = 'quick_cleanup')
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_tw3_qc_01', 'pg_witcher3_01', 'Brawler', 'bronze', 'quick_cleanup', false, false, NULL, 'Lutas de rua em Velen, Novigrad e Skellige'),
    ('tr_tw3_qc_02', 'pg_witcher3_01', 'Fist of the South Star', 'bronze', 'quick_cleanup', false, false, NULL, 'Skellige')
ON CONFLICT (player_game_id, trophy_name)
DO UPDATE SET trophy_category = EXCLUDED.trophy_category, is_missable = EXCLUDED.is_missable, is_unlocked = EXCLUDED.is_unlocked;

-- Seed Heavy Grind Trophies (trophy_category = 'heavy_grind')
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_tw3_hg_01', 'pg_witcher3_01', 'Walked the Demon''s Path', 'gold', 'heavy_grind', false, false, NULL, 'Dificuldade Marcha da Morte'),
    ('tr_tw3_hg_02', 'pg_witcher3_01', 'Ran the Gauntlet', 'silver', 'heavy_grind', false, false, NULL, 'Dificuldade Sangue e Glória')
ON CONFLICT (player_game_id, trophy_name)
DO UPDATE SET trophy_category = EXCLUDED.trophy_category, is_missable = EXCLUDED.is_missable, is_unlocked = EXCLUDED.is_unlocked;

-- Seed Standard Trophies (trophy_category = 'standard', completing the 35 unearned catalog)
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_tw3_std_01', 'pg_witcher3_01', 'Lilac and Gooseberries', 'bronze', 'standard', false, false, NULL, 'Pomar Branco'),
    ('tr_tw3_std_02', 'pg_witcher3_01', 'A Friend in Need', 'bronze', 'standard', false, false, NULL, 'Novigrad'),
    ('tr_tw3_std_03', 'pg_witcher3_01', 'Necromancer', 'bronze', 'standard', false, false, NULL, 'Skellige'),
    ('tr_tw3_std_04', 'pg_witcher3_01', 'Family Counselor', 'bronze', 'standard', false, false, NULL, 'Velen'),
    ('tr_tw3_std_05', 'pg_witcher3_01', 'Something More', 'bronze', 'standard', false, false, NULL, 'Kaer Morhen'),
    ('tr_tw3_std_06', 'pg_witcher3_01', 'Xenonaut', 'bronze', 'standard', false, false, NULL, 'Tir ná Lia'),
    ('tr_tw3_std_07', 'pg_witcher3_01', 'Passed the Trial', 'bronze', 'standard', false, false, NULL, 'Kaer Morhen'),
    ('tr_tw3_std_08', 'pg_witcher3_01', 'The King is Dead', 'bronze', 'standard', false, false, NULL, 'Skellige'),
    ('tr_tw3_std_09', 'pg_witcher3_01', 'Geralt: The Professional', 'bronze', 'standard', false, false, NULL, 'Contratos de Bruxo'),
    ('tr_tw3_std_10', 'pg_witcher3_01', 'Dendrologist', 'bronze', 'standard', false, false, NULL, 'Habilidades'),
    ('tr_tw3_std_11', 'pg_witcher3_01', 'Armed and Dangerous', 'bronze', 'standard', false, false, NULL, 'Equipamento de Bruxo'),
    ('tr_tw3_std_12', 'pg_witcher3_01', 'Can''t Touch This!', 'bronze', 'standard', false, false, NULL, 'Combate'),
    ('tr_tw3_std_13', 'pg_witcher3_01', 'Bookworm', 'bronze', 'standard', false, false, NULL, 'Livros e Manuscritos'),
    ('tr_tw3_std_14', 'pg_witcher3_01', 'Rad Steez, Bro!', 'bronze', 'standard', false, false, NULL, 'Montanhas de Skellige'),
    ('tr_tw3_std_15', 'pg_witcher3_01', 'Pest Control', 'bronze', 'standard', false, false, NULL, 'Ninhos de Monstros'),
    ('tr_tw3_std_16', 'pg_witcher3_01', 'Fire in the Hole', 'bronze', 'standard', false, false, NULL, 'Ninhos de Monstros'),
    ('tr_tw3_std_17', 'pg_witcher3_01', 'The Doppler Effect', 'bronze', 'standard', false, false, NULL, 'Novigrad'),
    ('tr_tw3_std_18', 'pg_witcher3_01', 'In Wolf''s Clothing', 'bronze', 'standard', false, false, NULL, 'Jardim de Freya, Skellige'),
    ('tr_tw3_std_19', 'pg_witcher3_01', 'Shrieker', 'bronze', 'standard', false, false, NULL, 'Poleiro do Corvo, Velen'),
    ('tr_tw3_std_20', 'pg_witcher3_01', 'Fearless Vampire Slayer', 'bronze', 'standard', false, false, NULL, 'Novigrad'),
    ('tr_tw3_std_21', 'pg_witcher3_01', 'Woody Woodpecker', 'bronze', 'standard', false, false, NULL, 'Combate com Besta'),
    ('tr_tw3_std_22', 'pg_witcher3_01', 'Munchkin', 'gold', 'standard', false, false, NULL, 'Nível de Personagem'),
    ('tr_tw3_std_23', 'pg_witcher3_01', 'Overkill', 'silver', 'standard', false, false, NULL, 'Combate'),
    ('tr_tw3_std_24', 'pg_witcher3_01', 'Triple Threat', 'bronze', 'standard', false, false, NULL, 'Combate'),
    ('tr_tw3_std_25', 'pg_witcher3_01', 'What Was That?', 'bronze', 'standard', false, false, NULL, 'Contra-ataque'),
    ('tr_tw3_plat',   'pg_witcher3_01', 'The Limits of the Possible', 'platinum', 'standard', false, false, NULL, 'Geral')
ON CONFLICT (player_game_id, trophy_name)
DO UPDATE SET trophy_category = EXCLUDED.trophy_category, is_missable = EXCLUDED.is_missable, is_unlocked = EXCLUDED.is_unlocked;
