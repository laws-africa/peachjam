from django.urls import path
from africanlii import views


urlpatterns = [
    path('', views.HomePageView.as_view(), name='home_page'),
    path('search-results/', views.SearchPageView.as_view(), name='search_page'),
    path('judgments', views.JudgmentListView.as_view(), name='judgment_list'),
    path('judgments/<int:pk>', views.JudgmentDetailView.as_view(), name='judgment_detail'),
]
