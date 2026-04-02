from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "service": settings.APP_SLUG,
                "version": settings.API_VERSION,
                "status": "ok",
            }
        )
