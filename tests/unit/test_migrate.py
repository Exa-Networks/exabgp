"""Unit tests for the migrate module."""

import pytest

from exabgp.application.migrate import (
    find_balanced_braces,
    get_conf_migration_chain,
    has_context_key,
    migrate_api,
    migrate_api_command,
    migrate_api_json,
    migrate_conf,
    migrate_conf_3_4_to_4,
    migrate_conf_4_to_5,
    migrate_conf_5_to_main,
    reverse_migrate_api_json,
    reverse_migrate_api_line,
    wrap_run_commands,
)


class TestFindBalancedBraces:
    """Tests for find_balanced_braces function."""

    def test_simple_braces(self) -> None:
        assert find_balanced_braces('{abc}', 0) == 4

    def test_nested_braces(self) -> None:
        assert find_balanced_braces('{a{b}c}', 0) == 6

    def test_deeply_nested(self) -> None:
        assert find_balanced_braces('{a{b{c}d}e}', 0) == 10

    def test_no_opening_brace(self) -> None:
        assert find_balanced_braces('abc', 0) == -1

    def test_unbalanced(self) -> None:
        assert find_balanced_braces('{abc', 0) == -1

    def test_start_not_brace(self) -> None:
        assert find_balanced_braces('a{bc}', 0) == -1

    def test_inner_brace(self) -> None:
        assert find_balanced_braces('a{b{c}d}e', 1) == 7


class TestMigrateConf34To4:
    """Tests for 3.4 -> 4 config migration."""

    def test_add_encoder_to_process_block(self) -> None:
        config = """process announce {
    run /usr/bin/test.py;
}"""
        result = migrate_conf_3_4_to_4(config)
        assert 'encoder text;' in result.content
        assert len(result.changes) == 1
        assert 'encoder text' in result.changes[0]

    def test_skip_existing_encoder(self) -> None:
        config = """process announce {
    encoder json;
    run /usr/bin/test.py;
}"""
        result = migrate_conf_3_4_to_4(config)
        assert result.content == config
        assert len(result.changes) == 0

    def test_wrap_process_reference(self) -> None:
        config = """neighbor 10.0.0.1 {
    process announce;
}"""
        result = migrate_conf_3_4_to_4(config)
        assert 'api {' in result.content
        assert 'processes [ announce ]' in result.content
        assert 'process announce;' not in result.content

    def test_route_refresh_enable(self) -> None:
        config = """capability {
    route-refresh;
}"""
        result = migrate_conf_3_4_to_4(config)
        assert 'route-refresh enable;' in result.content
        assert len(result.changes) == 1

    def test_hyphenated_process_name(self) -> None:
        config = """process my-process {
    run /usr/bin/test.py;
}"""
        result = migrate_conf_3_4_to_4(config)
        assert 'encoder text;' in result.content
        assert 'my-process' in result.changes[0]

    def test_nested_braces_in_process(self) -> None:
        config = """process test {
    run /bin/test { arg };
}"""
        result = migrate_conf_3_4_to_4(config)
        assert 'encoder text;' in result.content
        # Original content should be preserved
        assert '{ arg }' in result.content


class TestMigrateConf4To5:
    """Tests for 4 -> 5 config migration."""

    def test_route_refresh_hyphenation(self) -> None:
        config = 'capability { route refresh; }'
        result = migrate_conf_4_to_5(config)
        assert 'route-refresh' in result.content
        assert 'route refresh' not in result.content

    def test_tcp_once_true(self) -> None:
        config = 'tcp.once true'
        result = migrate_conf_4_to_5(config)
        assert 'tcp.attempts 1' in result.content

    def test_tcp_once_false(self) -> None:
        config = 'tcp.once false'
        result = migrate_conf_4_to_5(config)
        assert 'tcp.attempts 0' in result.content

    def test_fragment_syntax(self) -> None:
        config = 'fragment not-a-fragment'
        result = migrate_conf_4_to_5(config)
        assert '!is-fragment' in result.content
        assert 'not-a-fragment' not in result.content

    def test_facility_syslog(self) -> None:
        config = 'facility syslog'
        result = migrate_conf_4_to_5(config)
        assert 'facility daemon' in result.content


