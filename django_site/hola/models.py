from django.db import models

# Create your models here.

# создаем модель таблицы
class BotTable(models.Model):
    code = models.TextField()

