from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.


def main(request):

    name = [1,2,3,4,5]
    return render(request,'main_page.html', context={'links': name})
