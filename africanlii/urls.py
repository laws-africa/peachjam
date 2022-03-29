from django.urls import path, include
from africanlii import views
from django.conf import settings


urlpatterns = [
    path('', views.HomePageView.as_view(), name='home_page'),
    path('judgments', views.JudgmentListView.as_view(), name='judgment_list'),
    path('judgments/<int:pk>', views.JudgmentDetailView.as_view(), name='judgment_detail'),
    path('', include('peachjam.urls')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns