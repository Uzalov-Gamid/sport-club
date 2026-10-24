"""Манифест и сервис-воркер: приложение можно установить на экран телефона."""
from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static
from django.urls import reverse


def manifest(request):
    return JsonResponse({
        'name': 'Пульс — спортивный клуб', 'short_name': 'Пульс', 'lang': 'ru',
        'start_url': reverse('club:home'), 'scope': '/', 'display': 'standalone',
        'background_color': '#101214', 'theme_color': '#101214',
        'icons': [{'src': static('club/icon-192.png'), 'sizes': '192x192', 'type': 'image/png'},
                  {'src': static('club/icon-512.png'), 'sizes': '512x512', 'type': 'image/png'}]},
        content_type='application/manifest+json')


def service_worker(request):
    """Пустой обработчик fetch: данные всегда берутся с сервера, но браузер разрешает установку."""
    js = "self.addEventListener('install',e=>self.skipWaiting());\n" \
         "self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));\n" \
         "self.addEventListener('fetch',()=>{});\n"
    return HttpResponse(js, content_type='application/javascript')
