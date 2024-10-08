import os
import sys

import site
from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Field, ForeignKey, Model
from django.template.loader import render_to_string
from pathlib import Path, PosixPath
from typing import Iterator

from django_er_diagram import settings as local_settings
from django_er_diagram.constants import (
    ERD_TEMPLATE_HTML,
    ERD_TEMPLATE_MD,
    HTML,
    INDEX_FILENAME,
    MANY_TO_MANY,
    MD,
    MERMAID_SYNTAX_DICT,
    ONE_TO_MANY,
    ONE_TO_ONE,
)


class Command(BaseCommand):
    help = "Generate Mermaid Entity-Relationship Diagrams for Django models"
    output_options = [MD, HTML]

    def add_arguments(self, parser) -> None:
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
        parser.add_argument(
            "--output",
            default=local_settings.DJANGO_ER_DIAGRAM_OUTPUT_FORMAT,
            help=f"Output format, options are: {*self.output_options,}",
        )

    def handle(self, *args, **kwargs) -> None:
        # Initializations
        self.model_fields = {}
        self.relation_tree = {}
        self.sorted_model_fields = {}
        self.app_files = []
        self.output_dir = local_settings.DJANGO_ER_DIAGRAM_OUTPUT_DIRECTORY

        # Handle input arguments
        only_apps_input = kwargs.get("only_apps", [])
        if isinstance(only_apps_input, str):
            only_apps_input = [only_apps_input]

        ignore_apps_input = kwargs.get("ignore_apps", [])
        if isinstance(ignore_apps_input, str):
            ignore_apps_input = [ignore_apps_input]

        only_apps = [app_name.lower() for app_name in only_apps_input]
        ignore_apps = [app_name.lower() for app_name in ignore_apps_input]
        output = kwargs.get("output")

        # Validations
        overlap_apps = [temp_app for temp_app in only_apps if temp_app in ignore_apps]
        if overlap_apps:
            raise CommandError(
                f"The following apps cannot be selected and ignored at the same time: {*overlap_apps,}"
            )

        if output not in self.output_options:
            raise CommandError(
                f"The following output format is not supported: {output}"
            )

        # Main logic begins here
        self.base_dir = self.get_base_dir()
        self.index_file_path = (
            self.base_dir / INDEX_FILENAME if output == HTML else None
        )
        project_name = str(self.base_dir).split("/")[-1]
        site_packages_paths = [Path(sp).resolve() for sp in site.getsitepackages()]

        # Loop through all installed apps in the root project directory
        for app_config in apps.get_app_configs():
            # Check that app is in the user specified set
            if (only_apps and app_config.label not in only_apps) or (
                ignore_apps and app_config.label in ignore_apps
            ):
                continue

            # Check if app is in root project directory
            app_directory = Path(app_config.path).resolve()
            if not self.base_dir in app_directory.parents or any(
                sp in app_directory.parents for sp in site_packages_paths
            ):
                continue

            models = app_config.get_models()
            if not models:
                continue

            # Generate Mermaid diagram syntax for each model
            self.generate_relation_tree(models)
            self.sort_fields()
            mermaid_code = self.generate_mermaid()

            # Create docs directory in the app if it doesn't exist
            output_path = Path(app_config.path) / self.output_dir
            output_path.mkdir(parents=True, exist_ok=True)

            # Export Mermaid diagram to output file
            file_path = output_path / f"erd.{output}"
            export_func = f"export_to_{output}"
            getattr(self, export_func)(
                content=mermaid_code,
                file_path=str(file_path),
                app_name=app_config.label,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Generated Entity-Relationship Diagram for app '{app_config.name}'"
                )
            )

        # For html output format, create index static page as directory for app diagrams
        if output == HTML:
            sorted_app_files = sorted(self.app_files, key=lambda x: x[0])
            index_content = render_to_string(
                "index_template.html",
                {"app_files": sorted_app_files, "project_name": project_name},
            )
            with open(self.index_file_path, "w") as f:
                f.write(index_content)

    def generate_relation_tree(self, models: Iterator[Model]) -> None:
        """Store model and field data for easier use when writing Mermaid code

        Args:
            models (Iterator[Model]): iterator of model objects for an app

        Returns:
            None
        """
        model_fields = {}
        relation_tree = {MANY_TO_MANY: {}, ONE_TO_MANY: {}, ONE_TO_ONE: {}}
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
                    self.stdout.write(
                        self.style.WARNING(
                            f"Field {field.name} on model {model_name} has unrecognized type. It has been excluded from the diagram."
                        )
                    )
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

                if not field.is_relation or isinstance(field, GenericForeignKey):
                    continue

                related_model_name = field.related_model.__name__
                key = f"{model_name}_to_{related_model_name}"
                reverse_key = f"{related_model_name}_to_{model_name}"

                if field.one_to_one:
                    tree_key = ONE_TO_ONE
                elif field.many_to_many:
                    tree_key = MANY_TO_MANY
                elif isinstance(field, ForeignKey):
                    tree_key = ONE_TO_MANY
                else:
                    continue

                if reverse_key in relation_tree[tree_key]:
                    relation_tree[tree_key][reverse_key]["from_zero"] = getattr(
                        field, "blank", False
                    ) or getattr(field, "null", False)
                elif key not in relation_tree[tree_key]:
                    relation_tree[tree_key][key] = {
                        "from": related_model_name,
                        "from_zero": False,
                        "to": model_name,
                        "to_zero": getattr(field, "blank", False)
                        or getattr(field, "null", False),
                    }

        self.model_fields = model_fields
        self.relation_tree = relation_tree

    def sort_fields(self) -> None:
        """
        Sort model fields so they are displyed properly in ERD
        List primary key first, then relations, then attributes
        """
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

    def generate_mermaid(self) -> str:
        """Generate Mermaid ERD syntax for given models

        Args:
            None

        Returns:
            str: single string containing generated Mermaid code
        """
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

        left = MERMAID_SYNTAX_DICT[relation_type]["from"] + ("o" if from_zero else "|")
        right = ("o" if to_zero else "|") + MERMAID_SYNTAX_DICT[relation_type]["to"]
        return " " * indent + f"{from_model} {left}--{right} {to_model} : has"

    def export_to_md(self, content: str, file_path: str, *args, **kwargs) -> None:
        """Export the Mermaid syntax to a markdown file using a template

        Args:
            content (str): stringified mermaid syntax detailing ERD
            file_path (str): file path to save the resultant markdown content to

        Returns:
            None
        """
        md_content = render_to_string(ERD_TEMPLATE_MD, {"content": content})

        with open(file_path, "w") as f:
            f.write(md_content)

    def export_to_html(self, content: str, file_path: str, app_name: str) -> None:
        """Export the Mermaid syntax to htm

        Args:
            content (str): stringified mermaid syntax detailing ERD
            file_path (str): file path to save the resultant html content to

        Returns:
            None
        """
        html_content = render_to_string(
            ERD_TEMPLATE_HTML,
            {
                "content": content,
                "app_name": app_name,
                "index_path": self.index_file_path,
            },
        )

        with open(file_path, "w") as f:
            f.write(html_content)

        self.app_files.append((app_name, file_path[len(str(self.base_dir)) + 1 :]))

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
