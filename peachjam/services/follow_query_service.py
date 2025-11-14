from peachjam.models import CoreDocument


class FollowQueryService:
    @staticmethod
    def documents_for_follow(follow):
        qs = CoreDocument.objects

        if follow.court:
            return qs.filter(judgment__court=follow.court)

        if follow.author:
            return qs.filter(genericdocument__author=follow.author)

        if follow.court_class:
            return qs.filter(judgment__court__court_class=follow.court_class)

        if follow.court_registry:
            return qs.filter(judgment__registry=follow.court_registry)

        if follow.country:
            return qs.filter(jurisdiction=follow.country)

        if follow.locality:
            return qs.filter(locality=follow.locality)

        if follow.taxonomy:
            topics = [follow.taxonomy] + list(follow.taxonomy.get_descendants())
            return qs.filter(taxonomies__topic__in=topics)

        return qs.none()
