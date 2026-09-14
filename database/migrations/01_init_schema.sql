-- Migration 01: Initialize Schema for Neon DB (PostgreSQL)

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(20) DEFAULT 'resident' CHECK (role IN ('admin', 'resident')) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Face encodings table (stores 128-dimensional vectors as double precision arrays)
CREATE TABLE IF NOT EXISTS face_encodings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    encoding DOUBLE PRECISION[] NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- RFID card associations
CREATE TABLE IF NOT EXISTS rfid_cards (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    card_uid VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Per-user Floor Permissions
CREATE TABLE IF NOT EXISTS floor_permissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    floor INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    UNIQUE (user_id, floor)
);

-- Visitor OTPs (valid for 30 minutes, specific to floor list)
CREATE TABLE IF NOT EXISTS visitor_otps (
    id SERIAL PRIMARY KEY,
    otp_code VARCHAR(6) NOT NULL,
    requested_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    allowed_floors INTEGER[] NOT NULL,
    is_used BOOLEAN DEFAULT FALSE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Authentication Logs (REQ-38, REQ-39)
CREATE TABLE IF NOT EXISTS auth_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    username VARCHAR(50) NOT NULL,
    method VARCHAR(20) NOT NULL CHECK (method IN ('face', 'rfid', 'otp', 'password')),
    result VARCHAR(50) NOT NULL
);

-- Elevator Access Logs (REQ-40, REQ-41)
CREATE TABLE IF NOT EXISTS access_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    username VARCHAR(50) NOT NULL,
    floor INTEGER NOT NULL,
    result VARCHAR(20) NOT NULL CHECK (result IN ('granted', 'denied'))
);
