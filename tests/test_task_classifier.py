"""Tests for the task classifier module."""


from core.task_classifier import is_simple_task_quick


class TestTaskClassifier:
    """Test task classification heuristics."""

    def test_greeting_is_simple(self):
        """Greetings should be classified as simple."""
        assert is_simple_task_quick("hello") is True
        assert is_simple_task_quick("hi there") is True
        assert is_simple_task_quick("good morning") is True

    def test_math_question_is_simple(self):
        """Math questions should be simple."""
        assert is_simple_task_quick("what is 15 * 23?") is True
        assert is_simple_task_quick("calculate 100 / 5") is True

    def test_explanation_is_simple(self):
        """Explanation requests should be simple."""
        assert is_simple_task_quick("explain decorators") is True
        assert is_simple_task_quick("what is a closure?") is True

    def test_build_is_complex(self):
        """'Build' tasks should be complex."""
        assert is_simple_task_quick("build a web scraper") is False
        assert is_simple_task_quick("build a REST API") is False

    def test_web_app_is_complex(self):
        """Web applications should be complex."""
        assert is_simple_task_quick("create a web application") is False
        assert is_simple_task_quick("make a web app with authentication") is False

    def test_database_is_complex(self):
        """Tasks with database should be complex."""
        assert is_simple_task_quick("create a Python app with database") is False

    def test_authentication_is_complex(self):
        """Tasks with authentication should be complex."""
        assert is_simple_task_quick("API with authentication") is False

    def test_full_stack_is_complex(self):
        """Full stack should be complex."""
        assert is_simple_task_quick("full stack application") is False

    def test_short_input_is_simple(self):
        """Very short inputs (<=4 words) should be simple."""
        assert is_simple_task_quick("create calculator") is True
        assert is_simple_task_quick("make a timer") is True

    def test_single_file_creation_is_simple(self):
        """Single file type creation should be simple (without multiple components)."""
        assert is_simple_task_quick("create a html file") is True
        assert is_simple_task_quick("make a python file") is True

    def test_single_tool_is_simple(self):
        """Single-purpose tools should be simple."""
        assert is_simple_task_quick("create a calculator") is True
        assert is_simple_task_quick("make a parser") is True

    def test_multiple_components_is_complex(self):
        """Tasks with 'and' or 'with' should be complex."""
        assert is_simple_task_quick("create a calculator and a converter") is False
        assert is_simple_task_quick("build a web app with authentication") is False
