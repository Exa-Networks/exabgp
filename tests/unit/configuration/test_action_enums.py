"""Unit tests for action enums and apply_action() handler.

Tests the type-safe action enums introduced to replace string-based actions.
"""

from exabgp.configuration.schema import (
    ActionTarget,
    ActionOperation,
    ActionKey,
    Leaf,
    LeafList,
    ValueType,
    action_string_to_enums,
)


class TestActionEnums:
    """Tests for ActionTarget, ActionOperation, ActionKey enums."""

    def test_action_target_values(self) -> None:
        """Test ActionTarget enum has expected values."""
        assert ActionTarget.SCOPE.value == 'scope'
        assert ActionTarget.ATTRIBUTE.value == 'attribute'
        assert ActionTarget.NLRI.value == 'nlri'
        assert ActionTarget.NEXTHOP.value == 'nexthop'
        assert ActionTarget.ROUTE.value == 'route'

    def test_action_operation_values(self) -> None:
        """Test ActionOperation enum has expected values."""
        assert ActionOperation.SET.value == 'set'
        assert ActionOperation.APPEND.value == 'append'
        assert ActionOperation.EXTEND.value == 'extend'
        assert ActionOperation.ADD.value == 'add'
        assert ActionOperation.NOP.value == 'nop'

    def test_action_key_values(self) -> None:
        """Test ActionKey enum has expected values."""
        assert ActionKey.COMMAND.value == 'command'
        assert ActionKey.NAME.value == 'name'
        assert ActionKey.FIELD.value == 'field'


class TestActionStringToEnums:
    """Tests for action_string_to_enums() conversion function."""

    def test_set_command(self) -> None:
        """Test set-command conversion."""
        result = action_string_to_enums('set-command')
        assert result == (ActionTarget.SCOPE, ActionOperation.SET, ActionKey.COMMAND)

    def test_append_command(self) -> None:
        """Test append-command conversion."""
        result = action_string_to_enums('append-command')
        assert result == (ActionTarget.SCOPE, ActionOperation.APPEND, ActionKey.COMMAND)

    def test_extend_command(self) -> None:
        """Test extend-command conversion."""
        result = action_string_to_enums('extend-command')
        assert result == (ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.COMMAND)

    def test_append_name(self) -> None:
        """Test append-name conversion."""
        result = action_string_to_enums('append-name')
        assert result == (ActionTarget.SCOPE, ActionOperation.APPEND, ActionKey.NAME)

    def test_extend_name(self) -> None:
        """Test extend-name conversion."""
        result = action_string_to_enums('extend-name')
        assert result == (ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)

    def test_attribute_add(self) -> None:
        """Test attribute-add conversion."""
        result = action_string_to_enums('attribute-add')
        assert result == (ActionTarget.ATTRIBUTE, ActionOperation.ADD, ActionKey.NAME)

    def test_nlri_set(self) -> None:
        """Test nlri-set conversion."""
        result = action_string_to_enums('nlri-set')
        assert result == (ActionTarget.NLRI, ActionOperation.SET, ActionKey.FIELD)

    def test_nlri_add(self) -> None:
        """Test nlri-add conversion."""
        result = action_string_to_enums('nlri-add')
        assert result == (ActionTarget.NLRI, ActionOperation.APPEND, ActionKey.FIELD)

    def test_nlri_nexthop(self) -> None:
        """Test nlri-nexthop conversion."""
        result = action_string_to_enums('nlri-nexthop')
        assert result == (ActionTarget.NEXTHOP, ActionOperation.SET, ActionKey.COMMAND)

    def test_append_route(self) -> None:
        """Test append-route conversion."""
        result = action_string_to_enums('append-route')
        assert result == (ActionTarget.ROUTE, ActionOperation.EXTEND, ActionKey.COMMAND)

    def test_nop(self) -> None:
        """Test nop conversion."""
        result = action_string_to_enums('nop')
        assert result == (ActionTarget.SCOPE, ActionOperation.NOP, ActionKey.COMMAND)

    def test_unknown_action_returns_none(self) -> None:
        """Test unknown action returns None."""
        result = action_string_to_enums('unknown-action')
        assert result is None


