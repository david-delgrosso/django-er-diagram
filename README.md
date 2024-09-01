# django-er-diagram

[![PyPI](https://img.shields.io/pypi/v/django-er-diagram.svg)](https://pypi.org/project/django-er-diagram/)

Auto-generate Entity-Relationship diagrams for a Django project using Mermaid

## Installation

Install this library using `pip`:
```bash
pip install django-er-diagram
```
## Usage
1. Add `django_er_diagram` to your list of installed apps.

2. Optionally enter your user settings in `settings.py`
```python
DJANGO_ER_DIAGRAM_ONLY_APPS = ... # List of apps to generate diagrams for
DJANGO_ER_DIAGRAM_IGNORE_APPS = ... # List of apps to ignore generating diagrams for
DJANGO_ER_DIAGRAM_OUTPUT_FORMAT = ... # Output format, options are "md" and "html"
DJANGO_ER_DIAGRAM_OUTPUT_DIRECTORY = ... # Output directory name
```

3. Navigate to the root directory of the project and run the following command along with any command arguments you'd like to specify.
```bash
python3 manage.py generate_diagrams
```

4. The Entity-Relationship Diagrams for each specified app will be generated in the specified output format and saved to the specified destination directory. For the `html` format, an `erd_index.html` file will be created in the project's root directory. That file can be used to navigate through the various app diagrams.