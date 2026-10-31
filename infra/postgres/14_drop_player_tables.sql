-- Migration 14: Drop player tables and rename catalog trophy column to remove PSN account references
ALTER TABLE IF EXISTS trophies RENAME COLUMN psn_trophy_id TO psnprofiles_trophy_id;
DROP TABLE IF EXISTS player_trophies CASCADE;
DROP TABLE IF EXISTS player_games CASCADE;
DROP TABLE IF EXISTS players CASCADE;
