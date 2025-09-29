from django.urls.conf import path

from peachjam_subs import views

urlpatterns = [
    path(
        "accounts/subscription/<int:pk>/cancel",
        views.CancelSubscriptionView.as_view(),
        name="cancel_subscription",
    ),
    path("subscribe", views.SubscribeView.as_view(), name="subscribe"),
]
