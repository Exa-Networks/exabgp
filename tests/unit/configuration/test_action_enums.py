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


class TestLeafGetActionEnums:
    """Tests for Leaf.get_action_enums() method."""

    def test_default_action_set_command(self) -> None:
        """Test default action is set-command for Leaf."""
        leaf = Leaf(type=ValueType.STRING)
        result = leaf.get_action_enums()
        assert result == (ActionTarget.SCOPE, ActionOperation.SET, ActionKey.COMMAND)

    def test_explicit_enum_fields(self) -> None:
        """Test explicit enum fields are returned correctly."""
        leaf = Leaf(
            type=ValueType.STRING,
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

    def test_all_enum_targets(self) -> None:
        """Test all ActionTarget values work correctly."""
        for target in ActionTarget:
            leaf = Leaf(type=ValueType.STRING, target=target)
            result = leaf.get_action_enums()
            assert result[0] == target


class TestLeafListGetActionEnums:
    """Tests for LeafList.get_action_enums() method."""

    def test_default_action_append_command(self) -> None:
        """Test default action is append-command for LeafList."""
        leaf_list = LeafList(type=ValueType.STRING)
        result = leaf_list.get_action_enums()
        assert result == (ActionTarget.SCOPE, ActionOperation.APPEND, ActionKey.COMMAND)

    def test_explicit_enum_fields(self) -> None:
        """Test explicit enum fields are returned correctly."""
        leaf_list = LeafList(
            type=ValueType.STRING,
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

    def test_all_enum_targets(self) -> None:
        """Test all ActionTarget values work correctly."""
        for target in ActionTarget:
            leaf_list = LeafList(type=ValueType.STRING, target=target)
            result = leaf_list.get_action_enums()
            assert result[0] == target


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
