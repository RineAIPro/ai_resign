# AI服务
# 修改时间：2026/05/08
# 功能：AI接口（Claude/OpenAI/自定义），测试连接，自动生成

import httpx


class AIService:
    def __init__(self, config: dict):
        self.config = config

    @property
    def provider(self) -> str:
        return self.config.get("ai_provider", "claude")

    @property
    def api_key(self) -> str:
        return self.config.get("ai_api_key", "")

    @property
    def base_url(self) -> str:
        return self.config.get("ai_base_url", "https://api.anthropic.com")

    @property
    def model(self) -> str:
        if self.config.get("ai_custom_model"):
            return self.config["ai_custom_model"]
        model = self.config.get("ai_model", "")
        # 提取括号前的模型ID
        if "（" in model:
            return model.split("（")[0]
        return model

    def is_configured(self) -> bool:
        return bool(self.api_key and self.config.get("ai_enabled"))

    # 修改时间：2026/05/09 - 超时和最大tokens从配置读取
    @property
    def timeout(self) -> int:
        return self.config.get("ai_timeout", 180)

    @property
    def max_tokens(self) -> int:
        return self.config.get("ai_max_tokens", 8192)

    async def test_connection(self) -> tuple[bool, str]:
        """测试AI连接"""
        if not self.api_key:
            return False, "API Key未填写"

        try:
            if self.provider == "claude":
                async with httpx.AsyncClient(timeout=15) as client:
                    # 修改时间：2026/05/08 - 自定义BaseURL不发送anthropic-version头（DeepSeek等代理不支持）
                    headers = {
                        "x-api-key": self.api_key,
                        "content-type": "application/json"
                    }
                    # 仅官方Anthropic API发送版本头
                    if "api.anthropic.com" in self.base_url:
                        headers["anthropic-version"] = "2023-06-01"
                    resp = await client.post(
                        f"{self.base_url}/v1/messages",
                        json={
                            "model": self.model,
                            "max_tokens": 1,
                            "messages": [{"role": "user", "content": "hi"}]
                        },
                        headers=headers
                    )
                    if resp.status_code == 200:
                        return True, "连接成功"
                    # 返回API实际错误信息
                    try:
                        err = resp.json()
                        err_msg = err.get('error', {}).get('message', '') or str(err)
                    except Exception:
                        err_msg = resp.text[:300]
                    return False, f"HTTP {resp.status_code}: {err_msg}"
            elif self.provider == "openai":
                async with httpx.AsyncClient(timeout=15) as client:
                    # 修改时间：2026/05/08 - 改进错误信息返回
                    resp = await client.get(
                        f"{self.base_url}/models",
                        headers={"Authorization": f"Bearer {self.api_key}"}
                    )
                    if resp.status_code == 200:
                        return True, "连接成功"
                    try:
                        err = resp.json()
                        err_msg = err.get('error', {}).get('message', '')
                    except Exception:
                        err_msg = resp.text[:200]
                    return False, err_msg or f"HTTP {resp.status_code}"
            else:
                return True, "自定义提供商，跳过验证"
        except Exception as e:
            return False, str(e)

    async def generate_text(self, prompt: str, system: str = "") -> str:
        """调用AI生成文本"""
        if not self.is_configured():
            return ""

        if self.provider == "claude":
            return await self._call_claude(prompt, system)
        elif self.provider == "openai":
            return await self._call_openai(prompt, system)
        else:
            return await self._call_openai(prompt, system)  # 自定义走OpenAI兼容格式

    async def _call_claude(self, prompt: str, system: str = "") -> str:
        # 修改时间：2026/05/09 - 非官方API不发送anthropic-version头，与test_connection保持一致
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
        }
        if "api.anthropic.com" in self.base_url:
            headers["anthropic-version"] = "2023-06-01"
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 修改时间：2026/05/09 - 手动处理HTTP错误，返回API实际错误信息
            resp = await client.post(f"{self.base_url}/v1/messages", json=body, headers=headers)
            if resp.status_code != 200:
                try:
                    err = resp.json()
                    err_msg = err.get('error', {})
                    if isinstance(err_msg, dict):
                        err_msg = err_msg.get('message', str(err_msg))
                except Exception:
                    err_msg = resp.text[:500]
                raise Exception(f"HTTP {resp.status_code}: {err_msg}")
            data = resp.json()
            # 修改时间：2026/05/09 - 兼容DeepSeek等API，跳过thinking块，取text块
            content = data.get("content", [])
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")
            # 没有text块时兜底：取第一个有text字段的块
            for block in content:
                if isinstance(block, dict) and block.get("text"):
                    return block["text"]
            # 兼容OpenAI格式
            choices = data.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                return msg.get("content", "")
            return str(data)

    async def _call_openai(self, prompt: str, system: str = "") -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {"model": self.model, "messages": messages, "max_tokens": self.max_tokens}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
