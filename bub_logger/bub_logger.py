import atexit
import importlib.resources as pkg_resources
import json
import logging
import logging.config
import os
import sys
from logging import FileHandler
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from queue import Queue
from typing import List

import yaml


def update_docstring(docstring):
    """Decorator to update the docstring of a function."""

    def decorator(func):
        func.__doc__ = docstring
        return func

    return decorator


class BubLogger:
    def __init__(self):
        self.loggers = {}
        # check if the logger is configured, otherwise don't return any loggers
        self.configured = False
        self.queue = Queue()
        self.queue_listener = None
        self.configs = []
        self.config_files = self._find_config_files()

        # register the stop method to be called on exit
        atexit.register(self._stop)

        # Set the global exception handler
        sys.excepthook = self.log_uncaught_exceptions

        # Update the docstring of the load_config method with available configuration files
        # self._update_docstring()

        # initial parent class

    def _find_config_files(self, directory="."):
        """Find all logging configuration files in the specified directory."""
        config_files = []
        for file in os.listdir(directory):
            if (
                file.endswith(".json")
                or file.endswith(".yaml")
                or file.endswith(".yml")
            ):
                config_files.append(os.path.splitext(file)[0])
        return config_files

    def load_configs(
        self, configs: List[List[str]] = [["logging_console", None, "DEBUG", None]]
    ):
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

    def load_config(self, config_file, log_file_path=None, log_level="DEBUG", formatter=None):
        """Load logging configuration from a file (JSON or YAML) and set log file path if provided and log level.

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
        config_data = None
        for ext in ["json", "yaml", "yml"]:
            try:
                if hasattr(sys, "_MEIPASS"):
                    config_file_path = os.path.join(sys._MEIPASS, "configs", f"{config_file}.{ext}")
                else:
                    config_file_path = pkg_resources.files("bub_logger.configs").joinpath(
                    f"{config_file}.{ext}"
                )
                with config_file_path.open("r") as file:
                    config_data = file.read()
                    if ext == "json":
                        config = json.loads(config_data)
                    else:
                        config = yaml.safe_load(config_data)
                    break
            except FileNotFoundError:
                continue

        if config_data is None:
            raise FileNotFoundError(f"Configuration file {config_file} not found.")

        # Update the log file path if provided
        if log_file_path:
            for handler in config.get("handlers", {}).values():
                if "filename" in handler:
                    handler["filename"] = log_file_path

        # Update the log level if provided
        # set logger level to debug so that all messages are logged and then set the level of the handlers
        for logger in config.get("loggers", {}).values():
            logger["level"] = logging.getLevelName("DEBUG")
        for handler in config.get("handlers", {}).values():
            handler["level"] = logging.getLevelName(log_level)

        # remove the config if it already exists to avoid duplicates and add the new config
        if config in self.configs:
            self.configs.remove(config)

        self.configs.append(config)
        self.apply_configs()

    def merge_configs_and_get_handlers(self, *configs):
        """Merge multiple configurations together and apply them."""
        # empty config to start with
        combined_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {},
            "handlers": {},
            "loggers": {},
        }
        # list of actual handlers to add to the queue listener
        actual_handlers = []

        for config in configs:
            # add all formatters to the combined config
            for formatter_name, formatter_config in config.get(
                "formatters", {}
            ).items():
                if formatter_name not in combined_config["formatters"]:
                    combined_config["formatters"][formatter_name] = formatter_config
                else:
                    # merge the two formatter configs
                    combined_config["formatters"][formatter_name].update(
                        formatter_config
                    )
            combined_config["formatters"].update(config.get("formatters", {}))

            # Extract actual handlers and remove them from the config
            for handler_name, handler_config in list(
                config.get("handlers", {}).items()
            ):
                if handler_config["class"] != "logging.handlers.QueueHandler":
                    actual_handlers.append((handler_name, handler_config))
                else:
                    combined_config["handlers"][handler_name] = handler_config

        # Update loggers, but make sure they only use the QueueHandler
        for logger_name, logger_config in config.get("loggers", {}).items():
            if logger_name not in combined_config["loggers"]:
                combined_config["loggers"][logger_name] = logger_config
            else:
                combined_config["loggers"][logger_name]["handlers"].extend(
                    logger_config["handlers"]
                )
                combined_config["loggers"][logger_name]["handlers"] = list(
                    set(combined_config["loggers"][logger_name]["handlers"])
                )
            combined_config["loggers"][logger_name]["handlers"] = ["queue"]
            combined_config["loggers"][logger_name]["level"] = min(
                combined_config["loggers"][logger_name]["level"], logger_config["level"]
            )

        # Add the QueueHandler with the actual queue
        if "queue" not in combined_config["handlers"]:
            combined_config["handlers"]["queue"] = {
                "class": "logging.handlers.QueueHandler",
                "queue": self.queue,
            }
        return combined_config, actual_handlers

    def apply_configs(self):
        """Apply all loaded configurations."""
        combined_config, actual_handlers = self.merge_configs_and_get_handlers(
            *self.configs
        )

        logging.config.dictConfig(combined_config)

        # Create actual handler instances and start the QueueListener
        handler_instances = []
        for handler_name, handler_config in actual_handlers:
            handler_class_name = handler_config["class"].split(".")[-1]
            if handler_class_name == "StreamHandler":
                handler_class = logging.StreamHandler
            elif handler_class_name == "RotatingFileHandler":
                handler_class = RotatingFileHandler
            elif handler_class_name == "FileHandler":
                handler_class = FileHandler
            else:
                raise ValueError(f"Unknown handler class: {
                                 handler_class_name}")

            handler_instance = handler_class(
                **{
                    k: v
                    for k, v in handler_config.items()
                    if k not in ["class", "formatter", "level"]
                }
            )

            # Set the formatter if specified
            if "formatter" in handler_config:
                formatter_name = handler_config["formatter"]
                formatter_config = combined_config["formatters"][formatter_name]
                formatter = logging.Formatter(formatter_config["format"])
                handler_instance.setFormatter(formatter)

            # Set the level if specified
            if "level" in handler_config:
                handler_instance.setLevel(handler_config["level"])

            handler_instances.append(handler_instance)

        if self.queue_listener:
            self.queue_listener.stop()

        self.queue_listener = QueueListener(
            self.queue, *handler_instances, respect_handler_level=True
        )
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
        for ext in [".json", ".yaml", ".yml"]:
            if os.path.exists(config_file + ext):
                config_file_with_ext = config_file + ext
                break

        if not config_file_with_ext:
            raise FileNotFoundError(f"Config file {config_file} not found.")

        config_to_remove = None
        for config in self.configs:
            if config_file_with_ext.endswith(".json"):
                if (
                    config.get("handlers", {}).get("file", {}).get("filename")
                    == config_file_with_ext
                ):
                    config_to_remove = config
                    break
            elif config_file_with_ext.endswith(
                ".yaml"
            ) or config_file_with_ext.endswith(".yml"):
                if (
                    config.get("handlers", {}).get("yaml", {}).get("filename")
                    == config_file_with_ext
                ):
                    config_to_remove = config
                    break

        if config_to_remove:
            self.configs.remove(config_to_remove)
            self.apply_configs()
        else:
            raise FileNotFoundError(
                f"Config file {config_file} not found in loaded configs."
            )

    def get_logger(self, name) -> logging.Logger:
        """Get a logger by name, initializing if not already configured."""
        if not self.configured:
            # log to console if not configured
            self.load_config("logging_console", log_level="DEBUG")

        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)

        return self.loggers[name]

    def log_uncaught_exceptions(self, exc_type, exc_value, exc_traceback):
        """Log uncaught exceptions with traceback."""
        import traceback

        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        logger = self.get_logger("uncaught_exceptions")
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow KeyboardInterrupt to exit silently
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "---------------------Traceback lines-----------------------")
        logger.critical("\n".join(lines))
        logger.critical(
            "---------------------End of Traceback-----------------------")

        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        sys.exit(1)

    def _stop(self):
        """Stop the queue listener."""
        if self.queue_listener:
            self.queue_listener.stop()

    def _update_docstring(self):
        """Update the docstring of the load_config method with available configuration files."""
        available_configs = "\n        ".join(self.config_files)
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

    @classmethod
    def get_instance(
        cls, config_file=None, log_file_path=None, log_level="DEBUG", formatter=None
    ):
        instance = cls()
        if config_file:
            instance.load_config(
                config_file,
                log_file_path=log_file_path,
                log_level=log_level,
                formatter=formatter,
            )
        return instance


bub_logger = BubLogger()
