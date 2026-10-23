class HTTPException(Exception):

    def __init__(self, status_code: int, detail=None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail

class UploadFile:

    def __init__(self, filename, data: bytes):
        self.filename = filename
        self._data = data

    async def read(self) -> bytes:
        return self._data

def File(default=..., **kwargs):
    return default
Form = File
Query = File

class FastAPI:

    def __init__(self, **kwargs):
        self.routes = []

    def _route(self, method, path):

        def deco(fn):
            self.routes.append((method, path, fn))
            return fn
        return deco

    def get(self, path, **kwargs):
        return self._route('GET', path)

    def post(self, path, **kwargs):
        return self._route('POST', path)

    def delete(self, path, **kwargs):
        return self._route('DELETE', path)

    def mount(self, *args, **kwargs):
        pass
