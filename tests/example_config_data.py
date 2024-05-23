import json

# Definiere die Testkonfigurationsdaten
test_config_data = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "filename": "test.log",
        },
    },
    "loggers": {
        "": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": True}
    },
}

# Konfigurationsdaten in JSON-Format umwandeln
test_config_json = json.dumps(test_config_data)
