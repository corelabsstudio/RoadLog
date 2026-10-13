"""IP는 외부 서비스에 보내지 않고 로컬 DB-IP Country Lite로 국가만 판별한다."""
from functools import lru_cache
from pathlib import Path
import ipaddress
import maxminddb

DATABASE = Path(__file__).with_name('geo') / 'country.mmdb'


@lru_cache(maxsize=1)
def reader():
    return maxminddb.open_database(str(DATABASE))


def locate(ip: str, accept_language: str = '') -> dict:
    country, name = '', ''
    try:
        address = ipaddress.ip_address(ip)
        if address.is_global:
            result = reader().get(str(address)) or {}
            data = result.get('country') or {}
            country = data.get('iso_code', '')
            name = (data.get('names') or {}).get('en', country)
    except (ValueError, OSError, maxminddb.InvalidDatabaseError):
        pass
    language = ('ko' if country == 'KR' else 'en') if country else ('ko' if accept_language.lower().startswith('ko') else 'en')
    return {'language': language, 'country': country, 'country_name': name}