class TestMigrateConf5ToMain:
    """Tests for 5 -> main config migration."""

    def test_nlri_mpls_to_labeled_unicast(self) -> None:
        config = 'family { ipv4 nlri-mpls; }'
        result = migrate_conf_5_to_main(config)
        assert 'labeled-unicast' in result.content
        assert 'nlri-mpls' not in result.content

    def test_no_changes_needed(self) -> None:
        config = 'family { ipv4 unicast; }'
        result = migrate_conf_5_to_main(config)
        assert result.content == config
        assert len(result.changes) == 0


class TestMigrateConfChain:
    """Tests for full migration chain."""

    def test_get_chain_3_4_to_main(self) -> None:
        chain = get_conf_migration_chain('3.4', 'main')
        assert chain == [('3.4', '4'), ('4', '5'), ('5', 'main')]

    def test_get_chain_4_to_5(self) -> None:
        chain = get_conf_migration_chain('4', '5')
        assert chain == [('4', '5')]

    def test_invalid_source_version(self) -> None:
        with pytest.raises(ValueError, match='Unknown source version'):
            get_conf_migration_chain('2.0', 'main')

    def test_invalid_target_version(self) -> None:
        with pytest.raises(ValueError, match='Unknown target version'):
            get_conf_migration_chain('3.4', '6.0')

    def test_backwards_migration(self) -> None:
        with pytest.raises(ValueError, match='Cannot migrate backwards'):
            get_conf_migration_chain('5', '4')

    def test_full_migration_3_4_to_main(self) -> None:
        config = """process announce {
    run /usr/bin/test.py;
}

neighbor 10.0.0.1 {
    process announce;
    capability {
        route-refresh;
    }
    family {
        ipv4 nlri-mpls;
    }
}"""
        result = migrate_conf(config, '3.4', 'main')
        # 3.4 -> 4 changes
        assert 'encoder text;' in result.content
        assert 'api {' in result.content
        assert 'route-refresh enable;' in result.content
        # 5 -> main changes
        assert 'labeled-unicast' in result.content


class TestMigrateApiCommand:
    """Tests for API command migration."""

    def test_shutdown_command(self) -> None:
        result, changes = migrate_api_command('shutdown', '4', 'main')
        assert result == 'daemon shutdown'
        assert len(changes) == 1

    def test_announce_without_peer(self) -> None:
        result, changes = migrate_api_command('announce route 10.0.0.0/24 next-hop 1.2.3.4', '4', 'main')
        assert result == 'peer * announce route 10.0.0.0/24 next-hop 1.2.3.4'

    def test_withdraw_without_peer(self) -> None:
        result, changes = migrate_api_command('withdraw route 10.0.0.0/24', '4', 'main')
        assert result == 'peer * withdraw route 10.0.0.0/24'

    def test_neighbor_to_peer(self) -> None:
        result, changes = migrate_api_command('neighbor 10.0.0.1 announce route 10.0.0.0/24', '4', 'main')
        assert result == 'peer 10.0.0.1 announce route 10.0.0.0/24'

    def test_show_adj_rib(self) -> None:
        result, changes = migrate_api_command('show adj-rib out', '4', 'main')
        assert result == 'rib show out'

    def test_no_change_for_4_to_5(self) -> None:
        # Command migrations only apply when going to main
        result, changes = migrate_api_command('shutdown', '4', '5')
        assert result == 'shutdown'
        assert len(changes) == 0


