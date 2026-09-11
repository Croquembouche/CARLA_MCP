import sys,io,tarfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from archive import archive_stream

def test_archive_preserves_original_files(tmp_path):
    root=tmp_path/'session';root.mkdir();(root/'a.bin').write_bytes(b'\x00\xff'+b'xyz'*100000)
    data=b''.join(archive_stream(root))
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as tar:
        assert tar.extractfile('session/a.bin').read()==(root/'a.bin').read_bytes()
