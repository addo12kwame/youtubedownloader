import json
import re
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.core.cache import cache
from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from yt_dlp import YoutubeDL

JOBS = {}
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=2)
MAX_BYTES = 200 * 1024 * 1024


def video_url(raw):
    if not isinstance(raw, str) or len(raw) > 2048:
        raise ValueError('Paste a valid YouTube video link.')
    p = urlparse(raw.strip())
    if p.scheme not in ('http', 'https') or p.username or p.password or p.port:
        raise ValueError('Use a standard https://youtube.com or https://youtu.be link.')
    if p.hostname == 'youtu.be':
        identifier = p.path.strip('/')
    elif p.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
        identifier = parse_qs(p.query).get('v', [''])[0] if p.path == '/watch' else p.path.split('/')[-1] if p.path.startswith(('/shorts/', '/embed/', '/live/')) else ''
    else:
        raise ValueError('Only YouTube video links are supported.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', identifier):
        raise ValueError('This link does not contain a valid video ID.')
    return f'https://www.youtube.com/watch?v={identifier}'


def options():
    return {'quiet': True, 'no_warnings': True, 'noplaylist': True, 'socket_timeout': 20, 'retries': 1, 'cachedir': False}


def formats(info):
    result = []
    for f in info.get('formats', []):
        if f.get('ext') != 'mp4' or f.get('vcodec') in (None, 'none') or f.get('acodec') in (None, 'none'):
            continue
        if f.get('filesize', 0) and f['filesize'] > MAX_BYTES:
            continue
        result.append({'id': str(f['format_id']), 'height': f.get('height') or 0, 'size': f.get('filesize') or f.get('filesize_approx'), 'label': f"{f.get('height') or 'Auto'}p · MP4"})
    return sorted(result, key=lambda x: x['height'], reverse=True)[:12]


def main(request):
    if not request.session.session_key:
        request.session.create()
    return render(request, 'main_page.html', {'hosted': getattr(settings, 'HOSTED', False)})


@require_POST
def preview(request):
    if getattr(settings, 'HOSTED', False):
        count = cache.get('preview-budget', 0)
        if count >= 50:
            return JsonResponse({'error': 'The demo preview limit has been reached. Try again in five minutes.'}, status=429)
        cache.set('preview-budget', count + 1, 300)
    try:
        url = video_url(json.loads(request.body).get('url'))
        with YoutubeDL(options()) as downloader:
            info = downloader.extract_info(url, download=False)
        if info.get('is_live') or info.get('_type') in ('playlist', 'multi_video'):
            raise ValueError('Choose an individual video that is not currently live.')
        choices = formats(info)
        if not choices:
            raise ValueError('No supported video-with-audio MP4 is available. Try another video. Separate audio/video streams are not merged in this version.')
        result = {'url': url, 'title': info.get('title', 'Untitled video'), 'author': info.get('uploader', 'YouTube'), 'duration': info.get('duration'), 'thumbnail': f"https://i.ytimg.com/vi/{info['id']}/hqdefault.jpg", 'formats': choices}
        request.session['preview'] = result
        return JsonResponse(result)
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'error': 'Check the link and try an individual, available YouTube video.'}, status=400)
    except Exception:
        return JsonResponse({'error': 'Video details could not be loaded. The video may be restricted, unavailable, or YouTube may require additional extractor support.'}, status=422)


def cleanup():
    for identifier, job in list(JOBS.items()):
        if job['status'] in ('ready', 'error') and time.time() - job['created'] > 3600:
            shutil.rmtree(settings.DOWNLOAD_ROOT / identifier, ignore_errors=True)
            del JOBS[identifier]


def run_job(identifier, url, choice):
    folder = settings.DOWNLOAD_ROOT / identifier
    try:
        folder.mkdir(parents=True)
        def progress(event):
            if event.get('downloaded_bytes', 0) > MAX_BYTES:
                raise ValueError('File exceeds the 200 MB limit.')
            total = event.get('total_bytes') or event.get('total_bytes_estimate')
            with LOCK:
                JOBS[identifier]['progress'] = min(99, round(event.get('downloaded_bytes', 0) / total * 100)) if total else None
        opts = {**options(), 'format': choice, 'outtmpl': str(folder / 'video.%(ext)s'), 'max_filesize': MAX_BYTES, 'progress_hooks': [progress]}
        with YoutubeDL(opts) as downloader:
            downloader.extract_info(url, download=True)
        file = folder / 'video.mp4'
        if not file.is_file() or file.stat().st_size > MAX_BYTES:
            raise ValueError('No supported file was produced.')
        with LOCK:
            JOBS[identifier].update(status='ready', progress=100)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        with LOCK:
            JOBS[identifier].update(status='error', error='The download could not finish. Try another quality or video. Restricted videos and separate video/audio streams are not supported.')


@require_POST
def start(request):
    saved = request.session.get('preview')
    try:
        choice = str(json.loads(request.body)['format'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'error': 'Select a video quality.'}, status=400)
    if not saved or choice not in [f['id'] for f in saved['formats']]:
        return JsonResponse({'error': 'Load a video preview before downloading.'}, status=400)
    with LOCK:
        cleanup()
        if sum(j['status'] == 'working' for j in JOBS.values()) >= 2:
            return JsonResponse({'error': 'Two downloads are already processing. Please try again shortly.'}, status=429)
        if getattr(settings, 'HOSTED', False):
            used = sum(p.stat().st_size for p in settings.DOWNLOAD_ROOT.glob('*/video.mp4') if p.is_file())
            reserved = sum(MAX_BYTES for job in JOBS.values() if job['status'] == 'working')
            if used + reserved + MAX_BYTES > 512 * 1024 * 1024:
                return JsonResponse({'error': 'Temporary download storage is at capacity. Try again after older downloads expire.'}, status=429)
        identifier = uuid.uuid4().hex
        JOBS[identifier] = {'owner': request.session.session_key, 'title': saved['title'], 'created': time.time(), 'status': 'working', 'progress': 0}
        POOL.submit(run_job, identifier, saved['url'], choice)
    history = request.session.get('history', [])
    request.session['history'] = ([{'id': identifier, 'title': saved['title'], 'quality': next(f['label'] for f in saved['formats'] if f['id'] == choice), 'created': time.time()}] + history)[:10]
    return JsonResponse({'id': identifier}, status=202)


@require_GET
def job_status(request, identifier):
    with LOCK:
        job = JOBS.get(identifier)
        if not job or job['owner'] != request.session.session_key:
            return JsonResponse({'error': 'This download has expired or is not part of this session.'}, status=404)
        return JsonResponse({k: v for k, v in job.items() if k != 'owner'})


@require_GET
def file_download(request, identifier):
    with LOCK:
        job = JOBS.get(identifier)
        if not job or job['owner'] != request.session.session_key or job['status'] != 'ready':
            return JsonResponse({'error': 'This file is not available.'}, status=404)
        file = settings.DOWNLOAD_ROOT / identifier / 'video.mp4'
        if not file.is_file():
            return JsonResponse({'error': 'The file has expired.'}, status=404)
        name = re.sub(r'[^\w .-]', '', job['title'])[:100].strip() or 'video'
        return FileResponse(file.open('rb'), as_attachment=True, filename=name + '.mp4')


@require_GET
def history(request):
    rows = request.session.get('history', [])
    with LOCK:
        for row in rows:
            job = JOBS.get(row['id'])
            row['status'] = job['status'] if job and job['owner'] == request.session.session_key else 'expired'
    return JsonResponse({'items': rows})


@require_POST
def clear_links(request):
    request.session['history'] = []
    return JsonResponse({'ok': True})
