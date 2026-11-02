import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from . import views

INFO = {'id': 'abcdefghijk', 'title': 'My video', 'uploader': 'Creator', 'duration': 120, 'formats': [
    {'format_id': '18', 'height': 360, 'ext': 'mp4', 'vcodec': 'avc1', 'acodec': 'aac', 'filesize': 1024},
    {'format_id': '137', 'height': 1080, 'ext': 'mp4', 'vcodec': 'avc1', 'acodec': 'none'},
]}

class DownloadTests(TestCase):
    def setUp(self):
        views.JOBS.clear()
        self.client.get('/')

    def preview(self):
        with patch('download_page.views.YoutubeDL') as dl:
            dl.return_value.__enter__.return_value.extract_info.return_value = INFO
            return self.client.post('/api/preview/', {'url': 'https://youtu.be/abcdefghijk'}, content_type='application/json')

    def test_home_and_method_protection(self):
        self.assertContains(self.client.get('/'), 'Keep the')
        self.assertEqual(self.client.get('/api/start/').status_code, 405)
        self.assertEqual(self.client.get('/clear/').status_code, 405)

    def test_url_validation(self):
        for url in ['http://127.0.0.1/private', 'https://youtube.com.evil.test/watch?v=abcdefghijk', 'https://youtube.com:444/watch?v=abcdefghijk', 'file:///tmp/a', 'https://youtu.be/not-valid']:
            with self.assertRaises(ValueError):
                views.video_url(url)
        self.assertEqual(views.video_url('https://www.youtube.com/shorts/abcdefghijk'), 'https://www.youtube.com/watch?v=abcdefghijk')

    def test_preview_filters_and_start_ownership(self):
        response = self.preview()
        self.assertEqual(response.status_code, 200)
        self.assertEqual([f['id'] for f in response.json()['formats']], ['18'])
        with patch('download_page.views.POOL.submit'):
            response = self.client.post('/api/start/', {'format': '18'}, content_type='application/json')
        self.assertEqual(response.status_code, 202)
        identifier = response.json()['id']
        self.assertEqual(self.client.get(f'/api/jobs/{identifier}/').status_code, 200)
        other = Client(); other.get('/')
        self.assertEqual(other.get(f'/api/jobs/{identifier}/').status_code, 404)
        self.assertEqual(other.get(f'/files/{identifier}/').status_code, 404)
        self.assertEqual(len(self.client.get('/api/history/').json()['items']), 1)
        self.client.post('/clear/', {}, content_type='application/json')
        self.assertEqual(self.client.get('/api/history/').json()['items'], [])

    def test_unavailable_and_invalid_formats(self):
        self.assertEqual(self.client.post('/api/preview/', {'url': 'https://example.com'}, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/api/start/', {'format': '18'}, content_type='application/json').status_code, 400)
        self.preview()
        self.assertEqual(self.client.post('/api/start/', {'format': '137'}, content_type='application/json').status_code, 400)
        with patch('download_page.views.YoutubeDL', side_effect=RuntimeError('private backend error')):
            response = self.client.post('/api/preview/', {'url': 'https://youtu.be/abcdefghijk'}, content_type='application/json')
        self.assertEqual(response.status_code, 422)
        self.assertNotContains(response, 'private backend error', status_code=422)

    def test_worker_and_download_file(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(DOWNLOAD_ROOT=Path(directory)):
            identifier = 'test-job'
            views.JOBS[identifier] = {'owner': self.client.session.session_key, 'title': 'My video', 'created': 0, 'status': 'working', 'progress': 0}
            def extract(url, download):
                (Path(directory) / identifier / 'video.mp4').write_bytes(b'test-media')
                return INFO
            with patch('download_page.views.YoutubeDL') as dl:
                dl.return_value.__enter__.return_value.extract_info.side_effect = extract
                views.run_job(identifier, 'https://www.youtube.com/watch?v=abcdefghijk', '18')
            self.assertEqual(views.JOBS[identifier]['status'], 'ready')
            response = self.client.get(f'/files/{identifier}/')
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment', response['Content-Disposition'])
            self.assertEqual(b''.join(response.streaming_content), b'test-media')
            response.close()

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/')
        self.assertEqual(client.post('/api/start/', {'format': '18'}, content_type='application/json').status_code, 403)
