#!/usr/bin/env python3

import sys
import json

text = json.dumps(dict(
  executable=sys.executable,
  argv=sys.argv
), indent=2)

print(text)
