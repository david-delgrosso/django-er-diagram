GENERIC_FOREIGN_KEY = "GenericForeignKey"
INDEX_FILENAME = "erd_index.html"
ERD_TEMPLATE_HTML = "erd_template.html"
ERD_TEMPLATE_MD = "erd_template.md"
HTML = "html"
MD = "md"
ONE_TO_ONE = "one_to_one"
MANY_TO_MANY = "many_to_many"
ONE_TO_MANY = "one_to_many"


MERMAID_SYNTAX_DICT = {
    MANY_TO_MANY: {"from": "}", "to": "{"},
    ONE_TO_ONE: {"from": "|", "to": "|"},
    ONE_TO_MANY: {"from": "|", "to": "{"},
}
