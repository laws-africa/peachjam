from rest_framework import permissions


class CoreDocumentPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perms(
            [
                "peachjam.add_coredocument",
                "peachjam.change_coredocument",
                "peachjam.delete_coredocument",
                "peachjam.view_coredocument",
            ]
        )
