import pytest
import os
from unittest import mock
from bub_logger.bub_logger import BubLogger
import subprocess
import shutil




@pytest.fixture(scope='session', autouse=True)
def setup_bub_logger():
    """Fixture to setup BubLogger."""
    logger = BubLogger()
    yield logger

@pytest.fixture
def logger_instance(setup_bub_logger):
    """Fixture to provide a configured BubLogger instance."""
    return setup_bub_logger
    
@pytest.fixture(scope="session")
def manage_virtualenv():
    venv_dir = os.path.join("tests",".venv_test")

    subprocess.run(["python", "-m", "venv", venv_dir], check=True)

    if os.name == "nt":
        activate_script = os.path.join(os.path.abspath(venv_dir), "Scripts", "python")
    else:
        activate_script = os.path.join(venv_dir, "bin", "python")

    def run_in_venv(command):
        subprocess.run(f"{activate_script} && {command}", shell=True, check=True)

    # Installiere das Modul
    run_in_venv("pip install git+https://gitea.bub-group.com/woelte/logging.git@main")

    from bub_logger import BubLogger

    yield

    # Entferne virtuelle Umgebung
    shutil.rmtree(venv_dir)