import requests
import json
import re
import time
from typing import List, Dict


class OllamaQwenSystem:
    def __init__(self, base_url='http://localhost:11434'):
        self.base_url = base_url
        self.embedding_model = 'qwen3-embedding:4b'
        self.llm_model = 'qwen3:30b-a3b-instruct-2507-q4_K_M'  # 使用您指定的Qwen大模型

    def check_service_availability(self) -> bool:
        """检查Ollama服务是否可用"""
        try:
            response = requests.get(f'{self.base_url}/api/tags', timeout=30)
            if response.status_code == 200:
                print('✅ Ollama服务可用')
                # 检查模型是否存在
                models = response.json().get('models', [])
                embedding_model_exists = any(
                    model.get('name', '').startswith(self.embedding_model.split(':')[0])
                    for model in models
                )
                llm_model_exists = any(
                    model.get('name', '').startswith(self.llm_model.split(':')[0])
                    for model in models
                )
                if embedding_model_exists:
                    print(f'✅ 嵌入模型 {self.embedding_model} 可用')
                else:
                    print(f'⚠️  嵌入模型 {self.embedding_model} 不存在，请先拉取模型')
                if llm_model_exists:
                    print(
                        f'✅ 大语言模型 {self.llm_model} 可用 (注意：该模型较大，处理速度可能较慢但准确性更高)'
                    )
                else:
                    print(f'⚠️  大语言模型 {self.llm_model} 不存在，请先拉取模型')
                    print('  注意：该模型较大，请确保有足够的磁盘空间')
                return embedding_model_exists and llm_model_exists
            else:
                print(f'❌ Ollama服务不可用: {response.status_code}')
                return False
        except Exception as e:
            print(f'❌ 无法连接到Ollama服务: {e}')
            return False

    def check_llm_model_availability(self) -> bool:
        """专门检查大语言模型是否可用"""
        try:
            response = requests.get(f'{self.base_url}/api/tags', timeout=30)
            if response.status_code == 200:
                models = response.json().get('models', [])
                llm_model_exists = any(
                    model.get('name', '').startswith(self.llm_model.split(':')[0])
                    for model in models
                )
                return llm_model_exists
            else:
                print(f'❌ Ollama服务不可用: {response.status_code}')
                return False
        except Exception as e:
            print(f'❌ 无法连接到Ollama服务: {e}')
            return False

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """获取文本嵌入向量"""
        embeddings = []
        for i, text in enumerate(texts):
            # 添加进度提示
            if len(texts) > 10 and i % 10 == 0:
                print(f'  处理Embedding {i + 1}/{len(texts)}')

            payload = {'model': self.embedding_model, 'prompt': text}
            try:
                print(f'    发送Embedding请求: {len(text)} 字符')
                response = requests.post(
                    f'{self.base_url}/api/embeddings', json=payload, timeout=60
                )
                print(f'    收到Embedding响应: {response.status_code}')
                if response.status_code == 200:
                    embedding = response.json().get('embedding', [])
                    print(f'    Embedding维度: {len(embedding)}')
                    embeddings.append(embedding)
                else:
                    print(
                        f'  Embedding API错误: {response.status_code} - {response.text}'
                    )
                    embeddings.append([])
            except Exception as e:
                print(f'  Embedding调用异常: {e}')
                embeddings.append([])
        return embeddings

    def chat_completion(self, messages: List[Dict]) -> str:
        """调用Qwen大模型进行对话"""
        # 调用前检查LLM模型是否可用
        if not self.check_llm_model_availability():
            return f'模型 {self.llm_model} 不可用，请检查Ollama服务和模型配置'

        # 不再限制消息内容长度，允许完整分析

        payload = {
            'model': self.llm_model,
            'messages': messages,
            'stream': False,
            'options': {
                'temperature': 0.7,  # 控制随机性
                'top_p': 0.9,
            },
        }

        # 添加重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(
                    f'  正在调用大模型 {self.llm_model}... (尝试 {attempt + 1}/{max_retries})'
                )
                print(f'  请求负载大小: {len(str(payload))} 字符')
                # 增加超时时间到10分钟，以适应大型模型的处理需求
                print('  发送请求到Ollama API...')
                response = requests.post(
                    f'{self.base_url}/api/chat', json=payload, timeout=600
                )  # 10分钟超时
                print('  收到API响应')
                if response.status_code == 200:
                    print('  解析API响应...')
                    result = response.json()['message']['content']
                    print('  大模型调用完成')
                    return result
                else:
                    error_msg = (
                        f'模型调用失败: {response.status_code} - {response.text}'
                    )
                    print(f'  {error_msg}')
                    if attempt < max_retries - 1:
                        print(f'  将在5秒后进行第{attempt + 2}次尝试...')
                        time.sleep(5)
                    else:
                        return error_msg
            except Exception as e:
                error_msg = f'API错误: {e}'
                print(f'  {error_msg}')
                if attempt < max_retries - 1:
                    print(f'  将在5秒后进行第{attempt + 2}次尝试...')
                    time.sleep(5)
                else:
                    return error_msg
        # 如果所有重试都失败了，返回默认错误消息
        return '模型调用失败：所有重试均已失败'


