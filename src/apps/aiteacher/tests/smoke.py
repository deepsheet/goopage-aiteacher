#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from flask import Flask

from src.apps.aiteacher import aiteacher_bp
from src.apps.aiteacher.routes import MAX_HISTORY_ITEMS, _chat_messages
from src.web_server import app as web_app


class AITeacherSmokeTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SECRET_KEY='test')
        app.register_blueprint(aiteacher_bp, url_prefix='/aiteacher')
        self.client = app.test_client()

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
