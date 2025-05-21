import httpx

from eu_consultations.utils_scraping import BASE_URL


# TODO: check for internet connection before running
def test_base_url_returns_not_error():
    r_base = httpx.get(BASE_URL)
    assert r_base.status_code not in range(400, 599)