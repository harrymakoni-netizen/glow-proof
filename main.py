"""Vercel zero-config entrypoint.

Vercel's Python framework detection looks for a FastAPI instance named
`app` at a conventional root-level file (app.py / main.py / server.py /
wsgi.py / asgi.py) and serves the whole thing as one Vercel Function - no
vercel.json rewrites needed (an earlier api/index.py + rewrite approach was
the old pattern, and actively broke routing here: the rewrite made FastAPI
see the rewritten destination path instead of the real request path, so
every route 404'd). The real app still lives in app/main.py; this just
re-exports it under the name Vercel's detection expects.
"""
from app.main import app  # noqa: F401
