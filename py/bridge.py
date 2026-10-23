from __future__ import annotations
import base64
import dataclasses
import importlib.util
import inspect
import io
import json
import re
import sys
import types
import typing
import urllib.parse
import urllib.request
from datetime import date, datetime
from pyodide.http import open_url

def _urlopen(url, timeout=None):
    try:
        return io.BytesIO(open_url(url).read().encode('utf-8'))
    except Exception as e:
        raise OSError(str(e)) from e
urllib.request.urlopen = _urlopen
_pdf_stub = types.ModuleType('analysis.pdf_report')

def _build_plan_pdf(*args, **kwargs):
    real = sys.modules.get('analysis._pdf_report_real')
    if real is None:
        spec = importlib.util.spec_from_file_location('analysis._pdf_report_real', '/app/analysis/pdf_report.py')
        real = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = real
        spec.loader.exec_module(real)
    return real.build_plan_pdf(*args, **kwargs)
_pdf_stub.build_plan_pdf = _build_plan_pdf
sys.modules['analysis.pdf_report'] = _pdf_stub
import pydantic
from fastapi import HTTPException, UploadFile
from fastapi.responses import Response
import app as server
ROUTES = [(method, re.compile(re.sub('\\{(\\w+)\\}', '(?P<\\1>[^/]+)', path)), fn) for method, path, fn in server.app.routes]

def _coerce(value: str, ann):
    args = typing.get_args(ann) or (ann,)
    if value == '' and type(None) in args:
        return None
    for t in (int, float):
        if t in args:
            return t(value)
    return value

def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    return str(o)

def _error(status: int, detail) -> dict:
    return {'status': status, 'body': json.dumps({'detail': detail}, ensure_ascii=False)}

async def handle(method: str, path: str, body_text: str | None, file_name: str | None, file_bytes) -> dict:
    url = urllib.parse.urlsplit(path)
    query = dict(urllib.parse.parse_qsl(url.query, keep_blank_values=True))
    for route_method, pattern, fn in ROUTES:
        m = pattern.fullmatch(url.path)
        if route_method == method and m:
            break
    else:
        return _error(404, 'Not Found')
    hints = typing.get_type_hints(fn)
    kwargs = {}
    try:
        for name in inspect.signature(fn).parameters:
            ann = hints.get(name)
            if name in m.groupdict():
                kwargs[name] = m[name]
            elif ann is UploadFile:
                data = bytes(file_bytes.to_py()) if hasattr(file_bytes, 'to_py') else bytes(file_bytes or b'')
                kwargs[name] = UploadFile(file_name, data)
            elif isinstance(ann, type) and issubclass(ann, pydantic.BaseModel):
                kwargs[name] = ann.model_validate(json.loads(body_text or '{}'))
            elif name in query:
                kwargs[name] = _coerce(query[name], ann)
        result = fn(**kwargs)
        if inspect.isawaitable(result):
            result = await result
    except HTTPException as e:
        return _error(e.status_code, e.detail)
    except pydantic.ValidationError as e:
        return _error(422, str(e))
    except Exception as e:
        return _error(500, f'{type(e).__name__}: {e}')
    if isinstance(result, Response):
        return {'status': result.status_code, 'bytes_b64': base64.b64encode(result.content).decode('ascii'), 'media_type': result.media_type, 'headers': dict(result.headers)}
    return {'status': 200, 'body': json.dumps(result, ensure_ascii=False, default=_json_default)}
