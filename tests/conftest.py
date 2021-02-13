import pytest

def pytest_addoption(parser):
    parser.addoption("--coverage", action="store_true",
                     default=False, help="Enables coverage collecting")
