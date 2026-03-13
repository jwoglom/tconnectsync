import os
import sys

# Set timezone BEFORE importing any tconnectsync modules
os.environ['TIMEZONE_NAME'] = 'America/New_York'

# Remove any cached imports of tconnectsync modules to force reimport with new env
for module_name in list(sys.modules.keys()):
    if module_name.startswith('tconnectsync'):
        del sys.modules[module_name]
