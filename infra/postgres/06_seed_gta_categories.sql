-- Seed player profile for olliverW9 (GTA V post-campaign player)
INSERT INTO players (id, psn_id, email)
VALUES ('ply_olliverw9_01', 'olliverW9', 'olliverw9@platina.ai')
ON CONFLICT (psn_id) DO NOTHING;

-- Seed player game Grand Theft Auto V
INSERT INTO player_games (id, player_id, game_title, platform, total_trophies, unlocked_trophies, platinum_status)
VALUES ('pg_gtav_01', 'ply_olliverw9_01', 'Grand Theft Auto V', 'PS5', 49, 35, 'in_progress')
ON CONFLICT (player_id, game_title, platform) DO NOTHING;

-- Seed unlocked story and standard trophies (completed campaign, 35 unlocked = ~71.4% progress)
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_gta_01', 'pg_gtav_01', 'Welcome to Los Santos', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '30 days', 'Prologue'),
    ('tr_gta_02', 'pg_gtav_01', 'A Friendship Resurrected', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '28 days', 'Story'),
    ('tr_gta_03', 'pg_gtav_01', 'A Fair Day''s Pay', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '26 days', 'Story'),
    ('tr_gta_04', 'pg_gtav_01', 'The Moment of Truth', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '24 days', 'Story'),
    ('tr_gta_05', 'pg_gtav_01', 'Diamond Hard', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '22 days', 'Story'),
    ('tr_gta_06', 'pg_gtav_01', 'Subversive', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '20 days', 'Story'),
    ('tr_gta_07', 'pg_gtav_01', 'Blitzed', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '18 days', 'Story'),
    ('tr_gta_08', 'pg_gtav_01', 'Small Town, Big Job', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '16 days', 'Story'),
    ('tr_gta_09', 'pg_gtav_01', 'The Government Gimps', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '14 days', 'Story'),
    ('tr_gta_10', 'pg_gtav_01', 'The Big One!', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '12 days', 'Story'),
    ('tr_gta_11', 'pg_gtav_01', 'Solid Gold, Baby!', 'gold', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '10 days', 'Story'),
    ('tr_gta_12', 'pg_gtav_01', 'All''s Fare in Love and War', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '9 days', 'Side Quests'),
    ('tr_gta_13', 'pg_gtav_01', 'TP Industries Arms Race', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '9 days', 'Side Quests'),
    ('tr_gta_14', 'pg_gtav_01', 'From Beyond the Stars', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '8 days', 'Collectibles'),
    ('tr_gta_15', 'pg_gtav_01', 'A Mystery, Solved', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '8 days', 'Collectibles'),
    ('tr_gta_16', 'pg_gtav_01', 'Waste Management', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '7 days', 'Collectibles'),
    ('tr_gta_17', 'pg_gtav_01', 'Red Mist', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '7 days', 'Rampages'),
    ('tr_gta_18', 'pg_gtav_01', 'Show Off', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '6 days', 'Stunt Jumps'),
    ('tr_gta_19', 'pg_gtav_01', 'Kifflom!', 'silver', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '6 days', 'Epsilon Program'),
    ('tr_gta_20', 'pg_gtav_01', 'Three-Man Army', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '5 days', 'Free Roam'),
    ('tr_gta_21', 'pg_gtav_01', 'Out of Your Depth', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '5 days', 'Free Roam'),
    ('tr_gta_22', 'pg_gtav_01', 'Altruist Acolyte', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '4 days', 'Side Quests'),
    ('tr_gta_23', 'pg_gtav_01', 'A Lot of Cheddar', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '4 days', 'Investments'),
    ('tr_gta_24', 'pg_gtav_01', 'Trading Pure Alpha', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '3 days', 'Stock Market'),
    ('tr_gta_25', 'pg_gtav_01', 'Pimp My Sidearm', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '3 days', 'Ammu-Nation'),
    ('tr_gta_26', 'pg_gtav_01', 'Clean Sweep', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '2 days', 'Gang Attacks'),
    ('tr_gta_27', 'pg_gtav_01', 'San Andreas Sightseer', 'silver', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '2 days', 'Exploration'),
    ('tr_gta_28', 'pg_gtav_01', 'Career Criminal', 'gold', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '1 day', '100% Completion'),
    ('tr_gta_29', 'pg_gtav_01', 'Off the Plane', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '20 days', 'GTA Online'),
    ('tr_gta_30', 'pg_gtav_01', 'Three-Bit Gangster', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '18 days', 'GTA Online'),
    ('tr_gta_31', 'pg_gtav_01', 'Making Moves', 'silver', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '15 days', 'GTA Online'),
    ('tr_gta_32', 'pg_gtav_01', 'Above the Law', 'gold', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '10 days', 'GTA Online'),
    ('tr_gta_33', 'pg_gtav_01', 'Full Refund', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '8 days', 'GTA Online'),
    ('tr_gta_34', 'pg_gtav_01', 'Dialling Digits', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '7 days', 'GTA Online'),
    ('tr_gta_35', 'pg_gtav_01', 'Stick Up Kid', 'bronze', 'standard', false, true, CURRENT_TIMESTAMP - INTERVAL '6 days', 'GTA Online')
