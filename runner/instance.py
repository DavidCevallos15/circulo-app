"""One server or CLI process per data directory, including across restarts."""
import os
from pathlib import Path


class InstanceLock:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.handle = None

    def acquire(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.handle = (self.directory / 'runner.lock').open('a+b')
        self.handle.seek(0, 2)
        if self.handle.tell() == 0:
            self.handle.write(b'0')
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise RuntimeError('Ya hay un ejecutor usando esta carpeta de datos. Cierra el otro servidor o CLI.') from exc
        return self

    def release(self):
        if self.handle:
            try:
                self.handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()
                self.handle = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *_):
        self.release()
