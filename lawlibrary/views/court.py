from peachjam.views import CourtDetailView as BaseCourtDetailView


class CourtDetailView(BaseCourtDetailView):
    """View for listing a court's judgments."""

    pass


class CourtYearView(BaseCourtDetailView):
    """View for filtering a court's judgments, based on the year."""

    pass