class TestHasContextKey:
    """Tests for has_context_key function."""

    def test_context_in_current_dict(self) -> None:
        obj = {'bgp-ls': {}, 'other': 'value'}
        assert has_context_key(obj, 'bgp-ls', []) is True

    def test_context_in_parent(self) -> None:
        obj = {'key': 'value'}
        assert has_context_key(obj, 'bgp-ls', ['root', 'bgp-ls', 'data']) is True

    def test_context_not_found(self) -> None:
        obj = {'key': 'value'}
        assert has_context_key(obj, 'bgp-ls', ['root', 'data']) is False

    def test_partial_match(self) -> None:
        obj = {'ip-reachability-tlv': {}}
        assert has_context_key(obj, 'ip-reachability', []) is True


class TestMigrateApiJson:
    """Tests for API JSON migration."""

    def test_bgpls_key_renames(self) -> None:
        data = {'bgp-ls': {'sr_capability_flags': 'value'}}
        result, changes = migrate_api_json(data, '4', '5')
        assert 'sr-capability-flags' in str(result)
        assert 'sr_capability_flags' not in str(result)

    def test_ip_to_prefix_in_context(self) -> None:
        data = {'ip-reachability-tlv': {'ip': '10.0.0.1'}}
        result, changes = migrate_api_json(data, '5', 'main')
        assert result['ip-reachability-tlv']['prefix'] == '10.0.0.1'
        assert 'ip' not in result['ip-reachability-tlv']

    def test_ip_not_renamed_without_context(self) -> None:
        data = {'other': {'ip': '10.0.0.1'}}
        result, changes = migrate_api_json(data, '5', 'main')
        # 'ip' should NOT be renamed without proper context
        assert result['other']['ip'] == '10.0.0.1'

    def test_nested_transformation(self) -> None:
        data = {'bgp-ls': {'nested': {'sr_capability_flags': 'value'}}}
        result, changes = migrate_api_json(data, '4', '5')
        assert result['bgp-ls']['nested']['sr-capability-flags'] == 'value'


class TestMigrateApi:
    """Tests for full API migration."""

    def test_command_migration(self) -> None:
        result = migrate_api('shutdown', '4', 'main')
        assert result.content == 'daemon shutdown'

    def test_json_migration(self) -> None:
        result = migrate_api('{"bgp-ls":{"sr_capability_flags":"test"}}', '4', 'main')
        assert 'sr-capability-flags' in result.content

    def test_multiline_content(self) -> None:
        content = """shutdown
reload
announce route 10.0.0.0/24 next-hop 1.2.3.4"""
        result = migrate_api(content, '4', 'main')
        lines = result.content.splitlines()
        assert lines[0] == 'daemon shutdown'
        assert lines[1] == 'daemon reload'
        assert lines[2].startswith('peer * announce')

    def test_invalid_source_version(self) -> None:
        with pytest.raises(ValueError, match='Unknown API source version'):
            migrate_api('test', '3', 'main')

    def test_backwards_migration(self) -> None:
        with pytest.raises(ValueError, match='Cannot migrate backwards'):
            migrate_api('test', 'main', '4')

    def test_empty_lines_preserved(self) -> None:
        content = 'shutdown\n\nreload'
        result = migrate_api(content, '4', 'main')
        lines = result.content.splitlines()
        assert lines[1] == ''


class TestWrapRunCommands:
    """Tests for wrap_run_commands function."""

    def test_basic_wrap(self) -> None:
        config = """process announce {
    run /usr/bin/script.py;
}"""
        result, changes = wrap_run_commands(config, '3.4')
        assert 'exabgp migrate api -f 4 -t main --exec /usr/bin/script.py' in result
        assert len(changes) == 1

    def test_version_4_api(self) -> None:
        config = """process test {
    run /usr/bin/test.py;
}"""
        result, changes = wrap_run_commands(config, '4')
        assert '-f 4 -t main' in result

    def test_version_5_api(self) -> None:
        config = """process test {
    run /usr/bin/test.py;
}"""
        result, changes = wrap_run_commands(config, '5')
        assert '-f 5 -t main' in result

    def test_skip_already_wrapped(self) -> None:
        config = """process test {
    run exabgp migrate api -f 4 -t main --exec /usr/bin/test.py;
}"""
        result, changes = wrap_run_commands(config, '4')
        assert result == config
        assert len(changes) == 0

    def test_preserves_arguments(self) -> None:
        config = """process test {
    run /usr/bin/script.py --arg1 --arg2 value;
}"""
        result, changes = wrap_run_commands(config, '4')
        assert '--exec /usr/bin/script.py --arg1 --arg2 value' in result


