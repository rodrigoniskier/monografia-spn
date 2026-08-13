from django.conf import settings


def app_context(request):
    return {
        "APP_NAME": "Monografia SPN",
        "AI_AVAILABLE": bool(settings.GEMINI_API_KEY),
    }

