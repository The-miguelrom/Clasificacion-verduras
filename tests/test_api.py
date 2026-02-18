from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_inspect_reject_on_rotten() -> None:
    payload = {
        'lot_code': 'L-001',
        'supplier_name': 'Finca Norte',
        'product': 'tomate',
        'username': 'operario1',
        'manual_size_px': 200,
        'detected_defects': [
            {'code': 'podrido_rajadura', 'score': 0.7}
        ]
    }
    response = client.post('/inspect', json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body['quality_class'] == 'C'
    assert body['size_class'] == 'M'


def test_reports() -> None:
    response = client.get('/reports')
    assert response.status_code == 200
    body = response.json()
    assert 'total_inspections' in body
    assert 'quality_distribution' in body