class IntelligentBidEvaluator:
    def __init__(self):
        self.ollama = OllamaQwenSystem()

    def evaluate_bid_documents(self, tender_text: str, bid_text: str) -> Dict:
        """智能评价标书 - 协同工作流程"""

        # 第一步：使用Embedding进行初步筛选（快速）
        print('🔍 使用Embedding进行初步筛选...')
        key_sections = self.extract_key_sections_using_embedding(tender_text, bid_text)

        # 第二步：使用Qwen大模型进行深度分析（精准）
        print('🧠 使用Qwen大模型进行深度分析...')
        evaluation_results = self.deep_analysis_using_llm(
            tender_text, bid_text, key_sections
        )

        # 第三步：生成综合评价报告
        print('📊 生成综合评价报告...')
        final_report = self.generate_comprehensive_report(evaluation_results)

        return final_report

    def extract_key_sections_using_embedding(
        self, tender_text: str, bid_text: str
    ) -> Dict:
        """使用Embedding快速提取关键章节"""
        print('开始提取关键章节...')

        # 定义需要关注的关键条款类型
        key_clause_types = [
            '技术方案',
            '报价条款',
            '资质要求',
            '实施计划',
            '质量标准',
            '售后服务',
            '违约责任',
            '付款方式',
            '商务条款',
            '服务部分',
            '技术部分',
            '价格部分',
            # 添加评标相关的关键词
            '评分标准',
            '评审标准',
            '评标细则',
            '打分标准',
            '计分方法',
            '分值',
            '权重',
            '满分',
            '评标办法',
        ]

        print(f'关键词类型数量: {len(key_clause_types)}')

        # 将文档分块
        print('正在对招标文件进行分块...')
        tender_chunks = self.chunk_text(tender_text, chunk_size=300)
        print(f'招标文件分块数量: {len(tender_chunks)}')

        print('正在对投标文件进行分块...')
        bid_chunks = self.chunk_text(bid_text, chunk_size=300)
        print(f'投标文件分块数量: {len(bid_chunks)}')

        # 获取嵌入向量
        print('正在获取招标文件嵌入向量...')
        tender_embeddings = self.ollama.get_embeddings(tender_chunks)

        print('正在获取投标文件嵌入向量...')
        bid_embeddings = self.ollama.get_embeddings(bid_chunks)

        print('正在获取关键词嵌入向量...')
        clause_embeddings = self.ollama.get_embeddings(key_clause_types)

        # 找出相关度高的章节
        print('正在查找招标文件相关章节...')
        tender_relevant = self.find_relevant_chunks(
            tender_chunks, tender_embeddings, clause_embeddings, key_clause_types
        )

        print('正在查找投标文件相关章节...')
        bid_relevant = self.find_relevant_chunks(
            bid_chunks, bid_embeddings, clause_embeddings, key_clause_types
        )

        relevant_sections = {
            'tender': tender_relevant,
            'bid': bid_relevant,
        }

        # 添加专门的评标信息提取
        print('正在提取结构化评标信息...')
        tender_evaluation_info = self.extract_structured_evaluation_info(tender_text)
        tender_scoring_rules = self.extract_scoring_rules(tender_text)

        # 将结构化信息转换为字符串格式存储
        relevant_sections['tender_evaluation_info'] = json.dumps(
            tender_evaluation_info, ensure_ascii=False, indent=2
        )
        relevant_sections['tender_scoring_rules'] = json.dumps(
            tender_scoring_rules, ensure_ascii=False, indent=2
        )

        # 添加进度信息
        tender_len = len(relevant_sections['tender'])
        bid_len = len(relevant_sections['bid'])
        print(f'提取的关键招标内容长度: {tender_len} 字符')
        print(f'提取的关键投标内容长度: {bid_len} 字符')
        print('关键章节提取完成')

        return relevant_sections

    def _compress_content_for_llm(self, key_sections: Dict) -> Dict:
        """压缩发送给大模型的内容，只保留最相关的部分"""
        compressed_sections = {}

        # 对于招标文件和投标文件的关键章节，只保留前3000个字符
        for key in ['tender', 'bid']:
            if key in key_sections and key_sections[key]:
                content = key_sections[key]
                if len(content) > 3000:
                    print(f'  压缩{key}内容从{len(content)}到3000字符')
                    # 保留前3000个字符，但确保不截断句子
                    compressed_content = content[:3000]
                    last_period = compressed_content.rfind('。')
                    if last_period > 2000:  # 如果最后的句号在2000字符之后
                        compressed_content = compressed_content[: last_period + 1]
                    compressed_sections[key] = compressed_content
                else:
                    compressed_sections[key] = content
            else:
                compressed_sections[key] = key_sections.get(key, '')

        # 对于评标信息，保留完整内容但限制长度
        for key in ['tender_evaluation_info', 'tender_scoring_rules']:
            if key in key_sections and key_sections[key]:
                content = key_sections[key]
                if len(content) > 5000:
                    print(f'  压缩{key}内容从{len(content)}到5000字符')
                    compressed_sections[key] = content[:5000]
                else:
                    compressed_sections[key] = content
            else:
                compressed_sections[key] = key_sections.get(key, '')

        return compressed_sections

    def _compress_prompt(self, prompt: str) -> str:
        """压缩提示词"""
        if len(prompt) <= 10000:
            return prompt

        # 保留系统指令和关键部分
        lines = prompt.split('\n')
        compressed_lines = []
        current_length = 0
        max_length = 8000  # 留一些空间给响应

        for line in lines:
            if current_length + len(line) > max_length:
                break
            compressed_lines.append(line)
            current_length += len(line) + 1  # +1 for newline

        print(f'  提示词已压缩到{current_length}字符')
        return '\n'.join(compressed_lines)

    def _compress_evaluation_results(self, evaluation_results: Dict) -> Dict:
        """压缩评审结果"""
        compressed_results = {}

        # 限制详细评价的长度
        if 'detailed_evaluation' in evaluation_results:
            detailed = evaluation_results['detailed_evaluation']
            compressed_detailed = {}

            for key, value in detailed.items():
                if isinstance(value, str) and len(value) > 1000:
                    print(f'  压缩详细评价项 {key} 从{len(value)}到1000字符')
                    compressed_detailed[key] = value[:1000] + '... (内容已截断)'
                else:
                    compressed_detailed[key] = value

            compressed_results['detailed_evaluation'] = compressed_detailed
        else:
            compressed_results['detailed_evaluation'] = evaluation_results.get(
                'detailed_evaluation', {}
            )

        # 保留其他关键字段
        for key in ['summary', 'recommendation']:
            if key in evaluation_results:
                content = evaluation_results[key]
                if isinstance(content, str) and len(content) > 2000:
                    print(f'  压缩{key}从{len(content)}到2000字符')
                    compressed_results[key] = content[:2000] + '... (内容已截断)'
                else:
                    compressed_results[key] = content
            else:
                compressed_results[key] = evaluation_results.get(key, '')

        return compressed_results

    def _compress_json_for_report(self, data: Dict) -> str:
        """压缩JSON数据用于报告生成"""
        # 只保留关键字段，去除冗余信息
        compressed_data = {}

        # 保留主要的评价结果
        if 'detailed_evaluation' in data:
            detailed = data['detailed_evaluation']
            # 只保留评分相关的字段
            compressed_detailed = {}
            for key in [
                'technical_score',
                'commercial_score',
                'service_score',
                'price_score',
            ]:
                if key in detailed:
                    compressed_detailed[key] = detailed[key]
            # 保留简短的评价说明
            for key in ['evaluation_summary', 'main_advantages', 'potential_risks']:
                if key in detailed and isinstance(detailed[key], str):
                    compressed_detailed[key] = (
                        detailed[key][:500] + '...'
                        if len(detailed[key]) > 500
                        else detailed[key]
                    )
            compressed_data['detailed_evaluation'] = compressed_detailed

        # 保留摘要和推荐意见
        for key in ['summary', 'recommendation']:
            if key in data and isinstance(data[key], str):
                compressed_data[key] = (
                    data[key][:1000] + '...' if len(data[key]) > 1000 else data[key]
                )

        # 生成压缩后的JSON字符串
        return json.dumps(compressed_data, ensure_ascii=False, indent=2)

    def deep_analysis_using_llm(
        self, tender_text: str, bid_text: str, key_sections: Dict
    ) -> Dict:
        """使用Qwen大模型进行深度分析"""
        print('开始构建评审提示词...')

        # 智能压缩关键章节内容，只保留最相关的部分
        truncated_key_sections = self._compress_content_for_llm(key_sections)

        # 构建专业的评审提示词
        evaluation_prompt = f"""
        你是一名资深的投标评审专家。请对以下招标文件和投标书进行专业评审：

        【招标文件关键要求】
        {truncated_key_sections['tender']}

        【投标书响应内容】  
        {truncated_key_sections['bid']}
        
        【招标文件评标信息】
        评标结构信息：{truncated_key_sections.get('tender_evaluation_info', '{}')}
        评分规则：{truncated_key_sections.get('tender_scoring_rules', '[]')}

        请从以下维度进行评价：
        1. 商务部分匹配度（0-18分）
        2. 服务部分匹配度（0-10分） 
        3. 技术部分匹配度（0-32分）
        4. 价格分（0-40分）

        请特别关注招标文件中的评分标准和细则，并据此对标书进行详细评审。

        请以JSON格式返回评价结果，包含：
        - 各维度评分
        - 具体评价说明
        - 主要优势
        - 潜在风险
        - 改进建议
        """

        # 如果提示词过长，进行进一步压缩
        if len(evaluation_prompt) > 10000:  # 10K字符限制
            print(f'  提示词过长 ({len(evaluation_prompt)} 字符)，正在进行压缩...')
            evaluation_prompt = self._compress_prompt(evaluation_prompt)

        print(f'  评审提示词长度: {len(evaluation_prompt)} 字符')

        messages = [
            {
                'role': 'system',
                'content': '你是一名专业的投标评审专家，擅长分析标书的技术和商务条款，特别关注评分标准和细则。',
            },
            {'role': 'user', 'content': evaluation_prompt},
        ]

        print('正在调用Qwen大模型进行深度分析...')
        llm_response = self.ollama.chat_completion(messages)
        print('大模型分析完成')

        # 解析大模型的响应
        print('正在解析大模型响应...')
        result = self.parse_llm_evaluation(llm_response)
        print('大模型响应解析完成')
        return result

    def generate_comprehensive_report(self, evaluation_results: Dict) -> Dict:
        """生成综合评价报告"""
        print('正在生成综合评价报告...')

        # 压缩评审结果内容
        truncated_evaluation_results = self._compress_evaluation_results(
            evaluation_results
        )

        # 进一步压缩JSON内容，只保留关键信息
        compressed_json = self._compress_json_for_report(truncated_evaluation_results)

        report_prompt = f"""
        基于以下评审结果，生成一份专业的投标评审报告：

        {compressed_json}

        报告应包含：
        1. 总体评价摘要
        2. 分项详细分析
        3. 风险提示
        4. 推荐意见
        5. 谈判要点建议

        要求：专业、客观、具有可操作性。
        """

        # 如果提示词过长，进行进一步压缩
        if len(report_prompt) > 8000:  # 8K字符限制
            print(f'  报告提示词过长 ({len(report_prompt)} 字符)，正在进行压缩...')
            report_prompt = self._compress_prompt(report_prompt)

        messages = [
            {'role': 'system', 'content': '你是专业的招标评审报告撰写专家。'},
            {'role': 'user', 'content': report_prompt},
        ]

        print('正在调用Qwen大模型生成综合报告...')
        print(f'  发送消息数量: {len(messages)}')
        print(f'  系统消息长度: {len(messages[0]["content"])} 字符')
        print(f'  用户消息长度: {len(messages[1]["content"])} 字符')
        final_report = self.ollama.chat_completion(messages)
        print('综合报告生成完成')

        return {
            'summary': final_report,
            'detailed_evaluation': evaluation_results,
            'recommendation': self.generate_recommendation(evaluation_results),
        }

    # 辅助方法
    def chunk_text(self, text: str, chunk_size: int = 300) -> List[str]:
        """文本分块"""
        # 如果文本太长，先按段落分割
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # 如果段落本身就不超过chunk_size，直接添加
            if len(paragraph) <= chunk_size:
                chunks.append(paragraph)
            else:
                # 如果段落太长，再按句子分割
                sentences = re.split(r'[。！？]', paragraph)
                current_chunk = ''

                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    if len(current_chunk) + len(sentence) <= chunk_size:
                        current_chunk += sentence + '。'
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        # 如果单个句子就超过chunk_size，强制截断
                        if len(sentence) > chunk_size:
                            chunks.append(sentence[:chunk_size])
                            current_chunk = sentence[chunk_size:] + '。'
                        else:
                            current_chunk = sentence + '。'

                if current_chunk:
                    chunks.append(current_chunk)

        # 限制最大块数以避免处理时间过长
        if len(chunks) > 100:
            print(f'  文本块数量过多 ({len(chunks)})，限制为100块')
            chunks = chunks[:100]

        return chunks

    def extract_scoring_rules(self, text: str) -> List[Dict]:
        """专门提取评分规则的方法"""
        scoring_rules = []

        # 查找评分规则相关的段落
        scoring_patterns = [
            r'(?:评分标准|评审标准|评标细则)[：:](.*?)(?=\n\n|\n\d+\.|\Z)',
            r'(?:技术|商务)评分标准[：:](.*?)(?=\n\n|\n\d+\.|\Z)',
            r'(\d+分)(.*?)(?=\n\n|\n\d+\.|\Z)',
            r'(?:满分|分值).*?(?:标准|要求|说明)[：:](.*?)(?=\n\n|\n\d+\.|\Z)',
        ]

        for pattern in scoring_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                rule_content = match.group(1).strip()
                if len(rule_content) > 10:  # 过滤掉太短的内容
                    # 进一步处理规则内容，提取关键信息
                    rule_info = self._parse_scoring_rule(rule_content)
                    scoring_rules.append(rule_info)

        return scoring_rules

    def _parse_scoring_rule(self, rule_content: str) -> Dict:
        """解析单个评分规则"""
        # 提取满分值
        max_score_match = re.search(
            r'(?:满分|分值)[：:]?(\d+(?:\.\d+)?)分', rule_content
        )
        max_score = float(max_score_match.group(1)) if max_score_match else None

        # 提取评分标准描述
        description = re.sub(r'满分\d+分', '', rule_content).strip()

        return {
            'content': rule_content,
            'max_score': max_score,
            'description': description,
            'type': self._classify_rule_type(rule_content),
        }

    def _classify_rule_type(self, rule_content: str) -> str:
        """分类评分规则类型"""
        if any(keyword in rule_content for keyword in ['价格', '报价', '基准价']):
            return 'price'
        elif any(keyword in rule_content for keyword in ['技术', '性能', '参数']):
            return 'technical'
        elif any(keyword in rule_content for keyword in ['商务', '服务', '交付']):
            return 'commercial'
        else:
            return 'other'

    def extract_structured_evaluation_info(self, text: str) -> Dict:
        """提取结构化的评标信息"""
        evaluation_info = {
            'total_score': None,
            'evaluation_components': [],
            'scoring_rules': [],
        }

        # 提取总分
        total_score_match = re.search(r'评标总分[：:]?(\d+(?:\.\d+)?)分', text)
        if total_score_match:
            evaluation_info['total_score'] = float(total_score_match.group(1))

        # 提取评标组成部分
        component_patterns = [
            r'(?:技术|商务|价格|综合)标[：:]?(\d+(?:\.\d+)?)分',
            r'(?:技术|商务|价格|综合)部分[：:]?(\d+(?:\.\d+)?)分',
        ]

        for pattern in component_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                component_name = re.sub(r'[：:]?\d+分', '', match.group(0))
                component_score = float(match.group(1))
                evaluation_info['evaluation_components'].append(
                    {'name': component_name, 'score': component_score}
                )

        # 提取具体的评分规则
        rule_patterns = [
            r'(\d+)\s*[\)、]\s*(.*?)(?:\n\d+[\)、]|\Z)',
            r'(?:技术|商务|价格)标.*?(\d+)分[：:](.*?)(?:\n\d+[\)、]|\Z)',
        ]

        for pattern in rule_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                if len(match.groups()) >= 2:
                    score = match.group(1)
                    description = match.group(2).strip()
                    evaluation_info['scoring_rules'].append(
                        {'score': score, 'description': description}
                    )

        return evaluation_info

    def find_relevant_chunks(
        self,
        chunks: List[str],
        chunk_embeddings: List,
        clause_embeddings: List,
        clause_types: List[str],
    ) -> str:
        """找到相关度高的文本块"""
        relevant_content = []

        for i, clause_embedding in enumerate(clause_embeddings):
            if not clause_embedding:
                continue

            best_similarity = 0
            best_chunk = ''

            for j, chunk_embedding in enumerate(chunk_embeddings):
                if chunk_embedding:
                    similarity = self.cosine_similarity(
                        clause_embedding, chunk_embedding
                    )
                    # 对于评标相关内容，使用更低的阈值
                    threshold = (
                        0.4
                        if any(
                            keyword in clause_types[i]
                            for keyword in ['评分', '评审', '评标', '打分', '计分']
                        )
                        else 0.6
                    )
                    if similarity > best_similarity and similarity > threshold:
                        best_similarity = similarity
                        best_chunk = chunks[j]

            if best_chunk:
                relevant_content.append(f'【{clause_types[i]}】{best_chunk}')

        return '\n'.join(relevant_content)

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        # 计算点积
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # 计算向量的模
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        # 避免除零错误
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        # 计算余弦相似度
        return dot_product / (magnitude1 * magnitude2)

    def parse_llm_evaluation(self, response: str) -> Dict:
        """解析大模型的评价结果"""
        try:
            # 尝试提取JSON格式内容
            if '```json' in response:
                json_str = response.split('```json')[1].split('```')[0]
                return json.loads(json_str)
            else:
                # 如果非标准JSON，返回原始内容
                return {'raw_evaluation': response}
        except:
            return {'raw_evaluation': response}

    def generate_recommendation(self, evaluation: Dict) -> str:
        """生成推荐意见"""
        # 基于评价结果生成推荐
        if (
            evaluation.get('technical_score', 0) >= 8
            and evaluation.get('commercial_score', 0) >= 7
        ):
            return '推荐中标，技术方案优秀，商务条件合理'
        elif evaluation.get('technical_score', 0) >= 6:
            return '建议进一步谈判，技术方案基本满足要求'
        else:
            return '不建议中标，存在重大技术或商务风险'

    def generate_scoring_table(self, evaluation_results: Dict) -> List[Dict]:
        """生成打分表，包含打分项目、满分值和实际得分"""
        scoring_table = []

        # 从评价结果中提取评分信息
        # 这里假设评价结果包含各个维度的评分
        if 'detailed_evaluation' in evaluation_results:
            detailed = evaluation_results['detailed_evaluation']

            # 检查是否有评审结果字段
            if '评审结果' in detailed:
                review_results = detailed['评审结果']

                # 添加技术部分评分
                if '技术部分匹配度' in review_results:
                    scoring_table.append(
                        {
                            'item': '技术部分',
                            'max_score': 32,  # 根据您的要求设置
                            'actual_score': review_results['技术部分匹配度'],
                        }
                    )

                # 添加商务部分评分
                if '商务部分匹配度' in review_results:
                    scoring_table.append(
                        {
                            'item': '商务部分',
                            'max_score': 18,  # 根据您的要求设置
                            'actual_score': review_results['商务部分匹配度'],
                        }
                    )

                # 添加服务部分评分
                if '服务部分匹配度' in review_results:
                    scoring_table.append(
                        {
                            'item': '服务部分',
                            'max_score': 10,  # 根据您的要求设置
                            'actual_score': review_results['服务部分匹配度'],
                        }
                    )

                # 添加价格部分评分
                if '价格分' in review_results:
                    scoring_table.append(
                        {
                            'item': '价格部分',
                            'max_score': 40,  # 根据您的要求设置
                            'actual_score': review_results['价格分'],
                        }
                    )
            else:
                # 添加技术部分评分
                if 'technical_score' in detailed:
                    scoring_table.append(
                        {
                            'item': '技术部分',
                            'max_score': 32,  # 根据您的要求设置
                            'actual_score': detailed.get('technical_score', 0),
                        }
                    )

                # 添加商务部分评分
                if 'commercial_score' in detailed:
                    scoring_table.append(
                        {
                            'item': '商务部分',
                            'max_score': 18,  # 根据您的要求设置
                            'actual_score': detailed.get('commercial_score', 0),
                        }
                    )

                # 添加服务部分评分
                if 'service_score' in detailed:
                    scoring_table.append(
                        {
                            'item': '服务部分',
                            'max_score': 10,  # 根据您的要求设置
                            'actual_score': detailed.get('service_score', 0),
                        }
                    )

                # 添加价格部分评分
                if 'price_score' in detailed:
                    scoring_table.append(
                        {
                            'item': '价格部分',
                            'max_score': 40,  # 根据您的要求设置
                            'actual_score': detailed.get('price_score', 0),
                        }
                    )

        # 如果没有详细的评分信息，尝试从raw_evaluation中解析
        elif 'raw_evaluation' in evaluation_results:
            raw_eval = evaluation_results['raw_evaluation']
            # 从原始评价中提取评分信息
            parsed_scores = self._parse_scores_from_text(raw_eval)
            scoring_table.extend(parsed_scores)

        # 如果没有任何评分信息，添加默认项
        else:
            scoring_table.extend(
                [
                    {'item': '技术部分', 'max_score': 32, 'actual_score': 0},
                    {'item': '商务部分', 'max_score': 18, 'actual_score': 0},
                    {'item': '服务部分', 'max_score': 10, 'actual_score': 0},
                    {'item': '价格部分', 'max_score': 40, 'actual_score': 0},
                ]
            )

        return scoring_table

    def _parse_scores_from_text(self, text: str) -> List[Dict]:
        """从文本中解析评分信息"""
        scoring_table = []

        # 使用正则表达式提取评分信息
        # 匹配类似 "技术部分：25分" 或 "技术部分匹配度（0-32分）：25分" 的模式
        patterns = [
            r'(?:技术|商务|服务|价格)[^：:]*[：:](?:\d+分)?[^\d]*(\d+(?:\.\d+)?)分',
            r'(?:技术|商务|服务|价格)[^：:]*\([^)]*?(\d+(?:\.\d+)?)分',
            r'(\d+(?:\.\d+)?)分[^(]*?(?:技术|商务|服务|价格)',
        ]

        scores_found = {
            '技术部分': 0.0,
            '商务部分': 0.0,
            '服务部分': 0.0,
            '价格部分': 0.0,
        }

        max_scores = {'技术部分': 32, '商务部分': 18, '服务部分': 10, '价格部分': 40}

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # 提取匹配到的评分信息
                try:
                    score = int(float(match.group(1)))
                    # 确定评分项目
                    match_text = match.group(0)
                    if '技术' in match_text:
                        scores_found['技术部分'] = max(scores_found['技术部分'], score)
                    elif '商务' in match_text:
                        scores_found['商务部分'] = max(scores_found['商务部分'], score)
                    elif '服务' in match_text:
                        scores_found['服务部分'] = max(scores_found['服务部分'], score)
                    elif '价格' in match_text:
                        scores_found['价格部分'] = max(scores_found['价格部分'], score)
                except (ValueError, IndexError):
                    # 如果转换失败，跳过这个匹配
                    continue

        # 添加找到的评分或默认值
        for item, max_score in max_scores.items():
            scoring_table.append(
                {
                    'item': item,
                    'max_score': max_score,
                    'actual_score': int(scores_found.get(item, 0)),
                }
            )

        return scoring_table

    def format_scoring_table(self, scoring_table: List[Dict]) -> str:
        """格式化打分表为字符串"""
        table_str = '=' * 50 + '\n'
        table_str += '📊 打分表\n'
        table_str += '=' * 50 + '\n'
        table_str += f'{"打分项目":<15} {"满分值":<10} {"实际得分":<10}\n'
        table_str += '-' * 35 + '\n'

        total_max_score = 0
        total_actual_score = 0

        for item in scoring_table:
            table_str += f'{item["item"]:<15} {item["max_score"]:<10} {item["actual_score"]:<10}\n'
            total_max_score += item['max_score']
            total_actual_score += item['actual_score']

        table_str += '-' * 35 + '\n'
        table_str += f'{"总计":<15} {total_max_score:<10} {total_actual_score:<10}\n'
        table_str += '=' * 50 + '\n'

        return table_str