class TestLeafGetActionEnums:
    """Tests for Leaf.get_action_enums() method."""

    def test_default_action_set_command(self) -> None:
        """Test default action is set-command for Leaf."""
        leaf = Leaf(type=ValueType.STRING)
        result = leaf.get_action_enums()
        assert result == (ActionTarget.SCOPE, ActionOperation.SET, ActionKey.COMMAND)

    def test_explicit_enum_fields_take_precedence(self) -> None:
        """Test explicit enum fields override string action."""
        leaf = Leaf(
            type=ValueType.STRING,
            action='set-command',  # This should be ignored
            target=ActionTarget.ATTRIBUTE,
            operation=ActionOperation.ADD,
            key=ActionKey.NAME,
        )
        result = leaf.get_action_enums()
        assert result == (ActionTarget.ATTRIBUTE, ActionOperation.ADD, ActionKey.NAME)

    def test_partial_enum_fields_use_defaults(self) -> None:
        """Test partial enum fields fill in from defaults."""
        leaf = Leaf(
            type=ValueType.STRING,
            target=ActionTarget.NLRI,
            # operation and key not specified
        )
        result = leaf.get_action_enums()
        assert result == (ActionTarget.NLRI, ActionOperation.SET, ActionKey.COMMAND)

    def test_string_action_conversion(self) -> None:
        """Test string action is converted to enums."""
        leaf = Leaf(type=ValueType.STRING, action='attribute-add')
        result = leaf.get_action_enums()
        assert result == (ActionTarget.ATTRIBUTE, ActionOperation.ADD, ActionKey.NAME)

    def test_unknown_action_returns_defaults(self) -> None:
        """Test unknown action string returns defaults."""
        leaf = Leaf(type=ValueType.NEXT_HOP, action='unknown-action')  # type: ignore[arg-type]
        result = leaf.get_action_enums()
        # Unknown actions fall back to defaults (SCOPE, SET, COMMAND)
        assert result == (ActionTarget.SCOPE, ActionOperation.SET, ActionKey.COMMAND)


class TestLeafListGetActionEnums:
    """Tests for LeafList.get_action_enums() method."""

    def test_default_action_append_command(self) -> None:
        """Test default action is append-command for LeafList."""
        leaf_list = LeafList(type=ValueType.STRING)
        result = leaf_list.get_action_enums()
        assert result == (ActionTarget.SCOPE, ActionOperation.APPEND, ActionKey.COMMAND)

    def test_explicit_enum_fields_take_precedence(self) -> None:
        """Test explicit enum fields override string action."""
        leaf_list = LeafList(
            type=ValueType.STRING,
            action='append-command',  # This should be ignored
            target=ActionTarget.NLRI,
            operation=ActionOperation.EXTEND,
            key=ActionKey.FIELD,
        )
        result = leaf_list.get_action_enums()
        assert result == (ActionTarget.NLRI, ActionOperation.EXTEND, ActionKey.FIELD)

    def test_partial_enum_fields_use_append_default(self) -> None:
        """Test partial enum fields fill in APPEND for LeafList."""
        leaf_list = LeafList(
            type=ValueType.STRING,
            target=ActionTarget.SCOPE,
            # operation not specified - should default to APPEND
        )
        result = leaf_list.get_action_enums()
        assert result == (ActionTarget.SCOPE, ActionOperation.APPEND, ActionKey.COMMAND)

    def test_string_action_conversion(self) -> None:
        """Test string action is converted to enums."""
        leaf_list = LeafList(type=ValueType.STRING, action='nlri-add')
        result = leaf_list.get_action_enums()
        assert result == (ActionTarget.NLRI, ActionOperation.APPEND, ActionKey.FIELD)


