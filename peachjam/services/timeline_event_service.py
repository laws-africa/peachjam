from peachjam.models import TimelineEvent


class TimelineEventService:
    @staticmethod
    def add_new_documents_event(follow, documents):
        event, _ = TimelineEvent.objects.get_or_create(
            user_following=follow,
            event_type=follow.get_event_type(),
            email_alert_sent_at__isnull=True,
        )
        event.append_documents(documents)
        return event

    @staticmethod
    def add_new_search_hits_event(follow, hits):
        # Prepare extra_data
        new_hits = []
        docs = []
        for hit in hits:
            doc = hit.document
            docs.append(doc)

            hit_dict = hit.as_dict()
            hit_dict["document"] = {
                "title": doc.title or "",
                "blurb": doc.blurb or "",
                "flynote": doc.flynote or "",
            }
            new_hits.append(hit_dict)

        event, created = TimelineEvent.objects.get_or_create(
            user_following=follow,
            event_type=follow.get_event_type(),
            email_alert_sent_at__isnull=True,
            defaults={"extra_data": {"hits": new_hits}},
        )

        if not created:
            existing = event.extra_data.get("hits", [])
            combined = {hit["id"]: hit for hit in existing}
            for hit in new_hits:
                combined[hit["id"]] = hit
            event.extra_data["hits"] = list(combined.values())
            event.save(update_fields=["extra_data"])

        event.append_documents(docs)
        return event