# 使用示例
def main():
    print('🔍 检查Ollama服务可用性...')
    evaluator = IntelligentBidEvaluator()

    # 检查Ollama服务是否可用
    if not evaluator.ollama.check_service_availability():
        print('❌ Ollama服务不可用，请确保服务已启动并正确配置')
        print('请运行以下命令启动Ollama服务:')
        print('  ollama serve')
        print('\n并确保已拉取所需模型:')
        print(f'  ollama pull {evaluator.ollama.embedding_model}')
        print(
            f'  ollama pull {evaluator.ollama.llm_model}  # 注意：该模型较大，请确保有足够的磁盘空间'
        )
        return

    # 示例文档内容
    print('📄 读取招标文件...')
    try:
        import os

        tender_file_path = os.path.join(
            '..', 'output', '昆明苏净工贸有限公司集装箱项目投标文件.md'
        )
        with open(tender_file_path, 'r', encoding='utf-8') as f:
            tender_text = f.read()
        print(f'  招标文件大小: {len(tender_text)} 字符')
    except FileNotFoundError:
        print(r'未找到投标文件: output\昆明苏净工贸有限公司集装箱项目投标文件.md')
        tender_text = ''
    except Exception as e:
        print(f'读取招标文件时出错: {e}')
        tender_text = ''

    print('📄 读取投标文件...')
    try:
        import fitz  # PyMuPDF
        import os

        bid_file_path = os.path.join('..', 'uploads', '招标文件正文.pdf')
        # 首先尝试使用PyMuPDF读取PDF文件
        try:
            doc = fitz.open(bid_file_path)
            bid_text = ''
            for page_num in range(doc.page_count):
                page = doc[page_num]
                # 使用类型注释避免静态分析错误
                text = page.get_text()  # type: ignore
                bid_text += text
            doc.close()
            print(f'  投标文件大小: {len(bid_text)} 字符')
        except Exception as pdf_error:
            # 如果PDF读取失败，尝试直接读取文本文件
            print(f'  PDF读取失败: {pdf_error}，尝试直接读取文本内容')
            with open(bid_file_path, 'r', encoding='utf-8') as f:
                bid_text = f.read()
            print(f'  投标文件大小: {len(bid_text)} 字符')
    except Exception as e:
        print(f'读取投标文件时出错: {e}')
        bid_text = '投标文件内容占位符'

    # 检查文件是否为空
    if not tender_text and not bid_text:
        print('❌ 招标文件和投标文件都为空，无法进行分析')
        return

    if not tender_text:
        print('⚠️  招标文件为空，无法进行分析')
        return

    if not bid_text:
        print('⚠️  投标文件为空，无法进行分析')
        return

    try:
        print('\n🚀 开始智能标书评价...')
        results = evaluator.evaluate_bid_documents(tender_text, bid_text)

        print('\n' + '=' * 60)
        print('📊 智能标书评审报告')
        print('=' * 60)

        print(f'总体评价：\n{results["summary"]}')
        print(f'\n推荐意见：{results["recommendation"]}')

        # 生成并显示打分表
        print('\n' + '=' * 50)
        print('📊 打分表')
        print('=' * 50)

        scoring_table = evaluator.generate_scoring_table(results)
        scoring_table_str = evaluator.format_scoring_table(scoring_table)
        print(scoring_table_str)

        # 保存详细结果
        results_with_scoring = results.copy()
        results_with_scoring['scoring_table'] = scoring_table

        with open('bid_evaluation_report.json', 'w', encoding='utf-8') as f:
            json.dump(results_with_scoring, f, ensure_ascii=False, indent=2)

        # 保存打分表到单独文件
        with open('scoring_table.txt', 'w', encoding='utf-8') as f:
            f.write(scoring_table_str)

        print('\n✅ 详细评价已保存到 bid_evaluation_report.json')
        print('\n✅ 打分表已保存到 scoring_table.txt')

    except Exception as e:
        print(f'❌ 评价过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    main()
