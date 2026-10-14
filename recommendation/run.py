"""Launch Python with one shared OpenMP runtime for macOS PyTorch/FAISS wheels.

Usage: python -m recommendation.run -m pytest -q
       python -m recommendation.run -m recommendation.export ...
"""
import importlib.util
import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    env = os.environ.copy()
    if sys.platform == 'darwin':
        spec = importlib.util.find_spec('torch')
        if spec is not None and spec.origin is not None:
            library_dir = Path(spec.origin).parent / 'lib'
            if (library_dir / 'libomp.dylib').is_file():
                previous = env.get('DYLD_LIBRARY_PATH', '')
                paths = [str(library_dir)] + [p for p in previous.split(':') if p and p != str(library_dir)]
                env['DYLD_LIBRARY_PATH'] = ':'.join(paths)
    # Native library search paths must be set before this new interpreter starts.
    # Do not import torch/faiss here or suppress their duplicate-runtime checks.
    os.execve(sys.executable, [sys.executable, *sys.argv[1:]], env)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
