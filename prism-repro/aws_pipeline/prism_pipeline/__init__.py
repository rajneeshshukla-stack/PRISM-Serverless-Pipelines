"""PRISM four-stage pipeline deployment kit (aws_pipeline/README.md). Nothing here calls AWS unless authorised."""
import os as _os
import sys as _sys

_HERE = _os.path.dirname(_os.path.abspath(__file__))
for _p in (_os.path.join(_HERE, "..", "..", "src"), _os.path.join(_HERE, "..", "..", "aws_measurement")):
    _p = _os.path.normpath(_p)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