ON CONFLICT (player_game_id, trophy_name) 
DO UPDATE SET trophy_category = EXCLUDED.trophy_category, is_unlocked = EXCLUDED.is_unlocked;

-- Seed pending Director Mode trophies (categorized as quick_cleanup)
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_gta_qc_01', 'pg_gtav_01', 'Vinewood Visionary', 'bronze', 'quick_cleanup', false, false, NULL, 'Director Mode'),
    ('tr_gta_qc_02', 'pg_gtav_01', 'Majestic', 'bronze', 'quick_cleanup', false, false, NULL, 'Director Mode'),
    ('tr_gta_qc_03', 'pg_gtav_01', 'Humans of Los Santos', 'bronze', 'quick_cleanup', false, false, NULL, 'Director Mode'),
    ('tr_gta_qc_04', 'pg_gtav_01', 'Animal Lover', 'bronze', 'quick_cleanup', false, false, NULL, 'Director Mode'),
    ('tr_gta_qc_05', 'pg_gtav_01', 'Ensemble Piece', 'bronze', 'quick_cleanup', false, false, NULL, 'Director Mode'),
    ('tr_gta_qc_06', 'pg_gtav_01', 'Cult Movie', 'bronze', 'quick_cleanup', false, false, NULL, 'Director Mode'),
    ('tr_gta_qc_07', 'pg_gtav_01', 'Location Scout', 'bronze', 'quick_cleanup', false, false, NULL, 'Director Mode'),
    ('tr_gta_qc_08', 'pg_gtav_01', 'Method Actor', 'bronze', 'quick_cleanup', false, false, NULL, 'Director Mode'),
    ('tr_gta_qc_09', 'pg_gtav_01', 'Cryptozoologist', 'gold', 'quick_cleanup', false, false, NULL, 'Director Mode')
ON CONFLICT (player_game_id, trophy_name) 
DO UPDATE SET trophy_category = EXCLUDED.trophy_category, is_unlocked = EXCLUDED.is_unlocked;

-- Seed pending Heists / Doomsday trophies (categorized as heavy_grind)
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_gta_hg_01', 'pg_gtav_01', 'Live a Little', 'bronze', 'heavy_grind', false, false, NULL, 'Heists Update'),
    ('tr_gta_hg_02', 'pg_gtav_01', 'Mastermind', 'bronze', 'heavy_grind', false, false, NULL, 'Heists Update'),
    ('tr_gta_hg_03', 'pg_gtav_01', 'Masterminds', 'gold', 'heavy_grind', false, false, NULL, 'The Doomsday Heist'),
    ('tr_gta_hg_04', 'pg_gtav_01', 'Elitist', 'silver', 'heavy_grind', false, false, NULL, 'The Doomsday Heist')
ON CONFLICT (player_game_id, trophy_name) 
DO UPDATE SET trophy_category = EXCLUDED.trophy_category, is_unlocked = EXCLUDED.is_unlocked;

-- Seed overall Platinum trophy
INSERT INTO player_trophies (id, player_game_id, trophy_name, trophy_type, trophy_category, is_missable, is_unlocked, unlocked_at, chapter_or_location)
VALUES
    ('tr_gta_plat', 'pg_gtav_01', 'Los Santos Legend', 'platinum', 'standard', false, false, NULL, 'Los Santos')
ON CONFLICT (player_game_id, trophy_name) 
DO UPDATE SET trophy_category = EXCLUDED.trophy_category, is_unlocked = EXCLUDED.is_unlocked;
