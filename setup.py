from setuptools import setup

APP = ['gcal_menubar.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,  # hide from dock
        'CFBundleName': 'GCal Menu Bar',
        'CFBundleIdentifier': 'com.gcal.menubar',
    },
    'iconfile': 'icon.icns',
    'packages': ['google', 'google_auth_oauthlib', 'googleapiclient', 'httplib2'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    name='GCal Menu Bar',
)
