from django.conf import settings
from django.http import HttpResponse

from .models import TestModel


def access_mysql_db(request):
    # Calling list() on the queryset forces evaluation, which hits the DB
    list(TestModel.objects.using("mysql_test").all())
    return HttpResponse("Successfully hit DB")


def access_postgresql_db(request):
    # Calling list() on the queryset forces evaluation, which hits the DB
    list(TestModel.objects.using("postgresql_test").all())
    return HttpResponse("Successfully hit DB")


def get_secret_key(request):
    return HttpResponse(settings.SECRET_KEY)
