"""FastAPI startup uses the supported lifespan contract and remains fail-closed."""
from app.main import app, lifespan


def test_application_uses_the_validating_lifespan_contract():
    assert app.router.lifespan_context is lifespan
