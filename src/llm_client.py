#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM 客户端：统一的大语言模型调用接口，支持 DeepSeek、Qwen 等多个模型

框架说明：
- 通过 config.config 中的 CURRENT_MODEL 切换模型（deepseek / qwen）
- 支持普通输出与流式输出（SSE）两种模式
- 提供 generate() 通用对话接口，业务模块在此基础上封装具体提示词
"""

import sys
import os
import json
import re
import requests

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL,
    QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL,
    CURRENT_MODEL
)
from src.logger import logger


class LLMClient:
    """
    统一的大语言模型客户端类，支持多个模型提供商
    """

    def __init__(self, model_name=None, language=None):
        """
        初始化 LLM 客户端

        @param {str} model_name - 可选的模型名称，如果不提供则使用配置文件中的 CURRENT_MODEL
        @param {str} language - 可选的语言代码（zh/en），用于提示词本地化
        """
        self.model_name = model_name if model_name else CURRENT_MODEL
        self.language = language if language else 'zh'
        logger.info(f"初始化 LLM 客户端，使用模型：{self.model_name}，语言：{self.language}")

        # 根据模型名称配置 API 参数
        if self.model_name.lower() == 'deepseek':
            self.api_key = DEEPSEEK_API_KEY
            self.api_url = DEEPSEEK_API_URL
            self.model = DEEPSEEK_MODEL
        elif self.model_name.lower() == 'qwen':
            self.api_key = QWEN_API_KEY
            self.api_url = QWEN_BASE_URL
            self.model = QWEN_MODEL
        else:
            logger.error(f"不支持的模型：{self.model_name}")
            raise ValueError(f"不支持的模型：{self.model_name}")

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    # ============================================================
    # 通用对话接口
    # ============================================================

    def generate(self, system_prompt, user_content, max_tokens=4096, temperature=0.7, stream=False):
        """
        通用对话接口：传入系统提示词与用户内容，返回模型生成结果

        @param {str} system_prompt - 系统提示词（角色设定）
        @param {str} user_content - 用户输入内容
        @param {int} max_tokens - 最大输出 token 数
        @param {float} temperature - 采样温度
        @param {bool} stream - 是否使用流式输出（适合长内容）
        @return {str} - 模型生成的文本内容
        """
        logger.info(f"开始调用 LLM，max_tokens={max_tokens}, stream={stream}")
        prompt = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream
        }
        response = self._call_api(prompt)
        return self._parse_response(response)

    def generate_with_messages(self, messages, max_tokens=4096, temperature=0.7, stream=False):
        """
        多轮对话接口：直接传入完整 messages 列表

        @param {list} messages - OpenAI 格式的 messages 列表
        @param {int} max_tokens - 最大输出 token 数
        @param {float} temperature - 采样温度
        @param {bool} stream - 是否使用流式输出
        @return {str} - 模型生成的文本内容
        """
        logger.info(f"开始调用 LLM（多轮对话），messages数={len(messages)}, stream={stream}")
        prompt = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream
        }
        response = self._call_api(prompt)
        return self._parse_response(response)

    def generate_stream_yield(self, system_prompt, user_content, max_tokens=4096, temperature=0.7):
        """
        流式生成接口（逐 token 输出）

        调用方通过 for type, text in client.generate_stream_yield(...) 接收：
        - ('reasoning', text) 模型思考过程（仅展示用）
        - ('content', text)   实际生成内容

        @param {str} system_prompt - 系统提示词
        @param {str} user_content - 用户输入内容
        @return {generator} - 逐个产出 (type, text) 元组
        """
        prompt = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        yield from self._call_api_stream_yield(prompt)

    # ============================================================
    # API 调用核心
    # ============================================================

    def _call_api(self, prompt):
        """
        调用 LLM API

        @param {dict} prompt - API 请求参数（必须包含 'stream' 字段）
        @return {dict|str} - API 响应（非流式）或完整内容（流式）
        """
        try:
            # 从 prompt 中读取 stream 配置，决定使用流式还是非流式调用
            use_stream = prompt.get('stream', False)
            if use_stream:
                logger.info("检测到 stream=true，使用流式输出模式处理长内容...")
                return self._call_api_stream(prompt)
            else:
                logger.info("检测到 stream=false，使用非流式模式")
                # 确保非流式模式下 stream 参数为 False（双重保障）
                prompt['stream'] = False

                # 从 prompt 中获取 timeout，默认 180秒
                timeout = prompt.get('timeout', 180)

                logger.info(f"API请求 - model: {prompt.get('model')}, messages数量: {len(prompt.get('messages', []))}, timeout: {timeout}秒")

                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=prompt,
                    timeout=timeout
                )

                # 如果失败，记录响应详情
                if response.status_code != 200:
                    logger.error(f"API响应状态码: {response.status_code}")
                    logger.error(f"API响应内容: {response.text[:500]}")

                response.raise_for_status()

                # 检查响应是否为空
                if not response.text or len(response.text.strip()) == 0:
                    logger.error("API返回空响应")
                    raise ValueError("API返回空响应")

                # 尝试解析 JSON，如果失败则检查是否为 SSE 流式响应
                try:
                    return response.json()
                except ValueError:
                    # 检测是否为 SSE 流式响应格式（兼容某些 API 忽略 stream 参数的情况）
                    if response.text.startswith('data: '):
                        logger.warning("API返回SSE流式响应（尽管已设置stream=false），切换到流式处理模式")
                        return self._parse_sse_response(response.text)
                    else:
                        logger.error(f"API返回非JSON响应，前500字符: {response.text[:500]}")
                        raise
        except requests.exceptions.RequestException as e:
            logger.error(f"{self.model_name} API 请求失败：{str(e)}")
            raise

    def _call_api_stream(self, prompt):
        """
        使用流式输出调用 API，适合处理超长内容

        @param {dict} prompt - API 请求参数
        @return {str} - 完整的内容
        """
        try:
            # 启用流式输出
            prompt["stream"] = True
            # 流式输出时不设置 max_tokens，让 AI 自然输出完成
            if "max_tokens" in prompt:
                del prompt["max_tokens"]

            logger.info("开始流式接收数据...")

            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=prompt,
                timeout=600,
                stream=True
            )
            response.raise_for_status()

            # 收集所有流式片段
            full_content = []
            chunk_count = 0
            error_count = 0

            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data = line_str[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            # 只使用 content，忽略 reasoning_content（思考过程）
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                full_content.append(content)
                                chunk_count += 1
                        except json.JSONDecodeError:
                            error_count += 1
                            # 备用解析方案
                            try:
                                match = re.search(r'"content":"([^"]*(?:\\"[^"]*)*)"', data)
                                if match:
                                    content = match.group(1).replace('\\"', '"')
                                    full_content.append(content)
                                    chunk_count += 1
                            except Exception:
                                continue

            # 合并所有片段
            final_content = ''.join(full_content)
            logger.info(f"流式接收完成，共 {chunk_count} 个片段，总长度：{len(final_content)}")
            return final_content

        except Exception as e:
            logger.error(f"流式输出失败：{str(e)}")
            if 'full_content' in locals() and full_content:
                partial_content = ''.join(full_content)
                logger.warning(f"返回已接收的部分内容，长度：{len(partial_content)}")
                return partial_content
            raise

    def _call_api_stream_yield(self, prompt):
        """
        流式调用 API，逐个 yield (type, text) 元组给调用方

        @param {dict} prompt - API 请求参数
        @yield {tuple} - ('reasoning', text) 或 ('content', text)
        """
        # 启用流式
        prompt["stream"] = True

        # 流式模式不需要 max_tokens，让模型自然完成
        if "max_tokens" in prompt:
            del prompt["max_tokens"]

        logger.info("开始流式接收数据（逐 token yield）...")

        response = requests.post(
            self.api_url,
            headers=self.headers,
            json=prompt,
            timeout=3600,  # 流式模式用 1 小时超时作为安全兜底
            stream=True
        )
        response.raise_for_status()

        content_count = 0
        reasoning_count = 0

        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data = line_str[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        reasoning = delta.get("reasoning_content", "")

                        if reasoning:
                            yield ('reasoning', reasoning)
                            reasoning_count += 1

                        if content:
                            yield ('content', content)
                            content_count += 1
                    except json.JSONDecodeError:
                        # 备用解析只处理 content
                        try:
                            match = re.search(r'"content":"([^"]*(?:\\"[^"]*)*)"', data)
                            if match:
                                content = match.group(1).replace('\\"', '"')
                                if content:
                                    yield ('content', content)
                                    content_count += 1
                        except Exception:
                            continue

        logger.info(f"流式接收完成，content: {content_count} 片段, reasoning: {reasoning_count} 片段")

    # ============================================================
    # 响应解析
    # ============================================================

    def _parse_sse_response(self, sse_text):
        """
        解析 SSE (Server-Sent Events) 格式的响应

        @param {str} sse_text - SSE 格式的响应文本
        @return {str} - 提取的完整内容
        """
        try:
            full_content = []
            lines = sse_text.split('\n')

            for line in lines:
                line = line.strip()
                if line.startswith('data: '):
                    data = line[6:]  # 移除 "data: " 前缀

                    # 跳过结束标记
                    if data == '[DONE]':
                        break

                    try:
                        chunk = json.loads(data)
                        # 从 choices 中提取内容
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                full_content.append(content)
                    except json.JSONDecodeError:
                        continue

            final_content = ''.join(full_content)
            logger.info(f"SSE响应解析完成，共 {len(full_content)} 个片段，总长度：{len(final_content)}")
            return final_content

        except Exception as e:
            logger.error(f"SSE响应解析失败：{str(e)}")
            raise ValueError(f"SSE响应解析失败：{str(e)}")

    def _parse_response(self, response):
        """
        解析 API 响应获取生成的内容

        @param {dict|str} response - API 响应（非流式）或完整内容（流式）
        @return {str} - 解析后的内容
        """
        try:
            # 如果是流式输出，response 直接是字符串
            if isinstance(response, str):
                content = response
                logger.info(f"流式模式，内容长度: {len(content)}")
            else:
                # 非流式输出，从 JSON 中提取
                msg = response["choices"][0]["message"]

                # DeepSeek 模型有 reasoning_content（思考过程）和 content（最终输出）
                # 我们只需要 content，完全忽略 reasoning_content
                content = msg.get("content", "")
                reasoning_content = msg.get("reasoning_content", "")

                if reasoning_content:
                    logger.info(f"模型返回了reasoning_content（{len(reasoning_content)}字符），已自动忽略，只使用content")

                if not content:
                    logger.error("content字段为空！API可能出现问题")
                    # 如果 content 为空，尝试从 reasoning_content 中提取最终输出
                    if reasoning_content:
                        logger.info("尝试从reasoning_content中提取最终输出...")
                        content = reasoning_content

            # 清理可能的 markdown 代码块标记
            content = self._clean_code_block_markers(content)

            logger.info(f"最终返回内容长度: {len(content)}")
            return content
        except (KeyError, IndexError) as e:
            logger.error(f"解析 API 响应失败：{str(e)}")
            logger.error(f"API 响应：{json.dumps(response, ensure_ascii=False)[:1000]}")
            raise

    def _extract_json_from_response(self, response_text):
        """
        从 LLM 响应中提取 JSON 对象

        @param {str} response_text - LLM 返回的文本
        @return {dict|None} - 解析出的 JSON 对象，失败返回 None
        """
        try:
            return json.loads(response_text)
        except Exception:
            pass
        try:
            match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return None

    def _clean_code_block_markers(self, content):
        """
        清理 LLM 输出中的代码块标记

        @param {str} content - LLM 输出的内容
        @return {str} - 清理后的内容
        """
        # 移除 ```html 或 ``` 等代码块标记
        content = re.sub(r'^```html\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'^```\s*$', '', content, flags=re.MULTILINE)
        content = content.strip()
        return content


def main():
    """命令行测试入口"""
    import argparse

    parser = argparse.ArgumentParser(description='LLM 客户端测试')
    parser.add_argument('--model', default=CURRENT_MODEL, help='模型名称 (deepseek/qwen)')
    parser.add_argument('--prompt', default='你好，请简单介绍一下你自己。', help='测试提示词')
    parser.add_argument('--stream', action='store_true', help='使用流式输出')
    args = parser.parse_args()

    client = LLMClient(model_name=args.model)
    print(f"使用模型：{args.model}，流式：{args.stream}")
    result = client.generate(
        system_prompt="你是一个乐于助人的AI助手。",
        user_content=args.prompt,
        stream=args.stream
    )
    print(result)


if __name__ == "__main__":
    main()
