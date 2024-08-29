import os

from django.apps import apps
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string


class Command(BaseCommand):
    help = "Generate Mermaid ER diagrams for Django models"

    def handle(self, *args, **kwargs):
        # Loop through all installed apps
        for app_config in apps.get_app_configs():
            models = app_config.get_models()
            if not models:
                continue

            # Generate Mermaid diagram syntax for each model
            mermaid_syntax = self.generate_mermaid(models)

            # Create docs directory in the app if it doesn't exist
            docs_dir = os.path.join(app_config.path, "docs")
            os.makedirs(docs_dir, exist_ok=True)

            # Export Mermaid diagram to an HTML file
            html_file_path = os.path.join(docs_dir, "er_diagram.html")
            self.export_to_html(mermaid_syntax, html_file_path)

            self.stdout.write(
                self.style.SUCCESS(f"Generated ER diagram for app '{app_config.name}'")
            )

    def generate_mermaid(self, models):
        """Generate Mermaid ER diagram syntax for given models."""
        mermaid = ["erDiagram"]
        for model in models:
            model_name = model.__name__
            fields = model._meta.get_fields()
            field_lines = []

            for field in fields:
                if field.many_to_one or field.one_to_one:
                    relation = f"{model_name} ||--o| {field.related_model.__name__} : related to"
                    mermaid.append(relation)
                elif field.one_to_many or field.many_to_many:
                    relation = f"{model_name} ||--o{{ {field.related_model.__name__} : related to"
                    mermaid.append(relation)
                else:
                    field_type = field.get_internal_type()
                    field_name = field.name
                    field_lines.append(f"{field_name} {field_type}")

            mermaid.append(f"{model_name} {{")
            mermaid.extend(field_lines)
            mermaid.append("}")

        return "\n".join(mermaid)

    def export_to_html(self, mermaid_syntax, file_path):
        """Export the Mermaid syntax to an HTML file using a template."""
        html_content = render_to_string(
            "diagram_template.html", {"mermaid_syntax": mermaid_syntax}
        )

        with open(file_path, "w") as f:
            f.write(html_content)
