"""Conteúdo do arquivo WSGI do Web App no PythonAnywhere."""

import os
import sys


PROJECT_HOME = "/home/monografiaspn/monografia-spn"
if PROJECT_HOME not in sys.path:
    sys.path.insert(0, PROJECT_HOME)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "monografiaspn.settings")

from django.core.wsgi import get_wsgi_application


application = get_wsgi_application()

