import pytest
from fastapi.testclient import TestClient

from aplicacao_fastapi_comparador_agregadores import criar_app

SECRET_TESTE = "segredo-teste"


@pytest.fixture
def app(tmp_path):
    return criar_app(
        secret=SECRET_TESTE,
        db_path=str(tmp_path / "hubsia.db"),
        https=False,
    )


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def client_autenticado(client):
    client.post("/login", data={"secret": SECRET_TESTE}, follow_redirects=False)
    return client
