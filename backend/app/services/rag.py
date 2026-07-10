"""
RAG 检索服务（增强版）

改进点：
1. 混合检索 — 向量语义 + BM25 关键词，两路召回合并去重
2. 查询扩展 — 提取关键词、同义改写，提高召回率
3. 元数据返回 — 携带来源文件、分块索引，支持溯源
4. 结果缓存 — TTL 缓存，避免重复检索
5. Skill 感知 — 接受可选上下文，优化过滤条件
"""
import re
import time
import hashlib
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from .indexer import get_collection, clean_text

logger = logging.getLogger(__name__)


# ==================== 数据结构 ====================

@dataclass
class RetrievalResult:
    """单条检索结果"""
    content: str
    score: float                          # 综合得分 (0~1)
    source_file: str = ""                 # 来源文件名
    chunk_index: int = -1                 # 分块索引
    doc_id: int = -1                      # 文档 ID
    retrieval_method: str = "vector"      # 命中方式: "vector" | "bm25" | "both"

    def to_context_text(self) -> str:
        """转为注入上下文的文本"""
        header = f"[来源: {self.source_file}]" if self.source_file else ""
        return f"{header}\n{self.content}" if header else self.content


# ==================== 缓存 ====================

class RetrievalCache:
    """检索结果缓存（TTL 机制）"""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 200):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._store: Dict[str, Tuple[float, List[RetrievalResult]]] = {}

    def _key(self, query: str, top_k: int, context: str = "") -> str:
        raw = f"{query}|{top_k}|{context}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def get(self, query: str, top_k: int, context: str = "") -> Optional[List[RetrievalResult]]:
        key = self._key(query, top_k, context)
        entry = self._store.get(key)
        if entry:
            ts, results = entry
            if time.time() - ts < self.ttl:
                logger.info(f"检索缓存命中: {len(results)} 条结果")
                return results
            del self._store[key]
        return None

    def set(self, query: str, top_k: int, results: List[RetrievalResult], context: str = ""):
        key = self._key(query, top_k, context)
        if len(self._store) >= self.max_size:
            # 淘汰最旧的条目
            oldest = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest]
        self._store[key] = (time.time(), results)


# 全局缓存实例
_retrieval_cache = RetrievalCache()


# ==================== BM25 关键词检索 ====================

