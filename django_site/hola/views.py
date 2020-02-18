from django.shortcuts import render
from django.http import HttpResponse
from .models import BotTable

# Create your views here.


def home_page_view(request):
    x = request.GET  # перехватываем запрос с содержащимся в нем ключом - code
    code = x['code']

    new_code = BotTable(code=code)
    new_code.save()  # сохраняем код в базу данных

    return render(request, 'index.html')



