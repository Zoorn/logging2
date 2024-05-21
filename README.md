# BuB_logger

A flexible and extendable logging module for Python. Its adds all logging handlers into a queue and allow to load multiply defined logging configs.
So you only need to import the module and load all config you want.

## Installation

```bash
pip install git+https://gitea.bub-group.com/woelte/logging.git
or
pip install git+https://github.com/zoorn/logging2
```

## create a new config

It's important that in each config file every handler, formatter have his own Name. Otherwise the the last one called will overwrite the other one.

## Use the modul

```bash
import os
from internal_logger import internal_logger

# Liste der verfügbaren Konfigurationsdateien anzeigen

print(internal_logger.load_config.**doc**)

## Pfad für die Logdatei festlegen

log_directory = os.path.join(os.path.expanduser("~"), "AppData", "Local", "MyApp", "logs")
if not os.path.exists(log_directory):
os.makedirs(log_directory)
log_file_path = os.path.join(log_directory, "app.log")

# Logger konfigurieren mit benutzerdefiniertem Pfad

internal_logger.load_config('logging_file', log_file_path=log_file_path)
internal_logger.load_config('logging_console')

# Logger abrufen und verwenden

log = internal_logger.get_logger('main')
log.info('Logger in main.py konfiguriert.')

# Entfernen der Datei-Konfiguration

internal_logger.remove_config('logging_file')

# Logger erneut verwenden

log.info('Nach dem Entfernen der Datei-Konfiguration werden nur noch Konsolen-Logs ausgegeben.')

# Beispielcode, der den Logger verwendet

try:
raise ValueError("Ein Beispiel-Fehler in main.py")
except Exception as e:
log.error("Fehler aufgetreten", exc_info=e)
```
