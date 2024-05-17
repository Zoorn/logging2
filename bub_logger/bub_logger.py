import logging
import logging.config
import os
import json
import yaml
import sys
import traceback
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
from queue import Queue
import atexit

def update_docstring(docstring):
    """Decorator to update the docstring of a function."""
    def decorator(func):
        func.__doc__ = docstring
        return func
    return decorator

class BubLogger:
    def __init__(self):
        self.loggers = {}
        self.configured = False
        self.queue = Queue()
        self.queue_listener = None
        self.configs = []
        self.config_files = self._find_config_files()

        # register the stop method to be called on exit
        atexit.register(self.stop)

        # Update the docstring of the load_config method with available configuration files
        # self._update_docstring()

    def _find_config_files(self, directory='.'):
        """Find all logging configuration files in the specified directory."""
        config_files = []
        for file in os.listdir(directory):
            if file.endswith('.json') or file.endswith('.yaml') or file.endswith('.yml'):
                config_files.append(os.path.splitext(file)[0])
        return config_files

    def load_config(self, config_file, log_file_path=None, log_level= 'DEBUG'):
        """ Load logging configuration from a file (JSON or YAML) and set log file path if provided and log level.

            Available configuration files:
            {}

            Args:
                config_file (str): Name of the configuration file to load (without extension).
                log_file_path (str, optional): Custom path for log files if specified. Defaults to None.

            Raises:
                FileNotFoundError: If the specified configuration file is not found.
                ValueError: If the configuration file has an invalid format.
        """
        # Create the log file path if it doesn't exist
        if log_file_path:
            log_dir = os.path.dirname(log_file_path)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
        # Find the configuration file with the correct extension
        config_file_with_ext = None
        for ext in ['json', 'yaml', 'yml']:
            if os.path.exists(f'{config_file}.{ext}'):
                config_file_with_ext = f'{config_file}.{ext}'
                break
        
        if not config_file_with_ext:
            raise FileNotFoundError(f'Configuration file {config_file} not found.')
        
        with open(config_file_with_ext, 'r') as file:
            if config_file_with_ext.endswith('.json'):
                config = json.load(file)
            elif config_file_with_ext.endswith('.yaml') or config_file_with_ext.endswith('.yml'):
                config = yaml.safe_load(file)
            else:
                raise ValueError('Invalid configuration file format.')
        
        # Update the log file path if provided
        if log_file_path:
            for handler in config.get('handlers', {}).values():
                if 'filename' in handler:
                    handler['filename'] = log_file_path
        
        # Update the log level if provided
        if log_level:
            for logger in config.get('loggers', {}).values():
                logger['level'] = log_level

        self.configs.append(config)
        self.apply_configs()

    def apply_configs(self):
            """Apply all loaded configurations."""
            # empty config to start with
            combined_config = {'version': 1, 'disable_existing_loggers': False, 'formatters': {}, 'handlers': {}, 'loggers': {}}
            # list of actual handlers to add to the queue listener
            actual_handlers = []

            for config in self.configs:
                # add all formatters to the combined config
                combined_config['formatters'].update(config.get('formatters', {}))
                # Extract actual handlers and remove them from the config
                for handler_name, handler_config in list(config.get('handlers', {}).items()):
                    if handler_config['class'] != 'logging.handlers.QueueHandler':
                        actual_handlers.append((handler_name, handler_config))
                        del config['handlers'][handler_name]
                    else:
                        combined_config['handlers'][handler_name] = handler_config

            # Update loggers, but make sure they only use the QueueHandler
            for logger_name, logger_config in config.get('loggers', {}).items():
                if logger_name not in combined_config['loggers']:
                    combined_config['loggers'][logger_name] = logger_config
                else:
                    combined_config['loggers'][logger_name]['handlers'].extend(logger_config['handlers'])
                    combined_config['loggers'][logger_name]['handlers'] = list(set(combined_config['loggers'][logger_name]['handlers']))
                combined_config['loggers'][logger_name]['handlers'] = ['queue']
                combined_config['loggers'][logger_name]['level'] = min(combined_config['loggers'][logger_name]['level'], logger_config['level'])
                
                
            # Add the QueueHandler with the actual queue
            if 'queue' not in combined_config['handlers']:
                combined_config['handlers']['queue'] = {
                    'class': 'logging.handlers.QueueHandler',
                    'queue': self.queue
                    }

            logging.config.dictConfig(combined_config)

            # Create actual handler instances and start the QueueListener
            handler_instances = []
            for handler_name, handler_config in actual_handlers:
                handler_class_name = handler_config['class'].split('.')[-1]
                if handler_class_name == 'StreamHandler':
                    handler_class = logging.StreamHandler
                elif handler_class_name == 'RotatingFileHandler':
                    handler_class = RotatingFileHandler
                else:
                    raise ValueError(f"Unknown handler class: {handler_class_name}")
                
                handler_instance = handler_class(**{k: v for k, v in handler_config.items() if k not in ['class', 'formatter', 'level']})

                # Set the formatter if specified
                if 'formatter' in handler_config:
                    formatter_name = handler_config['formatter']
                    formatter_config = combined_config['formatters'][formatter_name]
                    formatter = logging.Formatter(formatter_config['format'])
                    handler_instance.setFormatter(formatter)
                
                # Set the level if specified
                if 'level' in handler_config:
                    handler_instance.setLevel(handler_config['level'])

                handler_instances.append(handler_instance)

            if self.queue_listener:
                self.queue_listener.stop()

            self.queue_listener = QueueListener(self.queue, *handler_instances)
            self.queue_listener.start()

            self.configured = True

            # Set the global exception handler
            sys.excepthook = self.log_uncaught_exceptions

    def remove_config(self, config_file):
        """
        Remove logging configuration from a file (JSON or YAML).

        Args:
            config_file (str): Name of the configuration file to remove (without extension).

        Raises:
            FileNotFoundError: If the specified configuration file is not found in the loaded configs.
        """
        config_file_with_ext = None
        for ext in ['.json', '.yaml', '.yml']:
            if os.path.exists(config_file + ext):
                config_file_with_ext = config_file + ext
                break

        if not config_file_with_ext:
            raise FileNotFoundError(f"Config file {config_file} not found.")

        config_to_remove = None
        for config in self.configs:
            if config_file_with_ext.endswith('.json'):
                if config.get('handlers', {}).get('file', {}).get('filename') == config_file_with_ext:
                    config_to_remove = config
                    break
            elif config_file_with_ext.endswith('.yaml') or config_file_with_ext.endswith('.yml'):
                if config.get('handlers', {}).get('yaml', {}).get('filename') == config_file_with_ext:
                    config_to_remove = config
                    break

        if config_to_remove:
            self.configs.remove(config_to_remove)
            self.apply_configs()
        else:
            raise FileNotFoundError(f"Config file {config_file} not found in loaded configs.")

    def get_logger(self, name):
        """Get a logger by name, initializing if not already configured."""
        if not self.configured:
            raise RuntimeError("Logging not configured. Please load a config file first.")
        
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        
        return self.loggers[name]

    def log_uncaught_exceptions(self, exc_type, exc_value, exc_traceback):
        """Log uncaught exceptions with traceback."""
        logger = self.get_logger('uncaught_exceptions')
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow KeyboardInterrupt to exit silently
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    def stop(self):
        """Stop the queue listener."""
        if self.queue_listener:
            self.queue_listener.stop()

    def _update_docstring(self):
        """Update the docstring of the load_config method with available configuration files."""
        available_configs = '\n        '.join(self.config_files)
        docstring = f"""
        Load logging configuration from a file (JSON or YAML) and set log file path if provided.

        Available configuration files: 
        {available_configs}

        Args:
            config_file (str): Name of the configuration file to load (without extension).
            log_file_path (str, optional): Custom path for log files if specified.

        Raises:
            FileNotFoundError: If the specified configuration file is not found.
            ValueError: If the configuration file has an invalid format.
        """
        self.load_config = update_docstring(docstring)(self.load_config)

bub_logger = BubLogger()

if __name__ == '__main__':
    __name__ = 'bub_logger'
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    log_file_path = os.path.join(log_dir, 'test.log')
    bub_logger.load_config('logging_console', log_level='INFO')
    bub_logger.load_config('logging_file', log_file_path=log_file_path, log_level='ERROR')
    logger = bub_logger.get_logger(__name__)
    logger.debug('Test debug message')
    logger.info('Test info message')
    logger.warning('Test warning message')
    logger.error('Test error message')
    logger.critical('Test critical message')
    logger.error('error two')
    print('Logging test successful')