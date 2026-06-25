# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['backend.py'],
    pathex=[],
    binaries=[],
    datas=[('index.html', '.'), ('api.js', '.'), ('jobs_data.js', '.'), ('jobs_data.json', '.'), ('job_profiles.js', '.'), ('job_profiles.json', '.'), ('job_profiles_data.js', '.'), ('job_profiles_data.json', '.'), ('requirements.txt', '.'), ('backend', 'backend')],
    hiddenimports=['backend.config', 'backend.models.kg_schema', 'backend.utils.data_loader', 'backend.utils.lsh_indexer', 'backend.utils.faiss_indexer', 'backend.services.retrieval_service', 'backend.services.embedding_service', 'backend.services.rag_service', 'backend.services.kg_service', 'backend.services.gnn_service'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='智绘青春',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='智绘青春',
)
