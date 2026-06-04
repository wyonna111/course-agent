"""问句关键词提取、检索 query、资料覆盖度评估（通用，无题型注册表）"""



import re



from src.question_types import detect_answer_mode, is_concept_application_question, question_mode



TECH_PATTERNS = [

    r"IEEE\s*754",

    r"单精度",

    r"双精度",

    r"浮点",

    r"规格化",

    r"阶码",

    r"尾数",

    r"冯诺依曼",

    r"UART",

    r"USART",

    r"SPI",

    r"I2C",

    r"GPIO",

    r"STM32",

    r"补码",

    r"原码",

    r"反码",

    r"无符号",

    r"总线",

    r"中断",

    r"定时器",

    r"PWM",

    r"ADC",

    r"DAC",

    r"字节编址",

    r"按字节",

    r"存储器",

    r"指针",

    r"字长",

    r"寻址",

    r"机器数",

    r"奇偶",

    r"校验",

    r"移码",

    r"符号位",

    r"数值位",

    r"\bDB\b",

    r"\bDW\b",

    r"\bDD\b",

    r"DUP",

    r"8086",

    r"汇编",

]



STOPWORDS = {

    "如何",

    "什么",

    "为什么",

    "怎样",

    "请将",

    "转换",

    "为",

    "的",

    "和",

    "把",

    "根据",

    "进行",

    "题目",

    "数据",

    "形式",

    "标准",

    "一下",

    "请问",

    "是否",

    "需要",

    "也就是",

    "一个",

    "这种",

    "具体",

    "来说",

    "当",

    "从",

    "读取",

    "下列",

    "语句",

    "分别",

    "并",

    "画出",

}





def extract_key_terms(text: str) -> list[str]:

    terms: set[str] = set()

    for pat in TECH_PATTERNS:

        for m in re.finditer(pat, text, re.I):

            terms.add(re.sub(r"\s+", "", m.group()))

    for m in re.finditer(r"[A-Za-z0-9]{2,}", text):

        terms.add(m.group())

    for w in re.findall(r"[\u4e00-\u9fff]{2,8}", text):

        if w not in STOPWORDS:

            terms.add(w)

    return sorted(terms, key=len, reverse=True)





def expand_retrieval_query(question: str) -> str:

    """去掉具体数字，保留概念词，便于召回规则/例题页。"""

    core = re.sub(r"-?\d+\.?\d*", " ", question)

    core = re.sub(r"'[^']*'", " ", core)

    core = re.sub(r"\s+", " ", core).strip()

    terms = extract_key_terms(question)

    extra = " ".join(terms[:14])

    return f"{core} {extra}".strip() or question





def _dedupe_queries(queries: list[str]) -> list[str]:

    seen: set[str] = set()

    out: list[str] = []

    for q in queries:

        q = q.strip()

        if q and q not in seen:

            seen.add(q)

            out.append(q)

    return out





def build_retrieval_queries(question: str) -> list[str]:

    """多路检索：原问句、去数字概念扩展、关键词 — 不依赖题型注册表。"""

    return _dedupe_queries(

        [

            question,

            expand_retrieval_query(question),

            " ".join(extract_key_terms(question)[:12]),

        ]

    )





def is_encoding_question(question: str) -> bool:

    q = question

    return any(

        k in q for k in ("原码", "补码", "反码", "无符号", "机器数", "移码", "奇偶", "校验")

    ) or (bool(re.search(r"[0-9A-Fa-f]+H", q)) and "十进制" in q)





def term_overlap_ratio(terms: list[str], corpus: str) -> float:

    if not terms:

        return 0.0

    corpus_l = corpus.lower()

    hits = sum(1 for t in terms if t.lower() in corpus_l or t in corpus)

    return hits / len(terms)





def assess_topic_coverage(question: str, corpus: str) -> dict:

    """通用概念覆盖：关键词重合 + 去数字后的问句子串命中。"""

    terms = extract_key_terms(question)

    term_hits = sum(1 for t in terms if t.lower() in corpus.lower() or t in corpus)

    ratio = term_overlap_ratio(terms, corpus)



    phrase_hits: list[str] = []

    concept_q = expand_retrieval_query(question)

    for w in re.findall(r"[\u4e00-\u9fff]{3,8}", concept_q):

        if w in STOPWORDS or len(w) < 3:

            continue

        if w in corpus and w not in phrase_hits:

            phrase_hits.append(w)



    phrase_score = min(len(phrase_hits) * 0.12, 0.6)

    coverage = min(ratio * 0.55 + phrase_score, 1.0)



    strong = (

        term_hits >= 4

        or coverage >= 0.40

        or (term_hits >= 2 and len(phrase_hits) >= 2)

        or (term_hits >= 3 and coverage >= 0.25)

    )



    return {

        "strong": strong,

        "term_ratio": round(ratio, 3),

        "term_hits": term_hits,

        "phrase_hits": phrase_hits[:8],

        "coverage": round(coverage, 3),

        "terms": terms[:10],

    }





__all__ = [

    "assess_topic_coverage",

    "build_retrieval_queries",

    "extract_key_terms",

    "is_concept_application_question",

    "is_encoding_question",

    "question_mode",

    "detect_answer_mode",

]


