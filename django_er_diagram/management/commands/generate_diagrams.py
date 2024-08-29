import os

import site
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import ForeignKey
from django.template.loader import render_to_string
from pathlib import Path


class Command(BaseCommand):
    help = "Generate Mermaid ER diagrams for Django models"

    def handle(self, *args, **kwargs):
        base_dir = Path(settings.BASE_DIR).resolve()
        site_packages_paths = [Path(sp).resolve() for sp in site.getsitepackages()]

        # Loop through all installed apps in the root project directory
        for app_config in apps.get_app_configs():
            # check if app is in root project directory
            app_directory = Path(app_config.path).resolve()
            if not base_dir in app_directory.parents or any(
                sp in app_directory.parents for sp in site_packages_paths
            ):
                continue

            models = app_config.get_models()
            if not models:
                continue

            # Generate Mermaid diagram syntax for each model
            self.generate_relation_tree(models)
            self.sort_fields()
            content = self.generate_mermaid()

            # Create docs directory in the app if it doesn't exist
            docs_dir = os.path.join(app_config.path, "docs")
            os.makedirs(docs_dir, exist_ok=True)

            # Export Mermaid diagram to a markdown file
            file_path = os.path.join(docs_dir, "er_diagram.md")
            self.export_to_md(content=content, file_path=file_path)

            self.stdout.write(
                self.style.SUCCESS(f"Generated ER diagram for app '{app_config.name}'")
            )

    def generate_relation_tree(self, models):
        model_fields = {}
        relation_tree = {"many_to_many": [], "one_to_many": [], "one_to_one": []}
        for model in models:
            model_name = model.__name__
            fields = model._meta.get_fields()
            model_fields[model_name] = []
            for field in fields:
                model_fields[model_name].append(
                    {"name": field.name, "type": field.get_internal_type()}
                )

                if not field.is_relation:
                    continue

                related_model_name = field.related_model.__name__

                if field.one_to_one:
                    reverse = {"to": model_name, "from": related_model_name}
                    if reverse not in relation_tree["one_to_one"]:
                        relation_tree["one_to_one"].append(
                            {"from": model_name, "to": related_model_name}
                        )

                if field.many_to_many:
                    reverse = {"to": model_name, "from": related_model_name}
                    if reverse not in relation_tree["many_to_many"]:
                        relation_tree["many_to_many"].append(
                            {"from": model_name, "to": related_model_name}
                        )

                if isinstance(field, ForeignKey):
                    relation_tree["one_to_many"].append(
                        {"from": related_model_name, "to": model_name}
                    )

        self.model_fields = model_fields
        self.relation_tree = relation_tree

    def sort_fields(self):
        pass

    def generate_mermaid(self):
        """Generate Mermaid ER diagram syntax for given models."""
        mermaid_lines = ["erDiagram"]
        for model_name, model_fields in self.model_fields.items():
            field_lines = []
            for field in model_fields:
                # if field.many_to_one or field.one_to_one:
                #     relation = f"{model_name} ||--o| {field.related_model.__name__} : related to"
                #     mermaid.append(relation)
                # elif field.one_to_many or field.many_to_many:
                #     relation = f"{model_name} ||--o{{ {field.related_model.__name__} : related to"
                #     mermaid.append(relation)
                # else:
                field_name = field["name"]
                field_type = field["type"]
                field_lines.append(f"        {field_name} {field_type}")

            mermaid_lines.append(f"    {model_name} {{")
            mermaid_lines.extend(field_lines)
            mermaid_lines.append("    }")

        one = "||"
        from_many = "}|"
        to_many = "|{"

        for relation_type, relations in self.relation_tree.items():
            for relation in relations:
                from_model = relation["from"]
                to_model = relation["to"]
                match relation_type:
                    case "many_to_many":
                        mermaid_line = (
                            f"{from_model} {from_many}--{to_many} {to_model} : has"
                        )
                    case "one_to_one":
                        mermaid_line = f"{from_model} {one}--{one} {to_model} : has"
                    case "one_to_many":
                        mermaid_line = f"{from_model} {one}--{to_many} {to_model} : has"
                    case _:
                        continue

                mermaid_lines.append("    " + mermaid_line)

        return "\n".join(mermaid_lines)

    def export_to_md(self, content: str, file_path: str) -> None:
        """Export the Mermaid syntax to an markdown file using a template

        Args:
            content (str): stringified mermaid syntax detailing ER diagram
            file_path (str): file path to save the resultant markdown content to

        Returns:
            None
        """
        md_content = render_to_string("er_diagram_template.md", {"content": content})

        with open(file_path, "w") as f:
            f.write(md_content)
