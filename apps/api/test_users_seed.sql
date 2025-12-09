-- Test Users for Local Testing
-- Password for all users: Test@123
-- Hash: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5QE7B5LG5jKBa

-- 1. Test Patient User
INSERT INTO "user" (
    email, 
    password_hash, 
    full_name, 
    phone_number, 
    role, 
    is_active, 
    created_at
) VALUES (
    'patient@test.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5QE7B5LG5jKBa',
    'John Patient',
    '9876543210',
    'PATIENT',
    true,
    NOW()
) ON CONFLICT (email) DO NOTHING;

-- Get the patient user ID and create patient profile
DO $$
DECLARE
    patient_user_id INTEGER;
BEGIN
    SELECT id INTO patient_user_id FROM "user" WHERE email = 'patient@test.com';
    
    IF patient_user_id IS NOT NULL THEN
        INSERT INTO patientprofile (
            user_id,
            date_of_birth,
            blood_group,
            emergency_contact_name,
            emergency_contact_phone,
            allergies,
            medical_conditions
        ) VALUES (
            patient_user_id,
            '1990-01-15',
            'O+',
            'Jane Patient',
            '9876543211',
            'None',
            'No significant medical history'
        ) ON CONFLICT (user_id) DO NOTHING;
    END IF;
END $$;

-- 2. Test Doctor User
INSERT INTO "user" (
    email, 
    password_hash, 
    full_name, 
    phone_number, 
    role, 
    is_active, 
    created_at
) VALUES (
    'doctor@test.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5QE7B5LG5jKBa', -- Test@123
    'Dr. Sarah Smith',
    '9876543220',
    'doctor',
    true,
    NOW()
) ON CONFLICT (email) DO NOTHING;

-- Get the doctor user ID and create doctor profile
DO $$
DECLARE
    doctor_user_id INTEGER;
BEGIN
    SELECT id INTO doctor_user_id FROM "user" WHERE email = 'doctor@test.com';
    
    IF doctor_user_id IS NOT NULL THEN
        INSERT INTO doctorprofile (
            user_id,
            specialization,
            license_number,
            years_of_experience,
            qualification,
            consultation_fee,
            bio,
            is_verified,
            is_online,
            average_rating,
            total_consultations
        ) VALUES (
            doctor_user_id,
            'General Physician',
            'MH-12345-2020',
            8,
            'MBBS, MD (General Medicine)',
            500.00,
            'Experienced general physician with focus on preventive care and chronic disease management.',
            true,
            true,
            4.5,
            25
        ) ON CONFLICT (user_id) DO NOTHING;
    END IF;
END $$;

-- 3. Test Admin User
INSERT INTO "user" (
    email, 
    password_hash, 
    full_name, 
    phone_number, 
    role, 
    is_active, 
    created_at
) VALUES (
    'admin@test.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5QE7B5LG5jKBa', -- Test@123
    'Admin User',
    '9876543230',
    'admin',
    true,
    NOW()
) ON CONFLICT (email) DO NOTHING;

-- 4. Additional Test Doctor (Cardiologist)
INSERT INTO "user" (
    email, 
    password_hash, 
    full_name, 
    phone_number, 
    role, 
    is_active, 
    created_at
) VALUES (
    'cardiologist@test.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5QE7B5LG5jKBa', -- Test@123
    'Dr. Rajesh Kumar',
    '9876543240',
    'doctor',
    true,
    NOW()
) ON CONFLICT (email) DO NOTHING;

DO $$
DECLARE
    cardio_user_id INTEGER;
BEGIN
    SELECT id INTO cardio_user_id FROM "user" WHERE email = 'cardiologist@test.com';
    
    IF cardio_user_id IS NOT NULL THEN
        INSERT INTO doctorprofile (
            user_id,
            specialization,
            license_number,
            years_of_experience,
            qualification,
            consultation_fee,
            bio,
            is_verified,
            is_online,
            average_rating,
            total_consultations
        ) VALUES (
            cardio_user_id,
            'Cardiologist',
            'MH-67890-2015',
            12,
            'MBBS, MD (Cardiology), DM (Interventional Cardiology)',
            1000.00,
            'Senior cardiologist specializing in preventive cardiology and heart disease management.',
            true,
            true,
            4.8,
            50
        ) ON CONFLICT (user_id) DO NOTHING;
    END IF;
END $$;

-- 5. Additional Test Patient
INSERT INTO "user" (
    email, 
    password_hash, 
    full_name, 
    phone_number, 
    role, 
    is_active, 
    created_at
) VALUES (
    'patient2@test.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5QE7B5LG5jKBa', -- Test@123
    'Mary Johnson',
    '9876543250',
    'patient',
    true,
    NOW()
) ON CONFLICT (email) DO NOTHING;

DO $$
DECLARE
    patient2_user_id INTEGER;
BEGIN
    SELECT id INTO patient2_user_id FROM "user" WHERE email = 'patient2@test.com';
    
    IF patient2_user_id IS NOT NULL THEN
        INSERT INTO patientprofile (
            user_id,
            date_of_birth,
            blood_group,
            emergency_contact_name,
            emergency_contact_phone,
            medical_conditions,
            allergies
        ) VALUES (
            patient2_user_id,
            '1985-05-20',
            'A+',
            'Robert Johnson',
            '9876543251',
            'Hypertension (controlled with medication)',
            'Penicillin'
        ) ON CONFLICT (user_id) DO NOTHING;
    END IF;
END $$;

-- Display created users
SELECT 
    u.id,
    u.email,
    u.full_name,
    u.role,
    u.is_active,
    CASE 
        WHEN u.role = 'doctor' THEN d.specialization
        ELSE NULL
    END as specialization
FROM "user" u
LEFT JOIN doctorprofile d ON u.id = d.user_id
WHERE u.email IN (
    'patient@test.com',
    'doctor@test.com',
    'admin@test.com',
    'cardiologist@test.com',
    'patient2@test.com'
)
ORDER BY u.role, u.email;
