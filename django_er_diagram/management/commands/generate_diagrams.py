import os
import sys

import site
from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Field, ForeignKey
from django.template.loader import render_to_string
from pathlib import Path, PosixPath

from django_er_diagram import settings as local_settings


class Command(BaseCommand):
    help = "Generate Mermaid ER diagrams for Django models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-apps",
            nargs="*",
            default=local_settings.DJANGO_ER_DIAGRAM_ONLY_APPS,
            help="Only create diagrams for these apps",
        )
        parser.add_argument(
            "--ignore-apps",
            nargs="*",
            default=local_settings.DJANGO_ER_DIAGRAM_IGNORE_APPS,
            help="Create diagrams for all apps except for these",
        )

    def handle(self, *args, **kwargs):
        # Initializations
        self.model_fields = {}
        self.relation_tree = {}
        self.sorted_model_fields = {}

        only_apps = kwargs.get("only_apps")
        ignore_apps = kwargs.get("ignore_apps")

        overlap_apps = [temp_app for temp_app in only_apps if temp_app in ignore_apps]
        if overlap_apps:
            raise CommandError(
                f"The following apps cannot be selected and ignored at the same time: {*overlap_apps,}"
            )

        base_dir = self.get_base_dir()
        site_packages_paths = [Path(sp).resolve() for sp in site.getsitepackages()]

        # Loop through all installed apps in the root project directory
        for app_config in apps.get_app_configs():
            # Check that app is in the user specified set
            if (
                only_apps
                and app_config.label not in only_apps
                or ignore_apps
                and app_config.label in ignore_apps
            ):
                continue

            # Check if app is in root project directory
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
        relation_tree = {"many_to_many": {}, "one_to_many": {}, "one_to_one": {}}
        for model in models:
            model_name = model.__name__
            fields = model._meta.get_fields()
            model_fields[model_name] = []
            for field in fields:
                if hasattr(field, "get_internal_type"):
                    field_type = field.get_internal_type()
                elif isinstance(field, GenericForeignKey):
                    field_type = "GenericForeignKey"
                else:
                    print(f"Field {field.name} on model {model_name} not recognized")
                    continue

                model_fields[model_name].append(
                    {
                        "name": field.name,
                        "type": field_type,
                        "is_relation": field.is_relation,
                        "is_primary_key": isinstance(field, Field)
                        and field.primary_key,
                    }
                )

                if not field.is_relation:
                    continue

                related_model_name = field.related_model.__name__
                key = f"{model_name}_to_{related_model_name}"
                reverse_key = f"{related_model_name}_to_{model_name}"

                if field.one_to_one:
                    tree_key = "one_to_one"
                elif field.many_to_many:
                    tree_key = "many_to_many"
                elif isinstance(field, (ForeignKey, GenericForeignKey)):
                    tree_key = "one_to_many"
                else:
                    continue

                if reverse_key in relation_tree[tree_key]:
                    relation_tree[tree_key][reverse_key]["from_zero"] = (
                        hasattr(field, "blank")
                        and field.blank
                        or hasattr(field, "null")
                        and field.null
                    )
                elif key not in relation_tree[tree_key]:
                    relation_tree[tree_key][key] = {
                        "from": related_model_name,
                        "from_zero": False,
                        "to": model_name,
                        "to_zero": hasattr(field, "blank")
                        and field.blank
                        or hasattr(field, "null")
                        and field.null,
                    }

        self.model_fields = model_fields
        self.relation_tree = relation_tree

    def sort_fields(self):
        self.sorted_model_fields = {}
        for model_name, model_fields in self.model_fields.items():
            self.sorted_model_fields[model_name] = sorted(
                model_fields,
                key=lambda field: (
                    not field["is_primary_key"],
                    not field["is_relation"],
                    field["name"],
                ),
            )

    def generate_mermaid(self):
        """Generate Mermaid ER diagram syntax for given models."""
        mermaid_lines = ["erDiagram"]
        for model_name, model_fields in self.sorted_model_fields.items():
            field_lines = []
            for field in model_fields:
                field_name = field["name"]
                field_type = field["type"]
                field_lines.append(f"        {field_name} {field_type}")

            mermaid_lines.append(f"    {model_name} {{")
            mermaid_lines.extend(field_lines)
            mermaid_lines.append("    }")

        for relation_type, relations in self.relation_tree.items():
            for relation_data in relations.values():
                mermaid_line = self.generate_mermaid_line(
                    relation_type=relation_type, relation_data=relation_data
                )
                mermaid_lines.append(mermaid_line)

        return "\n".join(mermaid_lines)

    def generate_mermaid_line(
        self, relation_type: str, relation_data: dict, indent: int = 4
    ) -> str:
        """Generate a single line of Mermaid relation syntax

        Args:
            relation_type (str): type of relation i.e. one-to-many

        Returns:
            str: string representing one line of Mermaid syntax
        """
        from_model = relation_data["from"]
        from_zero = relation_data["from_zero"]
        to_model = relation_data["to"]
        to_zero = relation_data["to_zero"]

        SYNTAX_DICT = {
            "many_to_many": {"from": "}", "to": "{"},
            "one_to_one": {"from": "|", "to": "|"},
            "one_to_many": {"from": "|", "to": "{"},
        }
        left = SYNTAX_DICT[relation_type]["from"] + ("o" if from_zero else "|")
        right = ("o" if to_zero else "|") + SYNTAX_DICT[relation_type]["to"]
        return " " * indent + f"{from_model} {left}--{right} {to_model} : has"

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

    def get_base_dir(self) -> PosixPath:
        """Get the base directory for the Django project
        Use the BASE_DIR attribute of the settings module if present.
        Otherwise use the parent directory of manage.py.

        Args:
            None

        Returns:
            PosixPath: base directory of the Django project
        """
        if hasattr(settings, "BASE_DIR"):
            return settings.BASE_DIR

        return Path(sys.argv[0]).resolve().parent
