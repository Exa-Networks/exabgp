"""Tests for configuration cross-reference validators."""

from exabgp.configuration.validators import CrossReferenceValidator, Reference, ValidationError


class TestCrossReferenceValidator:
    """Test cross-reference validation functionality."""

    def test_valid_process_reference(self):
        """Test that valid process references pass validation."""
        validator = CrossReferenceValidator()

        validator.register_process('monitor', line=5)
        validator.reference_process('monitor', line=25, context='neighbor 1.2.3.4')

        errors = validator.validate()
        assert len(errors) == 0

    def test_invalid_process_reference(self):
        """Test that invalid process references are caught."""
        validator = CrossReferenceValidator()

        validator.reference_process('undefined-process', line=25, context='neighbor 1.2.3.4')

        errors = validator.validate()
        assert len(errors) == 1
        assert 'undefined-process' in errors[0].message
        assert errors[0].line == 25

    def test_valid_template_reference(self):
        """Test that valid template references pass validation."""
        validator = CrossReferenceValidator()

        validator.register_template('peer-template', line=10)
        validator.reference_template('peer-template', line=30, context='neighbor 5.6.7.8')

        errors = validator.validate()
        assert len(errors) == 0

    def test_invalid_template_reference(self):
        """Test that invalid template references are caught."""
        validator = CrossReferenceValidator()

        validator.reference_template('undefined-template', line=30, context='neighbor 5.6.7.8')

        errors = validator.validate()
        assert len(errors) == 1
        assert 'undefined-template' in errors[0].message
        assert errors[0].line == 30

    def test_multiple_errors(self):
        """Test collecting multiple validation errors."""
        validator = CrossReferenceValidator()

        # Register one valid process
        validator.register_process('valid-process', line=5)

        # Reference valid and invalid processes
        validator.reference_process('valid-process', line=20, context='neighbor 1.1.1.1')
        validator.reference_process('invalid1', line=25, context='neighbor 2.2.2.2')
        validator.reference_process('invalid2', line=30, context='neighbor 3.3.3.3')

        errors = validator.validate()
        assert len(errors) == 2
        assert any('invalid1' in e.message for e in errors)
        assert any('invalid2' in e.message for e in errors)

    def test_unused_processes(self):
        """Test finding unused process definitions."""
        validator = CrossReferenceValidator()

        validator.register_process('used-process', line=5)
        validator.register_process('unused-process', line=10)

        validator.reference_process('used-process', line=20)

        unused = validator.get_unused_processes()
        assert len(unused) == 1
        assert unused[0][0] == 'unused-process'
        assert unused[0][1] == 10

    def test_unused_templates(self):
        """Test finding unused template definitions."""
        validator = CrossReferenceValidator()

        validator.register_template('used-template', line=5)
        validator.register_template('unused-template', line=10)

        validator.reference_template('used-template', line=20)

        unused = validator.get_unused_templates()
        assert len(unused) == 1
        assert unused[0][0] == 'unused-template'
        assert unused[0][1] == 10

    def test_duplicate_definitions(self):
        """Test that duplicate definitions track the last one."""
        validator = CrossReferenceValidator()

        # Register same process twice
        validator.register_process('my-process', line=5)
        validator.register_process('my-process', line=10)

        # Reference should still work
        validator.reference_process('my-process', line=20)

        errors = validator.validate()
        assert len(errors) == 0

    def test_clear(self):
        """Test clearing all tracked data."""
        validator = CrossReferenceValidator()

        validator.register_process('process1', line=5)
        validator.register_template('template1', line=10)
        validator.reference_process('process1', line=20)
        validator.reference_template('template1', line=25)

        validator.clear()

        # After clear, the reference should be invalid
        validator.reference_process('process1', line=30)
        errors = validator.validate()
        assert len(errors) == 1  # process1 no longer defined

    def test_validation_error_dataclass(self):
        """Test ValidationError dataclass."""
        error = ValidationError(
            message='Test error',
            line=42,
            context='neighbor 1.2.3.4',
        )

        assert error.message == 'Test error'
        assert error.line == 42
        assert error.context == 'neighbor 1.2.3.4'

    def test_reference_dataclass(self):
        """Test Reference dataclass."""
        ref = Reference(
            name='my-process',
            line=42,
            context='neighbor 1.2.3.4',
        )

        assert ref.name == 'my-process'
        assert ref.line == 42
        assert ref.context == 'neighbor 1.2.3.4'

    def test_empty_validator(self):
        """Test validator with no definitions or references."""
        validator = CrossReferenceValidator()

        errors = validator.validate()
        assert len(errors) == 0

        unused_processes = validator.get_unused_processes()
        assert len(unused_processes) == 0

        unused_templates = validator.get_unused_templates()
        assert len(unused_templates) == 0
