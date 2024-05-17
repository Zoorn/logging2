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

        # Set the global exception handler
        sys.excepthook = self.log_uncaught_exceptions

        # Update the docstring of the load_config method with available configuration files
        # self._update_docstring()

    def _find_config_files(self, directory='.'):
        """Find all logging configuration files in the specified directory."""
        config_files = []
        for file in os.listdir(directory):
            if file.endswith('.json') or file.endswith('.yaml') or file.endswith('.yml'):
                config_files.append(os.path.splitext(file)[0])
        return config_files

    def load_configs(self, configs: list[list] = [['logging_console', None, 'DEBUG', None]]):
        """Load multiple logging configurations from a list of configurations.

        Args:
            configs (list[list], optional): List of configurations to load. Each configuration is a list with the following elements:
                - config_file (str): Name of the configuration file to load (without extension).
                - log_file_path (str, optional): Custom path for log files if specified. Defaults to None.
                - log_level (str, optional): Log level to set. Defaults to 'DEBUG'.
                - formatter (str, optional): Formatter to use. Defaults to None.
        """
        for config in configs:
            self.load_config(*config)
            self.apply_configs()

    def load_config(self, config_file, log_file_path=None, log_level= 'DEBUG', formatter = None):
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
        # Find the configuration file with the correct extension
        config_file_with_ext = None
        for ext in ['json', 'yaml', 'yml']:
            file_path = os.path.join("configs/",f'{config_file}.{ext}')
            if os.path.exists(file_path):
                config_file_with_ext = file_path
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
        # set logger level to debug so that all messages are logged and then set the level of the handlers
        for logger in config.get('loggers', {}).values():
                logger['level'] = 'DEBUG'
        for handler in config.get('handlers', {}).values():
            handler['level'] = log_level
            

        # remove the config if it already exists to avoid duplicates and add the new config
        if config in self.configs:
            self.configs.remove(config)

        self.configs.append(config)

    def merge_configs_and_get_handlers(self, *configs):
        """Merge multiple configurations together and apply them."""
        # empty config to start with
        combined_config = {'version': 1, 'disable_existing_loggers': False, 'formatters': {}, 'handlers': {}, 'loggers': {}}
        # list of actual handlers to add to the queue listener
        actual_handlers = []

        for config in configs:
            # add all formatters to the combined config
            for formatter_name, formatter_config in config.get('formatters', {}).items():
                if formatter_name not in combined_config['formatters']:
                    combined_config['formatters'][formatter_name] = formatter_config
                else:
                    # merge the two formatter configs
                    combined_config['formatters'][formatter_name].update(formatter_config)
            combined_config['formatters'].update(config.get('formatters', {}))

            # Extract actual handlers and remove them from the config
            for handler_name, handler_config in list(config.get('handlers', {}).items()):
                if handler_config['class'] != 'logging.handlers.QueueHandler':
                    actual_handlers.append((handler_name, handler_config))
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
        return combined_config, actual_handlers

    def apply_configs(self):
        """Apply all loaded configurations."""
        combined_config, actual_handlers = self.merge_configs_and_get_handlers(*self.configs)


        # combined_config['handlers']['queue'] = {
        #     'class': 'logging.handlers.QueueHandler',
        #     'queue': "ext://queue.Queue"
        # }
        # with open('combined_config.json', 'w') as file:
        #     json.dump(combined_config, file, indent=4)

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
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, 'test.log')
    bub_logger.load_configs([['logging_file', log_file_path, 'DEBUG', None], ['logging_console', None, 'INFO', None]])
    # bub_logger.load_config('logging_file', log_file_path=log_file_path, log_level='ERROR')
    # bub_logger.load_config('logging_console', log_level='INFO')
    logger = bub_logger.get_logger(__name__)
    logger.debug('Test debug message')
    logger.info('Test info message')
    logger.warning('Test warning message')
    logger.error('Test error message')
    logger.critical('Test critical message')
    logger.error('error two')
    raise ValueError('Test exception')