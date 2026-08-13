# Implantação no PythonAnywhere

Este roteiro considera o usuário `monografiaspn` e o domínio `monografiaspn.pythonanywhere.com`.

## 1. Clonar e instalar

Abra um console Bash no PythonAnywhere:

```bash
cd /home/monografiaspn
git clone https://github.com/rodrigoniskier/monografia-spn.git
cd monografia-spn
python3.13 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

## 2. Criar o `.env` privado

Crie `/home/monografiaspn/monografia-spn/.env` sem publicar seu conteúdo:

```dotenv
APP_ENV=production
DJANGO_SECRET_KEY=gere-uma-chave-longa-e-aleatoria
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=monografiaspn.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://monografiaspn.pythonanywhere.com
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_HSTS_SECONDS=31536000
GEMINI_API_KEY=sua-chave-privada
GEMINI_MODEL=gemini-3.6-flash
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite
GEMINI_TIMEOUT_MS=30000
SQLITE_PATH=/home/monografiaspn/monografia-spn/db.sqlite3
CACHE_PATH=/home/monografiaspn/.cache/monografia-spn
RESEARCH_CONTACT_EMAIL=niskier.rodrigo@gmail.com
```

Uma chave Django pode ser gerada sem expô-la no histórico do Git:

```bash
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 3. Preparar banco e arquivos estáticos

```bash
mkdir -p /home/monografiaspn/.cache/monografia-spn
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
```

Opcionalmente, crie o primeiro administrador:

```bash
.venv/bin/python manage.py createsuperuser
```

## 4. Configurar o Web App

No painel **Web**:

1. crie ou selecione o Web App de `monografiaspn.pythonanywhere.com`;
2. escolha configuração manual e Python 3.13;
3. defina o virtualenv como `/home/monografiaspn/monografia-spn/.venv`;
4. abra o arquivo WSGI e substitua seu conteúdo pelo arquivo `deploy/pythonanywhere_wsgi.py`;
5. recarregue o Web App.

WhiteNoise serve os arquivos estáticos coletados. Se preferir o mapeamento nativo do PythonAnywhere, associe `/static/` a `/home/monografiaspn/monografia-spn/staticfiles/`.

## 5. Atualizações

No console Bash:

```bash
cd /home/monografiaspn/monografia-spn
bash deploy/update_pythonanywhere.sh
```

Depois, pressione **Reload** no painel Web. O script usa `git pull --ff-only`, instala dependências, executa migrações, coleta arquivos estáticos e roda as verificações do Django.

## Diagnóstico rápido

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py showmigrations
tail -n 100 /var/log/monografiaspn.pythonanywhere.com.error.log
```

Se a revisão por IA informar que não está configurada, confira apenas a existência de `GEMINI_API_KEY` no `.env`; nunca imprima o valor da chave no console ou nos logs.

