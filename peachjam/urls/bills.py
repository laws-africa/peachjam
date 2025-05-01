from django.urls import path

from peachjam.views import BillListView, PlaceBillListView

urlpatterns = [
    path("", BillListView.as_view(), name="bill_list"),
    path("<str:code>", PlaceBillListView.as_view(), name="place_bill_list"),
]
