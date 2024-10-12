import os

import pytubefix.exceptions
from django.http import HttpResponse
from django.shortcuts import render,redirect
from pytubefix import *
from pytubefix.exceptions import VideoUnavailable

from .models import Recent

# Create your views here.


def main(request):
    if 'links' not in request.session:
        request.session['links'] = []
    if request.method == 'POST':
        link = request.POST['link']
        link = link.strip()
        try:
            video = YouTube(link)
            stream = video.streams.get_highest_resolution()
            stream.download(os.path.expanduser(r'~\downloads'))

            request.session['links'].append(link)
            request.session.modified = True

            print(request.session.get('links', []))

        except VideoUnavailable:
            raise VideoUnavailable
        except Exception:
            raise Exception

        return render(request, 'main_page.html', context={'links': request.session.get('links', [])[-5:]})
    return render(request, 'main_page.html', context={'links':  request.session.get('links', [])[-5:]})


def clear_links(request):
    if request.method == 'POST':
        request.session['links'] = []
    return redirect('main_page')

