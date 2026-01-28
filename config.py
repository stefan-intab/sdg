import os

SERVICE_NAME = "SDB_BRIDGE"
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")

INTAB_API_USERNAME = os.getenv("INTAB_API_USERNAME", "sdb_bridge")
INTAB_API_PASSWORD = os.getenv("INTAB_API_PASSWORD", "sdb_bridge")
INTAB_API_BASE_URL = os.getenv("INTAB_API_BASE_URL", "http://localhost:8080/api/v1")

SDG_API_USERNAME = os.getenv("SDG_API_USERNAME", "intab")
SDG_API_PASSWORD = os.getenv("SDG_API_PASSWORD", "intab")
SDG_API_BASE_URL = os.getenv("SDG_API_BASE_URL", "https://smalldatagarden.fi/api")

NATS_USERNAME = os.getenv("NATS_USERNAME", "nats")
NATS_PASSWORD = os.getenv("NATS_PASSWORD", "nats")
NATS_SERVER1 = os.getenv("NATS_SERVER1", "nats")
NATS_PORT = os.getenv("NATS_PORT", 4222)