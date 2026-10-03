import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
from app import create_app
from recipes import load_recipes


@pytest.fixture()
def app():
    return create_app(testing=True)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def recipes():
    return load_recipes()
