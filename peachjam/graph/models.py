from neomodel import FloatProperty, RelationshipTo, StringProperty, StructuredNode


class Work(StructuredNode):
    frbr_uri = StringProperty(unique_index=True, required=True)
    ranking = FloatProperty(default=0)
    cites = RelationshipTo("peachjam.graph.models.Work", "CITES")
