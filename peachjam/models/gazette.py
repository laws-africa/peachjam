from peachjam.models import CoreDocument


class Gazette(CoreDocument):
    def save(self, *args, **kwargs):
        self.doc_type = "gazette"
        return super().save(*args, **kwargs)
