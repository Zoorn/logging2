import os
import shutil
import subprocess
from unittest import mock

import pytest

from bub_logger.bub_logger import BubLogger


@pytest.fixture(scope="session", autouse=True)
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
    venv_dir = os.path.join("tests", ".venv_test")

    subprocess.run(["python", "-m", "venv", venv_dir], check=True)

    if os.name == "nt":
        activate_script = os.path.join(os.path.abspath(venv_dir), "Scripts", "python")
    else:
        activate_script = os.path.join(venv_dir, "bin", "python")

    def run_in_venv(command):
        complete_command = f"{activate_script} -m {command}"
        subprocess.run(complete_command, shell=True, check=True)

    # Installiere das Modul

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    command = f"pip install -e {project_root}"
    run_in_venv(command)

    # move egg-info to tests venv
    egg_info = os.path.join(project_root, "bub_logger.egg-info")
    shutil.move(egg_info, os.path.join(venv_dir, "bub_logger.egg-info"))

    from bub_logger import BubLogger

    yield

    # Entferne virtuelle Umgebung
    shutil.rmtree(venv_dir)
