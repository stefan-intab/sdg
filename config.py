import os

SERVICE_NAME = "SDB_BRIDGE"
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")

INTAB_API_USERNAME_KEY = os.getenv("INTAB_API_USERNAME_KEY", "email")
INTAB_API_USERNAME = os.getenv("INTAB_API_USERNAME", "service")
INTAB_API_PASSWORD = os.getenv("INTAB_API_PASSWORD", "service")
INTAB_API_BASE_URL = os.getenv("INTAB_API_BASE_URL", "http://localhost:8080/api/v1")

SDG_API_USERNAME_KEY = os.getenv("SDG_API_USERNAME_KEY", "username")
SDG_API_USERNAME = os.getenv("SDG_API_USERNAME", "ss@intab.se")
SDG_API_PASSWORD = os.getenv("SDG_API_PASSWORD", "W08HYoH0l5AQS0k337y8m8Ni64E9lKB9")
SDG_API_BASE_URL = os.getenv("SDG_API_BASE_URL", "https://api2.smalldatagarden.fi")

NATS_USERNAME = os.getenv("NATS_USERNAME", "nats")
NATS_PASSWORD = os.getenv("NATS_PASSWORD", "nats")
NATS_SERVER1 = os.getenv("NATS_SERVER1", "nats")
NATS_PORT = os.getenv("NATS_PORT", 4222)
NATS_STREAM_NAME = os.getenv("NATS_STREAM_NAME", "SAMPLES")
NATS_SUBJECT = os.getenv("NATS_SUBJECT", "telemetry.v1")
