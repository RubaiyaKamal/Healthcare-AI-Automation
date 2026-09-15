from dotenv import load_dotenv

load_dotenv()

import os

FHIR_BASE_URL: str = os.getenv("FHIR_BASE_URL", "http://localhost:8080/fhir")
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://app_user:app_password@localhost:5434/healthcare_ai"
)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
INTAKE_MODEL: str = os.getenv("INTAKE_MODEL", "gpt-4o-mini")
ELIGIBILITY_MODEL: str = os.getenv("ELIGIBILITY_MODEL", "gpt-4o-mini")

FHIR_TIMEOUT_SECONDS: float = float(os.getenv("FHIR_TIMEOUT_SECONDS", "15"))