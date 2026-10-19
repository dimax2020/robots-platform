"""Необязательные дополнения к каталогу правит администратор; это не этап допуска."""
from fastapi import APIRouter, Depends, HTTPException
from app.api.auth import require_admin
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.assessment_repo import read_policy, save_policy

router = APIRouter(dependencies=[Depends(require_admin)])


def _read(kind, key):
    with session_factory()() as db:
        try:
            return read_policy(db, kind, key)
        except KeyError:
            raise HTTPException(404, 'Объект не найден') from None


def _save(kind, key, body):
    with session_factory()() as db:
        try:
            return save_policy(db, kind, key, body)
        except KeyError:
            raise HTTPException(404, 'Объект не найден') from None
        except ValueError as ex:
            raise HTTPException(422, str(ex)) from None


@router.get('/api/v1/admin/products/{slug}/assessment', tags=['Профили допуска'])
def product_read(slug: str):
    return _read('product', slug)


@router.put('/api/v1/admin/products/{slug}/assessment', tags=['Профили допуска'])
def product_save(slug: str, body: dict):
    return _save('product', slug, body)


@router.get('/api/v1/admin/processes/{code}/assessment', tags=['Профили допуска'])
def process_read(code: str):
    return _read('process', code)


@router.put('/api/v1/admin/processes/{code}/assessment', tags=['Профили допуска'])
def process_save(code: str, body: dict):
    return _save('process', code, body)
