from urllib.parse import urlparse
import requests
import re
from agent.seo_agent.pojo import ProductInfo
from langgraph.prebuilt import create_react_agent
from agent.llm import create_azure_llm
from agent.seo_agent.prompt import GET_KEYWORDS_AGENT_PROMPT_TEMPLATE, CREATE_TITLE_AGENT_PROMPT_TEMPLATE
from agent.seo_agent.pojo import Keywords
# 采用reAct

from agent.tool.tools import judge_if_brand, product_tavily_search


class GetKeywordsAgent():

    def __init__(self) -> None:
        self.llm = create_azure_llm()
        self.tool_list = [judge_if_brand, product_tavily_search]

    async def invoke(self, product_title: str, product_description: str, product_category: str) -> Keywords:
        prompt_template = GET_KEYWORDS_AGENT_PROMPT_TEMPLATE
        prompt = prompt_template.format(
            product_title=product_title, product_description=product_description, product_category=product_category)
        agent = create_react_agent(model=self.llm, tools=self.tool_list,
                                   prompt=prompt, response_format=Keywords)
        agent_result = await agent.ainvoke({})
        keywords: Keywords = agent_result["structured_response"]
        return keywords


class CreateTitleAgent():
    def __init__(self) -> None:
        self.llm = create_azure_llm()
        self.tool_list = [judge_if_brand, product_tavily_search]

    async def invoke(self, product_title: str, product_description: str, suggest: str, keywords: Keywords) -> ProductInfo:
        prompt_template = CREATE_TITLE_AGENT_PROMPT_TEMPLATE
        prompt = prompt_template.format(
            product_title=product_title, product_description=product_description, suggest=suggest, keywords=str(keywords))
        agent = create_react_agent(model=self.llm, tools=self.tool_list,
                                   prompt=prompt, response_format=ProductInfo)
        agent_result = await agent.ainvoke({})
        product_info: ProductInfo = agent_result["structured_response"]
        return product_info


# 接入gradio的agent


class SEOAgent():
    def __init__(self, user_name) -> None:
        self.user_name = user_name

    def predict(self, user_question, chatbot):
        # 假如len(chatbot)==1则为第一次回复
        if len(chatbot) == 1:
            # 第一次回复
            # 判断user_question是否为链接，使用re来获取链接部分
            url_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'
            urls = re.findall(url_pattern, user_question)

            if urls:
                # 如果包含链接，进行SEO分析
                url = urls[0]
                return self.analyze_seo(url)
            else:
                # 如果不包含链接，提供SEO建议
                return self.provide_seo_advice(user_question)
        else:
            # 非第一次回复
            return self.handle_follow_up(user_question, chatbot)

    def analyze_seo(self, url):
        """分析URL的SEO情况"""
        try:
            response = requests.get(url, timeout=10)
            content = response.text

            # 基本的SEO检查
            seo_analysis = []

            # 检查标题
            title_match = re.search(
                r'<title>(.*?)</title>', content, re.IGNORECASE)
            if title_match:
                title = title_match.group(1)
                seo_analysis.append(f"✅ 页面标题: {title}")
                if len(title) < 30:
                    seo_analysis.append("⚠️ 标题可能过短，建议30-60字符")
                elif len(title) > 60:
                    seo_analysis.append("⚠️ 标题可能过长，建议30-60字符")
            else:
                seo_analysis.append("❌ 未找到页面标题")

            # 检查meta描述
            meta_desc_match = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', content, re.IGNORECASE)
            if meta_desc_match:
                meta_desc = meta_desc_match.group(1)
                seo_analysis.append(f"✅ Meta描述: {meta_desc}")
                if len(meta_desc) < 120:
                    seo_analysis.append("⚠️ Meta描述可能过短，建议120-160字符")
                elif len(meta_desc) > 160:
                    seo_analysis.append("⚠️ Meta描述可能过长，建议120-160字符")
            else:
                seo_analysis.append("❌ 未找到Meta描述")

            # 检查H1标签
            h1_count = len(re.findall(
                r'<h1[^>]*>.*?</h1>', content, re.IGNORECASE))
            if h1_count == 1:
                seo_analysis.append("✅ 页面有且仅有一个H1标签")
            elif h1_count == 0:
                seo_analysis.append("❌ 页面缺少H1标签")
            else:
                seo_analysis.append(f"⚠️ 页面有{h1_count}个H1标签，建议只有一个")

            # 检查图片alt属性
            img_tags = re.findall(r'<img[^>]*>', content, re.IGNORECASE)
            img_with_alt = len(re.findall(
                r'<img[^>]*alt=["\'][^"\']*["\'][^>]*>', content, re.IGNORECASE))
            if img_tags:
                alt_percentage = (img_with_alt / len(img_tags)) * 100
                seo_analysis.append(f"📊 图片alt属性覆盖率: {alt_percentage:.1f}% ({
                                    img_with_alt}/{len(img_tags)})")
                if alt_percentage < 80:
                    seo_analysis.append("⚠️ 建议为所有图片添加alt属性")

            return "\n".join(seo_analysis)

        except Exception as e:
            return f"❌ 分析失败: {str(e)}"

    def provide_seo_advice(self, question):
        """提供SEO建议"""
        advice = [
            "🔍 SEO优化建议：",
            "",
            "1. **关键词优化**",
            "   - 在标题、描述、内容中合理使用关键词",
            "   - 避免关键词堆砌",
            "",
            "2. **内容质量**",
            "   - 提供有价值、原创的内容",
            "   - 保持内容更新频率",
            "",
            "3. **技术SEO**",
            "   - 确保网站加载速度快",
            "   - 优化移动端体验",
            "   - 使用HTTPS协议",
            "",
            "4. **用户体验**",
            "   - 清晰的网站结构",
            "   - 易于导航",
            "   - 减少跳出率",
            "",
            "请提供具体网址，我可以为您进行详细的SEO分析！"
        ]
        return "\n".join(advice)

    def handle_follow_up(self, user_question, chatbot):
        """处理后续对话"""
        # 简单的对话处理逻辑
        if "谢谢" in user_question or "感谢" in user_question:
            return "不客气！如果您还有其他SEO相关问题，随时可以问我。"
        elif "帮助" in user_question or "怎么" in user_question:
            return "我可以帮您：\n1. 分析网站SEO情况\n2. 提供SEO优化建议\n3. 解答SEO相关问题\n\n请提供网址或具体问题！"
        else:
            return "我理解您的问题。为了更好地帮助您，请提供具体的网址或更详细的问题描述。"
