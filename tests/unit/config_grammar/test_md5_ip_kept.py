"""An md5-ip given is kept with an auto-discovered local address.

It was dropped, and the TCP MD5 key of a listening neighbor set on no address.
"""

from __future__ import annotations

from exabgp.configuration.grammar.read import read_text


def _md5_ip(body: str) -> str:
    text = f'neighbor 127.0.0.2 {{ router-id 10.0.0.1; local-as 1; peer-as 2; md5-password secret; {body} }}'
    return str(read_text(text).neighbors[0].session.md5_ip)


def test_md5_ip_is_kept_with_local_address_auto() -> None:
    assert _md5_ip('local-address auto; md5-ip 192.0.2.5;') == '192.0.2.5'
    assert _md5_ip('md5-ip 192.0.2.5;') == '192.0.2.5'


def test_without_md5_ip_it_is_left_to_the_local_address() -> None:
    assert _md5_ip('local-address auto;') == 'None'
