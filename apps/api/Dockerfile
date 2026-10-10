FROM python:3.13-slim

WORKDIR /app

# postgresql-client provides pg_dump, used by app/backup.py's scheduled and
# on-demand database backups (runs against the `db` service over the
# network, so only the client — not the server — is needed here). git is
# needed by `pip install` itself: requirements.txt pulls the shared
# editor-common package straight from its GitHub repo (a VCS URL, not a
# package-index release), and pip shells out to `git clone` for that — the
# python:3.13-slim base image doesn't ship git, so without this the build
# fails at that line with no git executable found.
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client git fonts-ipafont-gothic \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
