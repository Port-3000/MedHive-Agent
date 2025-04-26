
-- Table definition for medical_diagnostics
CREATE TABLE IF NOT EXISTS medical_diagnostics (
    id TEXT PRIMARY KEY,
    diagnosis TEXT,
    radius_mean FLOAT,
    texture_mean FLOAT,
    perimeter_mean FLOAT,
    area_mean FLOAT,
    smoothness_mean FLOAT,
    compactness_mean FLOAT,
    concavity_mean FLOAT,
    concave_points_mean FLOAT,
    symmetry_mean FLOAT,
    fractal_dimension_mean FLOAT,
    radius_se FLOAT,
    texture_se FLOAT,
    perimeter_se FLOAT,
    area_se FLOAT,
    smoothness_se FLOAT,
    compactness_se FLOAT,
    concavity_se FLOAT,
    concave_points_se FLOAT,
    symmetry_se FLOAT,
    fractal_dimension_se FLOAT,
    radius_worst FLOAT,
    texture_worst FLOAT,
    perimeter_worst FLOAT,
    area_worst FLOAT,
    smoothness_worst FLOAT,
    compactness_worst FLOAT,
    concavity_worst FLOAT,
    concave_points_worst FLOAT,
    symmetry_worst FLOAT,
    fractal_dimension_worst FLOAT
);

-- Create an index on diagnosis for faster queries
CREATE INDEX IF NOT EXISTS idx_diagnosis ON medical_diagnostics (diagnosis);