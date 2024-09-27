# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('assets', 'assets'),
        ('games', 'games'),
        ('pages', 'pages'),
        ('config.py', '.'),
        ('app', 'app'),
    ],
    hiddenimports=[
        'app.custom_loader',
        'app.database',
        'app.errors',
        'app.routes',
        'app.socketio_events',
        'app.utils',
        'engineio.async_drivers.threading',
        'socketio',
        'flask_socketio',
        'eventlet',
        'dns',
        'dns.resolver',
        'engineio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ForrestHub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/img/forrestHubIcon.ico'
)