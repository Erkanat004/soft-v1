import pytest


@pytest.fixture(autouse=True)
def reset_error_simulation():
    # Import lazily after test collection configures the isolated test DB.
    from app.services.providers.mock_provider import set_simulated_error
    set_simulated_error(None)
    yield
    set_simulated_error(None)
