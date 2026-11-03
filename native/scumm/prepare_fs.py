"""Fix the upstream buffered stream's position after bypass reads."""
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text()
old = '\t\t\ttotalRead += bytesRead;\n\t\t\t// Invalidate buffer since file position changed'
new = ('\t\t\ttotalRead += bytesRead;\n'
       '\t\t\t_bufStart = cabal_file_tell((CabalFile *)_handle);\n'
       '\t\t\t// Invalidate buffer since file position changed')
if source.count(old) != 1:
    raise SystemExit('Unsupported upstream filesystem revision')
Path(sys.argv[2]).write_text(source.replace(old, new))
