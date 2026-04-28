"""
Directorio para los modelos ORM de la aplicación.
"""
from api.core.database import Base

# Importaremos todos los modelos aquí para que Alembic los encuentre fácilmente
from .base_models import *
from .domain_models import *