class TestApplyAction:
    """Tests for apply_action() function."""

    def test_nop_does_nothing(self) -> None:
        """Test NOP operation does nothing."""
        from exabgp.configuration.core.action import apply_action

        # Create a minimal mock scope - NOP should not call any methods
        class MockScope:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def set_value(self, *args: object) -> None:
                self.calls.append('set_value')

            def append(self, *args: object) -> None:
                self.calls.append('append')

        scope = MockScope()
        apply_action(
            ActionTarget.SCOPE,
            ActionOperation.NOP,
            ActionKey.COMMAND,
            scope,  # type: ignore[arg-type]
            name='test',
            command='cmd',
            value='ignored',
        )
        assert scope.calls == []

    def test_scope_set_command(self) -> None:
        """Test SCOPE + SET + COMMAND action."""
        from exabgp.configuration.core.action import apply_action

        class MockScope:
            def __init__(self) -> None:
                self.values: dict[str, object] = {}

            def set_value(self, key: str, value: object) -> None:
                self.values[key] = value

        scope = MockScope()
        apply_action(
            ActionTarget.SCOPE,
            ActionOperation.SET,
            ActionKey.COMMAND,
            scope,  # type: ignore[arg-type]
            name='section',
            command='my-command',
            value='my-value',
        )
        assert scope.values == {'my-command': 'my-value'}

    def test_scope_append_name(self) -> None:
        """Test SCOPE + APPEND + NAME action."""
        from exabgp.configuration.core.action import apply_action

        class MockScope:
            def __init__(self) -> None:
                self.lists: dict[str, list[object]] = {}

            def append(self, key: str, value: object) -> None:
                self.lists.setdefault(key, []).append(value)

        scope = MockScope()
        apply_action(
            ActionTarget.SCOPE,
            ActionOperation.APPEND,
            ActionKey.NAME,
            scope,  # type: ignore[arg-type]
            name='my-section',
            command='cmd',
            value='item1',
        )
        apply_action(
            ActionTarget.SCOPE,
            ActionOperation.APPEND,
            ActionKey.NAME,
            scope,  # type: ignore[arg-type]
            name='my-section',
            command='cmd',
            value='item2',
        )
        assert scope.lists == {'my-section': ['item1', 'item2']}

    def test_scope_extend(self) -> None:
        """Test SCOPE + EXTEND action."""
        from exabgp.configuration.core.action import apply_action

        class MockScope:
            def __init__(self) -> None:
                self.lists: dict[str, list[object]] = {}

            def extend(self, key: str, value: object) -> None:
                self.lists.setdefault(key, []).extend(value)  # type: ignore[arg-type]

        scope = MockScope()
        apply_action(
            ActionTarget.SCOPE,
            ActionOperation.EXTEND,
            ActionKey.COMMAND,
            scope,  # type: ignore[arg-type]
            name='section',
            command='items',
            value=['a', 'b', 'c'],
        )
        assert scope.lists == {'items': ['a', 'b', 'c']}

    def test_field_key_uses_field_name(self) -> None:
        """Test FIELD key uses explicit field_name."""
        from exabgp.configuration.core.action import apply_action

        class MockScope:
            def __init__(self) -> None:
                self.values: dict[str, object] = {}

            def set_value(self, key: str, value: object) -> None:
                self.values[key] = value

        scope = MockScope()
        apply_action(
            ActionTarget.SCOPE,
            ActionOperation.SET,
            ActionKey.FIELD,
            scope,  # type: ignore[arg-type]
            name='section',
            command='cmd',
            value='val',
            field_name='custom_field',
        )
        assert scope.values == {'custom_field': 'val'}

    def test_field_key_falls_back_to_command(self) -> None:
        """Test FIELD key falls back to command if field_name not specified."""
        from exabgp.configuration.core.action import apply_action

        class MockScope:
            def __init__(self) -> None:
                self.values: dict[str, object] = {}

            def set_value(self, key: str, value: object) -> None:
                self.values[key] = value

        scope = MockScope()
        apply_action(
            ActionTarget.SCOPE,
            ActionOperation.SET,
            ActionKey.FIELD,
            scope,  # type: ignore[arg-type]
            name='section',
            command='fallback-cmd',
            value='val',
            field_name=None,
        )
        assert scope.values == {'fallback-cmd': 'val'}
