from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import path
from django.views.generic import View


class HomeView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        return HttpResponse(
            "<h1>Aegis demo</h1>"
            "<p>Poke this endpoint to trigger rate limiting "
            "(limit : 10 requests / 60s , auto-block after 3 violations).</p>"
        )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", HomeView.as_view(), name="home"),
]
