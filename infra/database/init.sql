CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('CITIZEN', 'DRIVER', 'ADMIN')),
    eco_points INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE complaints (
    id SERIAL PRIMARY KEY,
    citizen_id INTEGER REFERENCES users(id),
    zone VARCHAR(100),
    area VARCHAR(100),
    ward VARCHAR(100),
    location GEOMETRY(Point, 4326),
    image_url TEXT,
    waste_type VARCHAR(50), -- Plastic, Organic, Mixed
    garbage_size VARCHAR(50),
    severity_level VARCHAR(50), -- Low, Medium, Critical
    health_risk_score DECIMAL(5, 2),
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assigned_routes (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER REFERENCES users(id),
    complaint_id INTEGER REFERENCES complaints(id),
    status VARCHAR(50) DEFAULT 'ASSIGNED',
    pickup_photo_url TEXT,
    pickup_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE driver_metrics (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER REFERENCES users(id),
    punctuality_score DECIMAL(5, 2) DEFAULT 100.0,
    fuel_efficiency_score DECIMAL(5, 2) DEFAULT 100.0,
    resolution_rate DECIMAL(5, 2) DEFAULT 100.0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Default Admin Account (password: admin123)
INSERT INTO users (name, email, password_hash, role, eco_points) 
VALUES ('Super Admin', 'admin@scos.gov', '$2b$12$qJ3vE8S0.U5A3Qn.Y9k1.OxR5p3z1Y.hF.q3S1X.O6lY1.Y1Y1Y1Y', 'ADMIN', 0);

-- Default Citizen Account (password: citizen123)
INSERT INTO users (name, email, password_hash, role, eco_points) 
VALUES ('Rahul Test', 'citizen@city.com', '$2b$12$qJ3vE8S0.U5A3Qn.Y9k1.OxR5p3z1Y.hF.q3S1X.O6lY1.Y1Y1Y1Y', 'CITIZEN', 150);

-- Default Driver Account (password: driver123)
INSERT INTO users (name, email, password_hash, role, eco_points)
VALUES ('Driver John', 'driver@fleet.com', '$2b$12$qJ3vE8S0.U5A3Qn.Y9k1.OxR5p3z1Y.hF.q3S1X.O6lY1.Y1Y1Y1Y', 'DRIVER', 0);