class TestMigrateConfWithWrapApi:
    """Tests for migrate_conf with wrap_api enabled."""

    def test_wrap_api_enabled(self) -> None:
        config = """process announce {
    run /usr/bin/test.py;
}"""
        result = migrate_conf(config, '3.4', 'main', wrap_api=True)
        assert 'exabgp migrate api' in result.content
        assert 'encoder text;' in result.content

    def test_wrap_api_not_for_non_main_target(self) -> None:
        config = """process announce {
    run /usr/bin/test.py;
}"""
        result = migrate_conf(config, '3.4', '5', wrap_api=True)
        assert 'exabgp migrate api' not in result.content


class TestReverseMigrateApiJson:
    """Tests for reverse JSON migration (NEW -> OLD)."""

    def test_reverse_bgpls_key_renames(self) -> None:
        # New format (main) -> Old format (4)
        data = {'bgp-ls': {'sr-capability-flags': 'value'}}
        result, changes = reverse_migrate_api_json(data, '4', 'main')
        assert 'sr_capability_flags' in str(result)
        assert 'sr-capability-flags' not in str(result)

    def test_reverse_prefix_to_ip(self) -> None:
        # New format (main) -> Old format (5)
        data = {'ip-reachability-tlv': {'prefix': '10.0.0.1'}}
        result, changes = reverse_migrate_api_json(data, '5', 'main')
        assert result['ip-reachability-tlv']['ip'] == '10.0.0.1'
        assert 'prefix' not in result['ip-reachability-tlv']

    def test_reverse_no_context_no_change(self) -> None:
        # prefix outside of ip-reachability-tlv should NOT be renamed
        data = {'other': {'prefix': '10.0.0.1'}}
        result, changes = reverse_migrate_api_json(data, '5', 'main')
        assert result['other']['prefix'] == '10.0.0.1'
        assert 'ip' not in result['other']

    def test_reverse_full_chain_4_to_main(self) -> None:
        # Reverse transform from main format back to v4 format
        data = {
            'bgp-ls': {
                'sr-capability-flags': 'test',
                'interface-addresses': ['1.2.3.4'],
            },
            'ip-reachability-tlv': {'prefix': '10.0.0.0/24'},
        }
        result, changes = reverse_migrate_api_json(data, '4', 'main')
        # BGP-LS renames should be reversed
        assert 'sr_capability_flags' in result['bgp-ls']
        assert 'interface-address' in result['bgp-ls']
        # ip-reachability-tlv prefix->ip should be reversed
        assert result['ip-reachability-tlv']['ip'] == '10.0.0.0/24'


class TestReverseMigrateApiLine:
    """Tests for reverse API line migration."""

    def test_reverse_json_line(self) -> None:
        line = '{"bgp-ls":{"sr-capability-flags":"test"}}'
        result, changes = reverse_migrate_api_line(line, '4', 'main')
        assert 'sr_capability_flags' in result
        assert 'sr-capability-flags' not in result

    def test_passthrough_non_json(self) -> None:
        # Non-JSON lines should pass through unchanged
        line = 'some text command'
        result, changes = reverse_migrate_api_line(line, '4', 'main')
        assert result == 'some text command'
        assert len(changes) == 0

    def test_empty_line(self) -> None:
        result, changes = reverse_migrate_api_line('', '4', 'main')
        assert result == ''
        assert len(changes) == 0
