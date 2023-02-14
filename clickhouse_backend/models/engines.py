from django.db.models.expressions import Value, Func

__all__ = [
    "Engine", "BaseMergeTree",
    "MergeTree",
    "ReplacingMergeTree", "GraphiteMergeTree",
    "CollapsingMergeTree", "VersionedCollapsingMergeTree",
    "SummingMergeTree", "AggregatingMergeTree",
    "ReplicatedMergeTree",
    "ReplicatedReplacingMergeTree", "ReplicatedGraphiteMergeTree",
    "ReplicatedCollapsingMergeTree", "ReplicatedVersionedCollapsingMergeTree",
    "ReplicatedSummingMergeTree", "ReplicatedAggregatingMergeTree"
]


class Engine(Func):
    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        if path.startswith("clickhouse_backend.models.engines"):
            path = path.replace("clickhouse_backend.models.engines", "clickhouse_backend.models")
        return path, args, kwargs


class BaseMergeTree(Engine):
    def __init__(self, *expressions, output_field=None, **extra):
        self.order_by = extra.pop("order_by", None)
        assert self.order_by is not None, "order_by is required by MergeTree family."
        self.partition_by = extra.pop("partition_by", None)
        self.primary_key = extra.pop("primary_key", None)
        super().__init__(*expressions, output_field=output_field, **extra)


class MergeTree(BaseMergeTree):
    function = "MergeTree"
    arity = 0


class ReplacingMergeTree(BaseMergeTree):
    function = "ReplacingMergeTree"


class SummingMergeTree(BaseMergeTree):
    function = "SummingMergeTree"


class AggregatingMergeTree(BaseMergeTree):
    function = "AggregatingMergeTree"
    arity = 0


class CollapsingMergeTree(BaseMergeTree):
    function = "CollapsingMergeTree"
    arity = 1


class VersionedCollapsingMergeTree(BaseMergeTree):
    function = "CollapsingMergeTree"
    arity = 2


class GraphiteMergeTree(BaseMergeTree):
    function = "GraphiteMergeTree"
    arity = 1


class ReplicatedMixin:
    def __init__(self, *expressions, **extra):
        if self.arity is not None and len(expressions) != self.arity + 2:
            raise TypeError(
                "'%s' takes exactly %s %s (%s given)" % (
                    self.__class__.__name__,
                    self.arity + 2,
                    "arguments",
                    len(expressions),
                )
            )
        if self.arity is None and len(expressions) < 2:
            raise TypeError(
                "'%s' takes at least %s %s (%s given)" % (
                    self.__class__.__name__,
                    2,
                    "arguments",
                    len(expressions),
                )
            )
        replicated_params = tuple(Value(arg) for arg in self.expressions[:2])
        super().__init__(*expressions[2:], **extra)
        self.expressions = replicated_params + self.expressions


class ReplicatedMergeTree(ReplicatedMixin, MergeTree):
    function = "ReplicatedMergeTree"


class ReplicatedReplacingMergeTree(ReplicatedMixin, ReplacingMergeTree):
    function = "ReplicatedReplacingMergeTree"


class ReplicatedSummingMergeTree(ReplicatedMixin, SummingMergeTree):
    function = "ReplicatedSummingMergeTree"


class ReplicatedAggregatingMergeTree(ReplicatedMixin, AggregatingMergeTree):
    function = "ReplicatedAggregatingMergeTree"


class ReplicatedCollapsingMergeTree(ReplicatedMixin, CollapsingMergeTree):
    function = "ReplicatedCollapsingMergeTree"


class ReplicatedVersionedCollapsingMergeTree(ReplicatedMixin, VersionedCollapsingMergeTree):
    function = "ReplicatedCollapsingMergeTree"


class ReplicatedGraphiteMergeTree(ReplicatedMixin, GraphiteMergeTree):
    function = "ReplicatedGraphiteMergeTree"
