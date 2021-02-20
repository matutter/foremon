import sys
import json

text = json.dumps(dict(
  executable=sys.executable,
  argv=sys.argv,
  name=__name__
), indent=2)


def main():
  print(text)
