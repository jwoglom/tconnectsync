# Hack to enable debug-level logging when running tests
# with `python3 -m unittest discover`

import sys
if 'unittest' in sys.modules:
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