class BM25Retriever:
    """
    轻量 BM25 检索器。

    在内存中维护文档索引，支持增量更新。
    参考 BM25 公式：score = IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_len))
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: List[List[str]] = []       # 分词后的文档
        self._raw_docs: List[str] = []          # 原始文档文本
        self._metadatas: List[Dict] = []        # 元数据
        self._doc_freq: Dict[str, int] = {}     # 词 → 包含该词的文档数
        self._avg_len: float = 0.0
        self._dirty: bool = True

    def index_documents(self, documents: List[str], metadatas: List[Dict] = None):
        """重建索引"""
        self._docs = [_tokenize(doc) for doc in documents]
        self._raw_docs = documents
        self._metadatas = metadatas or [{}] * len(documents)
        self._doc_freq = {}
        for tokens in self._docs:
            for token in set(tokens):
                self._doc_freq[token] = self._doc_freq.get(token, 0) + 1
        total_len = sum(len(t) for t in self._docs)
        self._avg_len = total_len / max(1, len(self._docs))
        self._dirty = False

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """返回 [(doc_index, score), ...] 按得分降序"""
        if not self._docs:
            return []

        query_tokens = _tokenize(query)
        N = len(self._docs)
        scores = []

        for i, doc_tokens in enumerate(self._docs):
            score = 0.0
            doc_len = len(doc_tokens)
            tf = {}
            for t in doc_tokens:
                tf[t] = tf.get(t, 0) + 1

            for token in set(query_tokens):
                if token not in self._doc_freq:
                    continue
                df = self._doc_freq[token]
                idf = max(0, (N - df + 0.5) / (df + 0.5))
                term_tf = tf.get(token, 0)
                numerator = term_tf * (self.k1 + 1)
                denominator = term_tf + self.k1 * (1 - self.b + self.b * doc_len / max(1, self._avg_len))
                score += idf * numerator / max(0.01, denominator)

            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_document(self, index: int) -> Tuple[str, Dict]:
        """获取文档内容及元数据"""
        if 0 <= index < len(self._raw_docs):
            meta = self._metadatas[index] if index < len(self._metadatas) else {}
            return self._raw_docs[index], meta
        return "", {}

    def __len__(self):
        return len(self._docs)


def _tokenize(text: str) -> List[str]:
    """
    中文分词（简易版）。
    使用 jieba 分词（如果可用），否则使用字符级 bigram。
    """
    try:
        import jieba
        return [t for t in jieba.cut(text) if t.strip() and len(t.strip()) >= 1]
    except ImportError:
        pass

    # 回退：字符级 unigram + bigram
    text = re.sub(r'[^一-鿿a-zA-Z0-9]', ' ', text)
    tokens = []
    # 英文单词
    tokens.extend(re.findall(r'[a-zA-Z]+', text.lower()))
    # 数字
    tokens.extend(re.findall(r'\d+', text))
    # 中文 unigram
    chars = re.findall(r'[一-鿿]', text)
    tokens.extend(chars)
    # 中文 bigram
    for i in range(len(chars) - 1):
        tokens.append(chars[i] + chars[i + 1])
    return [t for t in tokens if len(t) >= 1]


# ==================== 查询扩展 ====================

def _expand_query(question: str) -> List[str]:
    """
    查询扩展：生成多个变体查询以提升召回率。

    策略：
    1. 提取核心关键词（去停用词）
    2. 生成关键词组合查询
    3. 限制扩展数量避免过度检索
    """
    queries = [question]  # 原始查询始终包含

    # 提取核心实体词（连续中文字符 ≥2）
    entities = re.findall(r'[一-鿿]{2,}', question)
    if entities:
        # 选最重要的 3 个实体词
        key_entities = entities[:3]
        if len(key_entities) >= 1:
            queries.append(" ".join(key_entities))

    # 去除疑问词，保留实质内容
    for qw in ["请问", "你好", "帮我", "我想", "可以", "能不能", "有没有"]:
        clean = question.replace(qw, "").strip()
        if clean != question and clean not in queries:
            queries.append(clean)
            break

    # 去重并限制数量
    seen = set()
    result = []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            result.append(q)
    return result[:3]  # 最多 3 个变体


# ==================== 主检索函数 ====================

# BM25 全局实例（惰性初始化）
_bm25: Optional[BM25Retriever] = None
_bm25_doc_count: int = 0


def _ensure_bm25():
    """确保 BM25 索引已构建（文档变化时自动重建）"""
    global _bm25, _bm25_doc_count
    col = get_collection()
    current_count = col.count()

    if _bm25 is None or current_count != _bm25_doc_count:
        logger.info(f"构建 BM25 索引，文档数: {current_count}")
        try:
            all_data = col.get(include=["documents", "metadatas"])
            docs = all_data.get("documents", []) or []
            metas = all_data.get("metadatas", []) or []
            _bm25 = BM25Retriever()
            _bm25.index_documents(docs, metas)
            _bm25_doc_count = current_count
            logger.info(f"BM25 索引构建完成，词汇量: {len(_bm25._doc_freq)}")
        except Exception as e:
            logger.warning(f"BM25 索引构建失败（非致命）: {e}")
            _bm25 = None


def retrieve_context(
    question: str,
    top_k: int = 5,
    use_cache: bool = True,
    context: str = "",           # 新增：Skill 上下文（用于缓存键）
    prefer_area: str = "",       # 新增：优先景区（如 "灵山胜境"）
    return_rich: bool = False,   # 新增：返回富结果（含元数据）
) -> List[str]:
    """
    混合检索知识库文档。

    Args:
        question: 用户问题
        top_k: 返回结果数
        use_cache: 是否使用缓存
        context: 可选上下文（如 Skill 名称）
        prefer_area: 优先景区过滤
        return_rich: 是否返回带来源标注的结果

    Returns:
        检索到的文档片段列表（return_rich=True 时带 [来源: xxx] 前缀）
    """
    # ---- 缓存检查 ----
    if use_cache:
        cached = _retrieval_cache.get(question, top_k, context)
        if cached is not None:
            if return_rich:
                return [r.to_context_text() for r in cached]
            return [r.content for r in cached]

    collection = get_collection()
    if collection.count() == 0:
        return []

    start_time = time.time()

    # ---- 1. 查询扩展 ----
    queries = _expand_query(question)
    logger.info(f"检索查询扩展: {len(queries)} 个变体")

    # ---- 2. 向量检索（多查询合并）----
    vector_results: Dict[int, RetrievalResult] = {}  # doc_index → result

    for query in queries:
        try:
            results = collection.query(
                query_texts=[query],
                n_results=top_k * 2,  # 多取一些供合并
                where={"type": "document"},
                include=["documents", "metadatas", "distances"],
            )
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    content = clean_text(results["documents"][0][i])
                    distance = results["distances"][0][i] if results.get("distances") else [0.5]
                    score = 1.0 - min(distance[i] if isinstance(distance, list) else distance, 1.0)
                    meta = results["metadatas"][0][i] if results.get("metadatas") else {}

                    # 景区过滤
                    if prefer_area and meta.get("scenic_area", "") != prefer_area:
                        score *= 0.5  # 降权但不排除

                    if meta.get("type") != "document":
                        continue

                    # 用内容哈希作为去重键
                    doc_key = hash(content)
                    if doc_key not in vector_results or vector_results[doc_key].score < score:
                        vector_results[doc_key] = RetrievalResult(
                            content=content,
                            score=score,
                            source_file=meta.get("filename", meta.get("source_file", "")),
                            chunk_index=meta.get("chunk_idx", meta.get("chunk_index", -1)),
                            doc_id=meta.get("doc_id", -1),
                            retrieval_method="vector",
                        )
        except Exception as e:
            logger.warning(f"向量检索失败 (query={query[:30]}): {e}")

    # ---- 3. BM25 检索 ----
    _ensure_bm25()
    bm25_results: Dict[int, RetrievalResult] = {}

    if _bm25 and len(_bm25) > 0:
        for query in queries[:2]:  # BM25 只用前 2 个查询变体
            hits = _bm25.search(query, top_k=top_k * 2)
            for doc_idx, bm25_score in hits:
                content, meta = _bm25.get_document(doc_idx)
                if not content or meta.get("type") != "document":
                    continue
                content = clean_text(content)

                # 归一化 BM25 得分
                normalized_score = min(bm25_score / max(1.0, bm25_score + 5.0), 1.0)

                if prefer_area and meta.get("scenic_area", "") != prefer_area:
                    normalized_score *= 0.5

                doc_key = hash(content)
                if doc_key in bm25_results:
                    # 同时被向量和 BM25 命中 → 提升得分
                    existing = bm25_results[doc_key]
                    existing.score = max(existing.score, normalized_score)
                    existing.retrieval_method = "both"
                else:
                    bm25_results[doc_key] = RetrievalResult(
                        content=content,
                        score=normalized_score,
                        source_file=meta.get("filename", meta.get("source_file", "")),
                        chunk_index=meta.get("chunk_idx", meta.get("chunk_index", -1)),
                        doc_id=meta.get("doc_id", -1),
                        retrieval_method="bm25",
                    )

    # ---- 4. 合并去重排序 ----
    merged: Dict[int, RetrievalResult] = {}

    # 向量结果优先
    for key, result in vector_results.items():
        merged[key] = result

    # BM25 结果合并（已在 BM25 阶段处理了 "both" 标记）
    for key, result in bm25_results.items():
        if key in merged:
            merged[key].score = max(merged[key].score, result.score)
            merged[key].retrieval_method = "both"
        else:
            merged[key] = result

    # 按得分排序
    ranked = sorted(merged.values(), key=lambda r: r.score, reverse=True)
    final = ranked[:top_k]

    elapsed = time.time() - start_time
    vec_count = len(vector_results)
    bm_count = len(bm25_results)
    both_count = sum(1 for r in final if r.retrieval_method == "both")
    logger.info(
        f"混合检索完成 ({elapsed:.3f}s): "
        f"向量={vec_count}, BM25={bm_count}, "
        f"合并后={len(merged)}, 最终={len(final)}, "
        f"双命中共识={both_count}"
    )

    # ---- 5. 缓存 ----
    if use_cache:
        _retrieval_cache.set(question, top_k, final, context)

    # ---- 6. 返回 ----
    if return_rich:
        return [r.to_context_text() for r in final]
    return [r.content for r in final]


def retrieve_with_metadata(
    question: str,
    top_k: int = 5,
    context: str = "",
    prefer_area: str = "",
) -> List[RetrievalResult]:
    """检索并返回完整元数据（供 Skill 系统使用）"""
    # 绕过缓存，直接检索
    _retrieval_cache.get.cache_clear() if hasattr(_retrieval_cache.get, 'cache_clear') else None
    # 强制不走缓存
    collection = get_collection()
    if collection.count() == 0:
        return []

    queries = _expand_query(question)
    vector_results: Dict[int, RetrievalResult] = {}

    for query in queries:
        try:
            results = collection.query(
                query_texts=[query],
                n_results=top_k * 2,
                where={"type": "document"},
                include=["documents", "metadatas", "distances"],
            )
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    content = clean_text(results["documents"][0][i])
                    distances = results.get("distances")
                    dist_val = distances[0][i] if distances and distances[0] else 0.5
                    score = 1.0 - min(float(dist_val), 1.0)
                    meta = results["metadatas"][0][i] if results.get("metadatas") else {}

                    if meta.get("type") != "document":
                        continue

                    doc_key = hash(content)
                    if doc_key not in vector_results or vector_results[doc_key].score < score:
                        vector_results[doc_key] = RetrievalResult(
                            content=content,
                            score=score,
                            source_file=meta.get("filename", ""),
                            chunk_index=meta.get("chunk_idx", -1),
                            doc_id=meta.get("doc_id", -1),
                            retrieval_method="vector",
                        )
        except Exception as e:
            logger.warning(f"检索失败: {e}")

    ranked = sorted(vector_results.values(), key=lambda r: r.score, reverse=True)
    return ranked[:top_k]


def clear_retrieval_cache():
    """清除检索缓存（知识库更新后调用）"""
    global _retrieval_cache, _bm25, _bm25_doc_count
    _retrieval_cache = RetrievalCache()
    _bm25 = None
    _bm25_doc_count = 0
    logger.info("检索缓存已清除")
