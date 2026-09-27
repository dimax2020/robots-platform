"""Интеграционные проверки запускаются на отдельной тестовой БД."""
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.reference_data import _seed_attribute_meta
from app.domain.match import ParsedRecord, OverlayRow
from app.infrastructure.db.ingest import ingest_records, overlay_rows, normalize_stored
from app.infrastructure.db.models import AttributeDefRow, ProductRow
from app.infrastructure.db.product_repo import get_product
from app.infrastructure.db.product_admin_repo import patch_product
from app.infrastructure.db.session import get_engine


@pytest.fixture
def db():
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode='create_savepoint')
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def record(attributes=None, labels=None):
    return ParsedRecord(platform='normalization_test', external_id=str(uuid4()),
                        source_kind='vendor', source_publisher='Test', source_url='https://example.test/robot',
                        parser_code=None, name='Test ' + str(uuid4()),
                        attributes=attributes or {}, attribute_labels=labels or {})


def test_ingest_api_reimport_and_manual_override(db):
    r = record({'charge_min': '90'})
    ingest_records(db, [r])
    p = db.scalar(select(ProductRow).where(ProductRow.name == r.name))
    public = get_product(db, p.slug)
    assert [a['key'] for a in public['attrs']] == ['charge_time_h']
    assert public['attrs'][0]['value'] == 1.5
    assert public['attrs'][0]['unit'] == 'ч'
    assert public['attrs'][0]['label'] == 'Время зарядки'
    assert p.attrs['charge_time_h']['source_id'] == p.attrs['charge_min']['source_id']
    r.attributes['charge_min'] = '120'
    ingest_records(db, [r])
    assert p.attrs['charge_time_h']['value'] == 2
    patch_product(db, p.slug, {'attrs': {'charge_time_h': {'value': 3, 'status': 'known', 'confirmed': True}}})
    r.attributes['charge_min'] = '240'
    ingest_records(db, [r])
    assert p.attrs['charge_time_h']['value'] == 3


def test_overlay_and_seed_metadata(db):
    r = record()
    ingest_records(db, [r])
    p = db.scalar(select(ProductRow).where(ProductRow.name == r.name))
    overlay_rows(db, [OverlayRow(p.slug, 'charge_min', 'Зарядка', '90', 'known', 'vendor', 'https://example.test/manual', '90 минут')])
    assert p.attrs['charge_time_h']['value'] == 1.5
    assert p.attrs['charge_time_h']['quote'] == '90 минут'
    definition = db.get(AttributeDefRow, 'charge_time_h')
    definition.label = 'charge_time_h'
    definition.group_code = 'technical'
    db.flush()
    _seed_attribute_meta(db)
    assert definition.label == 'Время зарядки'
    definition.label = 'Моя подпись'
    _seed_attribute_meta(db)
    assert definition.label == 'Моя подпись'


def test_normalization_is_idempotent_for_database(db):
    normalize_stored(db)
    second = normalize_stored(db)
    assert second['changed'] == 0


def test_deleting_canonical_field_does_not_resurrect_alias(db):
    r = record({'charge_min': '90'})
    ingest_records(db, [r])
    p = db.scalar(select(ProductRow).where(ProductRow.name == r.name))
    patch_product(db, p.slug, {'attrs': {'charge_time_h': None}})
    assert 'charge_time_h' not in p.attrs
    assert 'charge_min' not in p.attrs


def test_unknown_key_requires_readable_label(db):
    r = record({'new_test_attribute': '42'})
    with pytest.raises(ValueError, match='подпись'):
        ingest_records(db, [r])
