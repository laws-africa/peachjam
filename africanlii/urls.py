from django.urls import path
from africanlii import views


urlpatterns = [
    path('judgments', views.JudgmentListView.as_view(), name='judgment_list'),
    path('judgments/<int:pk>', views.JudgmentDetailView.as_view(), name='judgment_detail'),
]
