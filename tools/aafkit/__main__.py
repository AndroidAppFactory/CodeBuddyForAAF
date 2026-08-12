"""允许 python3 -m aafkit 直接运行"""

import sys

from .cli.main import main

sys.exit(main())
