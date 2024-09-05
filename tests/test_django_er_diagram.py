import pytest

from django.core.management import call_command
from unittest.mock import patch
from io import StringIO
import textwrap
from django.core.management.base import CommandError


@pytest.mark.django_db
class TestGenerateDiagrams:
    def setup_method(self):
        pass

    @patch("django_er_diagram.management.commands.generate_diagrams.Path.mkdir")
    @patch("django_er_diagram.management.commands.generate_diagrams.open", create=True)
    def test_markdown_output(self, mock_open, mock_mkdir):
        # Mock file operations
        mock_file = StringIO()
        mock_open.return_value.__enter__.return_value = mock_file

        # Run the command
        call_command("generate_diagrams", output="md", only_apps="mock_app")

        expected_markdown = textwrap.dedent(
            """
        ```mermaid
        erDiagram
            Author {
                id AutoField
                book ForeignKey
                name CharField
            }
            Book {
                id AutoField
                author ForeignKey
                reader ManyToManyField
                review ForeignKey
                title CharField
            }
            Review {
                id AutoField
                book ForeignKey
                grade OneToOneField
                review_text TextField
            }
            Grade {
                id AutoField
                review OneToOneField
                letter CharField
            }
            Reader {
                id AutoField
                book ManyToManyField
                name CharField
            }
            Reader }|--o{ Book : has
            Author ||--|{ Book : has
            Book ||--|{ Review : has
            Grade ||--o| Review : has
        ```
        """
        ).strip()

        generated_markdown = mock_file.getvalue().strip()
        assert expected_markdown == generated_markdown

    @patch("django_er_diagram.management.commands.generate_diagrams.Path.mkdir")
    @patch("django_er_diagram.management.commands.generate_diagrams.open", create=True)
    def test_html_output(self, mock_open, mock_mkdir):
        # Mock file operations
        mock_file = StringIO()
        mock_open.return_value.__enter__.return_value = mock_file

        # Run the command
        call_command("generate_diagrams", output="html", only_apps="mock_app")

        with open("tests/fixtures/mock_html_output.html", "r") as f:
            expected_html = f.read().strip()

        generated_html = mock_file.getvalue().strip()
        assert expected_html == generated_html

    def test_overlapping_apps(self):
        with pytest.raises(CommandError):
            call_command(
                "generate_diagrams",
                output="md",
                only_apps="mock_app",
                ignore_apps="mock_app",
            )

    def test_invalid_input(self):
        with pytest.raises(CommandError):
            call_command("generate_diagrams", output="fake_input")
