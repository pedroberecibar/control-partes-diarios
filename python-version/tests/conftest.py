"""Configuracion compartida de pytest."""

def pytest_addoption(parser):
    parser.addoption("--update-snapshot", action="store_true", default=False,
                     help="Fuerza la regeneracion del snapshot de KPIs")
