import os
import subprocess
import sys


def on_starting(server):
    if 'RENDER' not in os.environ:
        return
    if os.environ.get('DEMO_MODE', 'true').lower() not in ('1', 'true', 'yes'):
        return

    # Run in subprocesses so the master holds no DB connections or network
    # state when it forks workers.
    for args in (['migrate', '--no-input'], ['flush', '--no-input'], ['seed_demo']):
        subprocess.run([sys.executable, 'manage.py', *args], check=True)
