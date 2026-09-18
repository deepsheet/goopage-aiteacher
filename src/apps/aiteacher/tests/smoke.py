#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask

from src.apps.aiteacher import aiteacher_bp
from src.apps.aiteacher import materials
from src.apps.aiteacher.routes import MAX_HISTORY_ITEMS, _chat_messages
from src.account import account_bp
from src.web_server import app as web_app


class AITeacherSmokeTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY='test')
        self.app.register_blueprint(aiteacher_bp, url_prefix='/aiteacher')
        self.app.register_blueprint(account_bp, url_prefix='/account')
        self.client = self.app.test_client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_root_patch = patch.object(
            materials, 'DATA_ROOT', Path(self.temp_dir.name))
        self.data_root_patch.start()

    def tearDown(self):
        self.data_root_patch.stop()
        self.temp_dir.cleanup()

    def test_page_and_assets_are_available(self):
        for path in (
            '/aiteacher/',
            '/aiteacher/api/course',
            '/aiteacher/static/app.css',
            '/aiteacher/static/app.js',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                try:
                    self.assertEqual(response.status_code, 200)
                finally:
                    response.close()

    def test_course_contains_the_complete_demo(self):
        payload = self.client.get('/aiteacher/api/course').get_json()
        self.assertTrue(payload['success'])
        self.assertEqual(len(payload['course']['lessons']), 4)
        self.assertEqual(payload['course']['lessons'][0]['id'], 'choose')
        self.assertEqual(payload['course']['lessons'][-1]['id'], 'turn-taking')

    def test_home_integrates_account_controls_and_dialogs(self):
        page = self.client.get('/aiteacher/')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'id="accountTrigger"', page.data)
        self.assertIn(b'id="loginForm"', page.data)
        self.assertIn(b'id="registerForm"', page.data)
        self.assertIn(b'id="accountInfoDialog"', page.data)

    def test_login_session_check_and_logout(self):
        verified_user = {
            'id': 'u-100', 'username': 'test-learner', 'email': 'learner@example.com',
        }
        with patch('src.account.auth_controller.verify_login', return_value={
            'status': 'success', 'user': verified_user,
        }):
            login = self.client.post('/account/api/login', json={
                'username': 'test-learner', 'password': 'secret123',
            })
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.get_json()['user']['username'], 'test-learner')

        status = self.client.get('/account/api/check_login').get_json()
        self.assertTrue(status['isLoggedIn'])
        self.assertEqual(status['user']['email'], 'learner@example.com')

        logout = self.client.get('/account/api/logout')
        self.assertEqual(logout.status_code, 200)
        self.assertFalse(self.client.get('/account/api/check_login').get_json()['isLoggedIn'])

    def test_registration_requires_a_regular_password(self):
        missing = self.client.post('/account/api/register', json={
            'username': 'new-learner', 'email': 'new@example.com',
        })
        self.assertEqual(missing.status_code, 400)

        with patch('src.account.auth_controller.create_user', return_value={
            'status': 'success', 'user_id': 'u-101',
        }) as create_user:
            created = self.client.post('/account/api/register', json={
                'username': 'new-learner', 'email': 'new@example.com',
                'password': 'secret123',
            })
        self.assertEqual(created.status_code, 200)
        create_user.assert_called_once()

    def test_empty_chat_message_is_rejected_without_calling_llm(self):
        response = self.client.post('/aiteacher/api/chat', json={})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()['success'])

    def test_context_and_history_are_bounded(self):
        history = [
            {'role': 'user', 'content': '第%s条' % index}
            for index in range(MAX_HISTORY_ITEMS + 4)
        ]
        message, messages = _chat_messages({
            'message': '泡泡',
            'history': history,
            'page_context': {
                'course_title': '把想法说出来',
                'lesson_title': '你想玩什么？',
                'last_action': '选择了泡泡',
            },
        })
        self.assertEqual(message, '泡泡')
        self.assertEqual(len(messages), MAX_HISTORY_ITEMS + 2)
        self.assertIn('选择了泡泡', messages[-1]['content'])

    def test_markdown_upload_is_saved_previewed_and_read_by_chat(self):
        upload = self.client.post(
            '/aiteacher/api/material/upload',
            data={'file': (io.BytesIO('# 光合作用\n植物把光能变成化学能。'.encode()), '课程.md')},
            content_type='multipart/form-data',
        )
        self.assertEqual(upload.status_code, 200)
        material = upload.get_json()['material']
        self.assertEqual(material['source_type'], 'upload')
        self.assertIn('植物把光能', material['text'])

        preview = self.client.get(material['viewer_url'])
        try:
            self.assertEqual(preview.status_code, 200)
            self.assertIn('sandbox allow-scripts', preview.headers['Content-Security-Policy'])
            self.assertIn('光合作用'.encode(), preview.data)
        finally:
            preview.close()

        fake_client = MagicMock()
        fake_client.model = 'test-model'
        fake_client._call_api_stream_yield.return_value = iter([
            ('content', '植物会利用光能。'),
        ])
        with patch('src.apps.aiteacher.routes.LLMClient', return_value=fake_client):
            chat = self.client.post('/aiteacher/api/chat', json={
                'message': '这份材料讲了什么？',
                'page_context': {
                    'material_id': material['id'],
                    'visible_text': '前端伪造的内容',
                },
            })
            self.assertEqual(chat.status_code, 200)
            self.assertIn('植物会利用光能'.encode(), chat.data)
        payload = fake_client._call_api_stream_yield.call_args.args[0]
        context_message = payload['messages'][-1]['content']
        self.assertIn('植物把光能变成化学能', context_message)
        self.assertNotIn('前端伪造的内容', context_message)

    def test_url_material_is_snapshotted(self):
        remote_html = '''<!doctype html><html><head><title>Python 入门</title></head>
        <body><h1>变量</h1><p>变量用于保存数据。</p></body></html>'''.encode()
        with patch.object(materials, '_download_url', return_value=(
            'https://example.com/python', remote_html,
            'text/html; charset=utf-8', 'utf-8')):
            response = self.client.post('/aiteacher/api/material/url', json={
                'url': 'https://example.com/python',
            })
        self.assertEqual(response.status_code, 200)
        material = response.get_json()['material']
        self.assertEqual(material['title'], 'Python 入门')
        self.assertIn('变量用于保存数据', material['text'])
        preview = self.client.get(material['viewer_url'])
        try:
            self.assertEqual(preview.status_code, 200)
        finally:
            preview.close()

    def test_ai_generated_material_is_stored_as_html(self):
        generated_html = '''<!doctype html><html><head><title>分数加法课</title></head>
        <body><h1>分数加法</h1><p>先把分母变成一样。</p></body></html>'''
        fake_client = MagicMock()
        fake_client.model_name = 'deepseek'
        fake_client.generate.return_value = generated_html
        with patch('src.apps.aiteacher.routes.LLMClient', return_value=fake_client):
            response = self.client.post('/aiteacher/api/material/generate', json={
                'requirement': '教我学习分数加法',
            })
        self.assertEqual(response.status_code, 200)
        material = response.get_json()['material']
        self.assertEqual(material['source_type'], 'generated')
        self.assertEqual(material['title'], '分数加法课')
        self.assertIn('先把分母变成一样', material['text'])
        saved = list(Path(self.temp_dir.name).rglob('*.html'))
        self.assertEqual(len(saved), 1)
        self.assertEqual(fake_client.generate.call_args.kwargs['thinking'], 'disabled')

    def test_ai_generation_discards_planning_text_before_html(self):
        generated = '''我先规划课程结构，然后再开始写页面。
        <!doctype html><html><head><title>勾股定理课</title></head>
        <body><h1>勾股定理</h1><p>在直角三角形中，两条直角边平方和等于斜边平方。</p>
        <section><h2>练习</h2><p>三、四、五是一组勾股数。</p></section></body></html>
        页面已经完成。'''
        fake_client = MagicMock()
        fake_client.generate.return_value = generated
        with patch('src.apps.aiteacher.routes.LLMClient', return_value=fake_client):
            response = self.client.post('/aiteacher/api/material/generate', json={
                'requirement': '勾股定理学习',
            })
        self.assertEqual(response.status_code, 200)
        saved_html = next(Path(self.temp_dir.name).rglob('*.html')).read_text()
        self.assertTrue(saved_html.lower().startswith('<!doctype html>'))
        self.assertNotIn('我先规划课程结构', saved_html)
        self.assertNotIn('页面已经完成', saved_html)

    def test_ai_generation_retries_when_first_response_has_no_html(self):
        fake_client = MagicMock()
        fake_client.generate.side_effect = [
            '我准备先设计学习目标、例题和练习。',
            '<!doctype html><html><head><title>重试成功</title></head><body>'
            '<h1>勾股定理</h1><p>这是重试后生成的完整教学内容，包含目标、讲解、例题、练习和答案提示。</p>'
            '</body></html>',
        ]
        with patch('src.apps.aiteacher.routes.LLMClient', return_value=fake_client):
            response = self.client.post('/aiteacher/api/material/generate', json={
                'requirement': '勾股定理学习',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['material']['title'], '重试成功')
        self.assertEqual(fake_client.generate.call_count, 2)

    def test_saved_materials_can_be_listed_and_reopened(self):
        upload = self.client.post(
            '/aiteacher/api/material/upload',
            data={'file': (io.BytesIO('重新打开这份材料'.encode()), 'saved.txt')},
            content_type='multipart/form-data',
        )
        material_id = upload.get_json()['material']['id']
        listing = self.client.get('/aiteacher/api/materials')
        self.assertEqual(listing.status_code, 200)
        listed_ids = [item['id'] for item in listing.get_json()['materials']]
        self.assertIn(material_id, listed_ids)
        self.assertIn('data/users/guest-', listing.get_json()['storage_path'])

        reopened = self.client.get('/aiteacher/api/materials/' + material_id)
        self.assertEqual(reopened.status_code, 200)
        self.assertIn('重新打开这份材料', reopened.get_json()['material']['text'])

    def test_login_does_not_hide_materials_created_in_guest_session(self):
        with self.client.session_transaction() as user_session:
            user_session['aiteacher_guest_id'] = 'before-login'
        uploaded = self.client.post(
            '/aiteacher/api/material/upload',
            data={'file': (io.BytesIO('登录前保存的材料'.encode()), 'before-login.txt')},
            content_type='multipart/form-data',
        ).get_json()['material']
        with self.client.session_transaction() as user_session:
            user_session['is_logged_in'] = True
            user_session['username'] = 'signed-in-user'
        listing = self.client.get('/aiteacher/api/materials').get_json()
        self.assertIn(uploaded['id'], [item['id'] for item in listing['materials']])
        self.assertEqual(len(listing['storage_paths']), 2)
        reopened = self.client.get('/aiteacher/api/materials/' + uploaded['id'])
        self.assertEqual(reopened.status_code, 200)

    def test_logged_in_material_is_saved_under_username(self):
        with self.client.session_transaction() as user_session:
            user_session['is_logged_in'] = True
            user_session['username'] = 'muusername'
        response = self.client.post(
            '/aiteacher/api/material/upload',
            data={'file': (io.BytesIO('学习正文'.encode()), 'notes.txt')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        user_folder = Path(self.temp_dir.name) / 'muusername'
        self.assertTrue(user_folder.is_dir())
        self.assertEqual(len(list(user_folder.glob('*.html'))), 1)

    def test_url_validation_allows_localhost_but_blocks_link_local(self):
        with patch('src.apps.aiteacher.materials.socket.getaddrinfo', return_value=[
            (2, 1, 6, '', ('127.0.0.1', 5058)),
            (10, 1, 6, '', ('::1', 5058, 0, 0)),
        ]):
            self.assertEqual(
                materials._validate_fetch_url('http://localhost:5058/lesson'),
                'http://localhost:5058/lesson',
            )
        with patch('src.apps.aiteacher.materials.socket.getaddrinfo', return_value=[
            (2, 1, 6, '', ('169.254.169.254', 80)),
        ]):
            with self.assertRaises(materials.MaterialError):
                materials._validate_fetch_url('http://169.254.169.254/latest')


class WebServerSmokeTest(unittest.TestCase):
    def setUp(self):
        web_app.config.update(TESTING=True)
        self.client = web_app.test_client()

    def test_homepage_is_the_ai_teacher_classroom(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('AI老师'.encode('utf-8'), response.data)
        self.assertIn('把想法说出来'.encode('utf-8'), response.data)

    def test_health_check_has_no_external_dependency(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'app': 'aiteacher', 'status': 'ok'})


if __name__ == '__main__':
    unittest.main()
