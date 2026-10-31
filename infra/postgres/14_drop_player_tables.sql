-- Migration 14: Drop deprecated player tracking tables if they exist
DROP TABLE IF EXISTS player_trophies CASCADE;
DROP TABLE IF EXISTS player_games CASCADE;
DROP TABLE IF EXISTS players CASCADE;
