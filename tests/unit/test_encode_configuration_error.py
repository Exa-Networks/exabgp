"""Configured encoding reports unresolved wire-ASN placeholders as input errors."""

import argparse

import pytest

from exabgp.application import encode


def test_encode_reports_unresolved_as_trans_as_configuration_error(tmp_path, capsys):
    config = tmp_path / 'unresolved.conf'
    config.write_text("""neighbor 192.0.2.1 {
        router-id 192.0.2.2;
        local-address 192.0.2.2;
        local-as 23456;
        peer-as 65002;
        family { ipv4 unicast; }
        static { route 10.0.0.0/24 next-hop 192.0.2.2; }
    }""")
    parser = argparse.ArgumentParser()
    encode.setargs(parser)
    with pytest.raises(SystemExit) as error:
        encode.cmdline(parser.parse_args(['-c', str(config)]))
    assert error.value.code == 1
    output = capsys.readouterr().out
    assert 'configuration error:' in output
    assert 'AS_TRANS' in output
