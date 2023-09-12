from clickhouse_backend.models import ClickhouseModel


def get_subclasses(class_):
    classes = class_.__subclasses__()

    index = 0
    while index < len(classes):
        classes.extend(classes[index].__subclasses__())
        index += 1

    return list(set(classes))


class ClickHouseRouter:
    def __init__(self):
        self.route_model_names = set()
        for model in get_subclasses(ClickhouseModel):
            if model._meta.abstract:
                continue
            self.route_model_names.add(model._meta.label_lower)

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if f"{app_label}.{model_name}" in self.route_model_names or hints.get(
            "clickhouse"
        ):
            return db != "other"
        return True
