import os
import pytest
import logging
from bub_logger.bub_logger import BubLogger
from unittest import mock
from tests.example_config_data import test_config_json

@pytest.fixture
def logger_instance():
    """Fixture to create a BubLogger instance and ensure clean up."""
    logger = BubLogger()
    yield logger


# load_config function with mocked Data
@mock.patch('os.makedirs')
@mock.patch('builtins.open', new_callable=mock.mock_open)
@mock.patch('os.path.exists', return_value=True)
@mock.patch('importlib.resources.open_text', new_callable=mock.mock_open)
def test_load_config(mock_importlib_open, mock_exists, mock_open, mock_makedirs, logger_instance):
    """Test loading a config file without creating actual files. Load example config data."""
    log_file_path = 'test.log'

    # Verwende die ausgelagerten Testdaten
    mock_importlib_open.return_value.read.return_value = test_config_json

    logger_instance.load_config('logging_file', log_file_path=log_file_path, log_level='CRITICAL')
    
    # Check if the config was loaded
    assert logger_instance.configs, "Config was not loaded"
    assert logger_instance.configured, "Logger was not configured"

def test_get_logger(logger_instance):
    """Test getting a logger instance."""
    logger_instance.load_config('logging_console', log_level='DEBUG')
    logger = logger_instance.get_logger('test_logger')
    assert isinstance(logger, logging.Logger), "Returned object is not a logger instance"
    # assert logger.level == logging.DEBUG, f"Logger level is {logger.level}, expected DEBUG"


#########################
## Testing the Package ##
#########################

def test_load_config_package(manage_virtualenv):
    """Test loading a config file from the package."""
    bub_logger = BubLogger()
    bub_logger.load_config('logging_console', log_level='DEBUG')
    assert isinstance(bub_logger, BubLogger), "Returned object is not a BubLogger instance"
    assert bub_logger.configs, "Config was not loaded"

def test_get_logger_package(manage_virtualenv):
    """Test getting a logger instance from the package."""
    bub_logger = BubLogger()
    bub_logger.load_config('logging_console', log_level='DEBUG')
    logger = bub_logger.get_logger('test_logger')
    assert isinstance(logger, logging.Logger), "Returned object is not a logger instance"
    # assert logger.level == logging.DEBUG, f"Logger level is {logger.level}, expected DEBUG"