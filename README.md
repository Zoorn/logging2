# BuB_logger

A flexible and extendable logging module for Python. Its adds all logging handlers into a queue and allow to load multiply defined logging configs.
So you only need to import the module and load all configs you want.

## Installation

```bash
pip install git+https://gitea.bub-group.com/woelte/logging.git
or
pip install git+https://github.com/zoorn/logging2
```

## create a new config

It's important that in each config file every handler, formatter have his own Name. Otherwise the the last one called will overwrite the other one.

## Use the modul

### Initialization

```bash
from bub_logger import BubLogger

# Initialisiere den Logger
bub_logger = BubLogger()

# Lade eine Logging-Konfiguration
bub_logger.load_config('logging_console', log_level='DEBUG')
```

### Useable methods

#### load_config

load a config file from a json or yaml and set optional the path for file handler and the log-level

##### parameter

- config_file (str): Name of the configuration file.
- log_file_path (str, optional): Custom path for log files if specified. Default is None.
- log_level (str, optional): Log-Level, which should be set. Default is DEBUG.
- formatter (str, optional): Formatter, which should be used. Default is None. (Not implemented)

##### Example

```bash
bub_logger.load_config('logging_file', log_file_path='path/to/logfile.log', log_level='ERROR')
```

#### load_configs

load multiply configuration files

##### parameter

- configs (list[list], optional): List of configurations to load. Each configuration is a list with the following items:
  - config_file (str): name of the configuration without file extension.
  - log_file_path (str, optional): Custom path for log files if specified. Default is None.
  - log_level (str, optional): Log-Level, which should be set. Default is DEBUG.
  - formatter (str, optional): Formatter, which should be used. Default is None. (Not implemented)

##### Example

```bash
configs = [
    ['logging_console', None, 'DEBUG', None],
    ['logging_file', 'path/to/logfile.log', 'ERROR', None]
]
bub_logger.load_configs(configs)
```

#### get_logger

Returns a logger by name and initializes it if not already configured.
If no configuration is given, the logging_console config is loaded

##### parameter

- name (str): Name of the logger

##### Example

```bash
logger = bub_logger.get_logger('my_logger')
logger.info('This is an info message')
```

#### get_instance

Returns an instance of BubLogger and optionally loads a configuration.

##### parameter

- config_file (str): Name of the configuration file.
- log_file_path (str, optional): Custom path for log files if specified. Default is None.
- log_level (str, optional): Log-Level, which should be set. Default is DEBUG.
- formatter (str, optional): Formatter, which should be used. Default is None. (Not implemented)

##### Example

```bash
logger_instance = BubLogger.get_instance('logging_file', log_file_path='path/to/logfile.log', log_level='ERROR')
```

## Here is a complete example of using the BubLogger:

```bash
from bub_logger import BubLogger
import os

# Initialize the logger
bub_logger = BubLogger()

# Create a directory for log files
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Load configurations
bub_logger.load_config('logging_file', log_file_path=os.path.join(log_dir, 'app.log'), log_level='ERROR')
bub_logger.load_config('logging_console', log_level='DEBUG')

# Get a logger
logger = bub_logger.get_logger('my_app')

# Write log messages
logger.debug('Debug message')
logger.info('Info message')
logger.warning('Warning message')
logger.error('Error message')
logger.critical('Critical message')
```

## Bugs

- The remove function not working.
- Check if the input is correct (formatter, path, level, logging config)
- Every Config File needs his own Name for formatter and handler
- formatter change nothing
- loadconfigs. (Multiply Configs) some parameter should be optional. Now you need to define everything. Not the idea of this module

## Feature

- Create for each config which is loaded a object with an id, so its can be removed (V0.0.2)
  - Clear remove bug
  - Clear own Name Problem (see bugs)
- Clear the bugs (V0.0.2)
- show all possible configs as suggestion when you use loadconfig function (V0.0.2)
- create a function which disable a config for one specified logger
- create a function so you can transfer a config File into the bib
- create a function to remove a config File from the bib
- change the formatter with an parameter
- Add other config Files with other handler typs (TimeRotatingFileHandler, SocketHandler, SysLogHandler, SMTPHandler, HTTPHandler)
- Add JSON Formatter
- Add Filters and make them dynamic
- as argument in load configs it should be possible to hand over a str or an formatter object or handler object or etc.

## PatchNotes

## V0.0.2 (not released)

- clear Bugs
- Feature: Config as an object with id to remove the config
- Feature: suggest all possible configs if loadconfig or loadconfigs is used

### V0.0.1

- load configs from given config files
- dynamic change of log file path, if there is a file Handler
- dynamic change of log level for each config loaded
