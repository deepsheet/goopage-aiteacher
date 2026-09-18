#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A教师：带学习区上下文的 AI 陪练课堂。"""

from flask import Blueprint


aiteacher_bp = Blueprint(
    'aiteacher',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static',
)


from src.apps.aiteacher import routes  # noqa: E402,F401
