import requests

BASE_URL = "http://46.202.150.190:5000"

def test_categories():
    response = requests.get(f"{BASE_URL}/api/categories")
    assert response.status_code == 200
    
def test_products():
    response = requests.get(f"{BASE_URL}/api/products?category_id=783")
    assert response.status_code == 200

def test_product_details():
    response = requests.get(f"{BASE_URL}/api/product/55155")
    assert response.status_code == 200
