-- Database setup for SCOS
CREATE EXTENSION IF NOT EXISTS postgis;

-- ===================== CORE TABLES =====================

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL, -- CITIZEN, DRIVER, ADMIN
    eco_points INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS complaints (
    id SERIAL PRIMARY KEY,
    citizen_id INTEGER REFERENCES users(id),
    zone VARCHAR(100),
    area VARCHAR(100),
    waste_type VARCHAR(100),
    severity_level VARCHAR(50),
    status VARCHAR(50) DEFAULT 'PENDING',
    image_url TEXT,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS driver_locations (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER REFERENCES users(id),
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===================== NEW TABLES =====================

-- Rewards catalog
CREATE TABLE IF NOT EXISTS rewards (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    provider VARCHAR(255),
    category VARCHAR(100),
    points_cost INTEGER NOT NULL,
    image_url TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Reward redemptions
CREATE TABLE IF NOT EXISTS reward_redemptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    reward_id INTEGER REFERENCES rewards(id),
    redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Driver task assignments (links drivers to complaints)
CREATE TABLE IF NOT EXISTS driver_tasks (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER REFERENCES users(id),
    complaint_id INTEGER REFERENCES complaints(id),
    priority VARCHAR(20) DEFAULT 'MEDIUM',
    waste_type VARCHAR(100),
    address VARCHAR(255),
    bin_fill_percent INTEGER DEFAULT 50,
    distance_km FLOAT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'ASSIGNED',
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Illegal dumping incidents
CREATE TABLE IF NOT EXISTS dumping_incidents (
    id SERIAL PRIMARY KEY,
    zone VARCHAR(100),
    cluster_id VARCHAR(50),
    description TEXT,
    severity VARCHAR(20) DEFAULT 'MEDIUM',
    predicted_culprit VARCHAR(255),
    common_time VARCHAR(100),
    confidence FLOAT DEFAULT 0,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    status VARCHAR(50) DEFAULT 'ACTIVE',
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dispatched_at TIMESTAMP
);

-- Contractor companies
CREATE TABLE IF NOT EXISTS contractors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    completion_rate FLOAT DEFAULT 0,
    satisfaction_score FLOAT DEFAULT 0,
    response_time_hours FLOAT DEFAULT 0,
    active_drivers INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===================== SEED DATA =====================

-- Users (password: "password" for all)
INSERT INTO users (name, email, password_hash, role, eco_points)
VALUES 
    ('Citizen John', 'citizen@city.com', '$2b$12$R.SjA80b4jOTmR1sCq0dGu3w81.mS.I35e.jU8rT7y7Xv.vQ7T./W', 'CITIZEN', 1240),
    ('Driver Dave', 'driver@city.com', '$2b$12$R.SjA80b4jOTmR1sCq0dGu3w81.mS.I35e.jU8rT7y7Xv.vQ7T./W', 'DRIVER', 0),
    ('Admin Alice', 'admin@city.com', '$2b$12$R.SjA80b4jOTmR1sCq0dGu3w81.mS.I35e.jU8rT7y7Xv.vQ7T./W', 'ADMIN', 0),
    ('Elena Santos', 'elena@city.com', '$2b$12$R.SjA80b4jOTmR1sCq0dGu3w81.mS.I35e.jU8rT7y7Xv.vQ7T./W', 'CITIZEN', 2410),
    ('Marcus Reed', 'marcus@city.com', '$2b$12$R.SjA80b4jOTmR1sCq0dGu3w81.mS.I35e.jU8rT7y7Xv.vQ7T./W', 'CITIZEN', 2185),
    ('Sarah Kim', 'sarah@city.com', '$2b$12$R.SjA80b4jOTmR1sCq0dGu3w81.mS.I35e.jU8rT7y7Xv.vQ7T./W', 'CITIZEN', 1940)
ON CONFLICT (email) DO NOTHING;

-- Rewards catalog
INSERT INTO rewards (title, provider, category, points_cost, image_url) VALUES
    ('Free Oat Latte', 'The Green Bean', 'LOCAL_SHOP', 450, 'https://lh3.googleusercontent.com/aida-public/AB6AXuDsMnCTZR9dq1_Dffs3O-4vc_Ae-UjP19BnWlJpAEvBNXWCY89M-CYOeu1srWAXsWyCt98q_X0aYUTCerhrRXOf4mv-kSd73BZPvMKOXG5_aj_y2HCd9D6ctqjQx6W8nWtffwKbJpatjZcrrezGWxypflYSjeXLEWoIjErc1s3RH8W1A9F4DU18YTzw1y2BeN0oJYzwdwcKFSfI0SyTPxmg3QjuvkFqM_e5ZpUY0bJs9-jQb9N58U4gJObpNSZZFEQZkrB3C0wuYz0x'),
    ('Botanic Garden Pass', 'City Parks Dept', 'PUBLIC_SERVICE', 800, 'https://lh3.googleusercontent.com/aida-public/AB6AXuBGJg8R-5zq-5XjFD8eqhidXrfI8VW0Rv7DgQSA8zH8wPFM7o9a_roDWLaUK3wAm7-FJ1n7vy2-EkyohXVHXc1Jf6td69d1bABwbU8NSbpUjEF43W4WTq676ejrdFX2_ivULWrnNC12OfeR6OUVRtk-if0fY_OOUTDVp3gGMmyZh3z-MSiG6hBqkfq21_xaNqycPCpbx6-Awfh19s-XiiaFV94ZYX0L_G7AYX5hfPKlQe_3ooopglGnuje5nT6dQTG15qZ5WX-MiZ3u'),
    ('15% Off Organic Box', 'Farm-to-Door', 'DISCOUNT', 300, 'https://lh3.googleusercontent.com/aida-public/AB6AXuA6-D8_U6KC8anRi_dhyBmXhNo0aXlXD7sXt5q8RPpPG9z3Ghq3zojIqSdlydPFFVxibzIdw8IekbYK4c2z2OoxNzPTm2LiKfZn2lcJB2W3yqI2j4KiuVLn9fnf-y8ER8ZycNAIzxZMekhz0kFKN2HZi_ANdQcvsGbZ25mWTsslT2RuST4U9I-EQgVIsGSUzgCnTYLVH1L11feUXm63cf90o3E10hvZvromfSr6etcKyTXJT3fjcxSyeUZnXuRiSLpgKAEy24q32cL0'),
    ('Weekly Transit Pass', 'Metro Transit', 'TRANSPORT', 1500, 'https://lh3.googleusercontent.com/aida-public/AB6AXuDGBq2DVPMh8YCOjlZyzmoeh3cKijdTqqLwIh3AWwN-8_eqSw075TI7lH4J6eFRqjOzmJsL-OxxiUFNf-dQIGi-mVwhEoZZVT53FWR1v7-mK53j_VJ_Fw07aAwqwOQ5FOelojJYK_5uSOBopJJjoA5UBF9mrAo3Tvy8jrvKvMnPx-X5UKlBbfCREiBBQYRGD35Ogph7kRQgDy6IojY_UOHueyg0IWnM1sh5XOfUy5isQpwSRQOJr8NTqabjcFw60Z-CSlB7qpL7NrMp')
ON CONFLICT DO NOTHING;

-- Contractors
INSERT INTO contractors (name, completion_rate, satisfaction_score, response_time_hours, active_drivers) VALUES
    ('CityClean Solutions', 99.8, 4.92, 1.8, 4),
    ('North-Link Logistics', 97.2, 4.85, 2.1, 3),
    ('EcoWaste Services', 95.4, 4.78, 2.8, 3),
    ('UrbanOps Inc', 88.0, 4.52, 3.2, 2),
    ('Global Enviro', 91.5, 4.65, 2.6, 2)
ON CONFLICT DO NOTHING;

-- Sample dumping incidents
INSERT INTO dumping_incidents (zone, cluster_id, description, severity, predicted_culprit, common_time, confidence, lat, lng) VALUES
    ('Mission District', '#412', 'Multiple unauthorized disposals at perimeter', 'HIGH', 'Private Contractors', '02:00 AM - 04:00 AM', 0.85, 37.7599, -122.4148),
    ('Downtown Sector 4', '#208', 'Construction debris in residential zone', 'MEDIUM', 'Unknown', '11:00 PM - 01:00 AM', 0.62, 37.7749, -122.4194),
    ('Riverside Walk', '#315', 'Repeated waste dumping near waterway', 'HIGH', 'Commercial Outlets', '03:00 AM - 05:00 AM', 0.78, 37.7849, -122.3894),
    ('Harbor View', '#501', 'Minor illegal disposal detected', 'LOW', 'Residential', '06:00 PM - 08:00 PM', 0.45, 37.7699, -122.3994)
ON CONFLICT DO NOTHING;

-- Sample complaints for testing
INSERT INTO complaints (citizen_id, zone, area, waste_type, severity_level, status, lat, lng) VALUES
    (1, 'Downtown', 'Sector 4', 'Plastic', 'High', 'IN_PROGRESS', 37.7749, -122.4194),
    (1, 'Greenwood', 'Avenue', 'Construction', 'Medium', 'PENDING', 37.7649, -122.4094),
    (1, 'Oak Ridge', 'Estates', 'Recyclable', 'Low', 'RESOLVED', 37.7549, -122.3994)
ON CONFLICT DO NOTHING;

-- Sample driver tasks
INSERT INTO driver_tasks (driver_id, complaint_id, priority, waste_type, address, bin_fill_percent, distance_km, status) VALUES
    (2, 1, 'HIGH', 'Bio-Waste', '882 Oakwood Dr, South Plaza', 95, 0.4, 'ASSIGNED'),
    (2, 2, 'MEDIUM', 'Recyclables', 'Central Station B-Wing', 78, 2.1, 'ASSIGNED'),
    (2, 3, 'LOW', 'General', 'Harbor View Condos', 62, 4.8, 'ASSIGNED')
ON CONFLICT DO NOTHING;

-- ===================== INDEXES FOR SCALABILITY =====================
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_citizen ON complaints(citizen_id);
CREATE INDEX IF NOT EXISTS idx_driver_tasks_driver ON driver_tasks(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_tasks_status ON driver_tasks(status);
CREATE INDEX IF NOT EXISTS idx_dumping_incidents_status ON dumping_incidents(status);
CREATE INDEX IF NOT EXISTS idx_driver_locations_driver ON driver_locations(driver_id);

