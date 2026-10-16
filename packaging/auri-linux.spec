# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['../app/main.py'],
    pathex=['..'],
    binaries=[],
    datas=[
        ('../templates', 'templates'),
        ('../.env.example', '.'),
    ],
    hiddenimports=[
        'celery', 'celery.apps', 'celery.apps.worker', 'celery.worker',
        'celery.worker.consumer', 'kombu', 'redis', 'openai', 'pydantic',
        'pydantic_settings', 'multipart', 'aiofiles', 'jinja2', 'opentimelineio',
        'app', 'app.main', 'app.api', 'app.api.routes', 'app.workers',
        'app.workers.tasks', 'app.workers.celery_app', 'app.services',
        'app.services.ingestion', 'app.services.indexing',
        'app.services.indexing.audio', 'app.services.indexing.vision',
        'app.services.director', 'app.services.director.agent',
        'app.services.rendering', 'app.services.rendering.ffmpeg_engine',
        'app.services.rendering.timeline', 'app.core', 'app.core.openrouter',
        'app.utils', 'app.utils.files', 'app.config',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='auri',
    debug=False,
    console=True,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, upx_exclude=[],
    name='auri',
)
