from django.db import models


class TestModel(models.Model):
    test_value = models.CharField(max_length=100)
