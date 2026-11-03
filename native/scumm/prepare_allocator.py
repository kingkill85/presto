"""Keep the upstream allocator license; expose its state for mpy_ld's GOT."""
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text()
old = 'static struct malloc_params mparams;'
if source.count(old) != 1:
    raise SystemExit('Unsupported dlmalloc revision: mparams declaration changed')
Path(sys.argv[2]).write_text(source.replace(old, 'struct malloc_params mparams;'))
