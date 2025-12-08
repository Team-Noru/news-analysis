import re
from typing import List, Optional

from keybert import KeyBERT
from sentence_transformers import SentenceTransformer


class KoNewsKeywordExtractor:
    """
    KoBERT 한국어 임베딩 + KeyBERT 기반 뉴스 키워드 추출기
    - 제목 가중치
    - 조사 제거
    - 불용어 필터링
    - fallback 명사 추출
    """

    def __init__(
        self,
        model_name: str = "jhgan/ko-sroberta-multitask",  
        top_n: int = 5,
    ):
        self.top_n = top_n

        # KoBERT 계열 sentence-transformer 로딩
        st_model = SentenceTransformer(model_name)
        self.keybert = KeyBERT(model=st_model)


        self.stopwords = {
            "기자", "이번", "다음", "지난", "당시", "현재", "오늘", "내일", "어제",
            "그러나", "하지만", "또한", "그리고", "때문", "통해", "위해", "따라",
            "이미지", "사진", "제공", "뉴스", "기사", "연합뉴스", "속보",
            "있는", "없는", "되는", "하는", "같은", "많은", "모든",
            "이상", "이하", "관련", "대한", "통한", "의한"
        }


    def _remove_josa_tail(self, word: str) -> str:
        """
        명사 꼬리에 붙은 조사만 슬쩍 제거하는 용도.
        '삼성전자와' -> '삼성전자'
        '정부의'     -> '정부'
        너무 공격적으로 자르지 않도록 한 번만 replace.
        """
        # 단어 전체가 2글자 이하이면 과도하게 자르지 않음
        if len(word) <= 2:
            return word

        josa_patterns = [
            r'(에서|에게|한테서|으로부터|로부터)$',  # 복합조사
            r'(으로|로|와|과|랑|이랑)$',
            r'(을|를|이|가|은|는|에|에서|에게|한테|께)$',
            r'(의|도|만|까지|부터|마저|조차|밖에|뿐|라도|라서)$',
        ]

        cleaned = word
        for pattern in josa_patterns:
            cleaned = re.sub(pattern, "", cleaned)
        return cleaned

    def _build_input_text(self, title: str, content: Optional[str]) -> str:
        """
        제목에 가중치를 주기 위해 3번 반복 + 본문 앞부분만 이어 붙임
        """
        title = title.strip()
        pieces = [title, title, title]  # 제목 3배 가중치

        if content:
            content = content.strip()
            if len(content) > 20:
                pieces.append(content[:1000])  # 너무 길면 앞부분만 사용

        return " ".join(pieces)

    def _extract_simple_nouns(self, text: str) -> List[str]:
        """
        형태소 분석기 없이 쓸 수 있는, 정규식 기반 명사 후보 추출
        - 2~8 글자 사이 한글 시퀀스만
        - 조사 꼬리만 살짝 제거
        """
        korean_words = re.findall(r"[가-힣]{2,8}", text)
        candidates = []

        for w in korean_words:
            w_clean = self._remove_josa_tail(w)
            if 2 <= len(w_clean) <= 8:
                candidates.append(w_clean)

        seen = set()
        result = []
        for w in candidates:
            if w not in seen:
                seen.add(w)
                result.append(w)
        return result

    # ----------------------- 키워드 필터링 ----------------------- #

    def _is_valid_keyword(self, keyword: str, seen: set) -> bool:
        """
        길이, stopword, 숫자, 중복 등을 검사해서 유효한 키워드만 통과
        """
        if not keyword:
            return False
        kw = keyword.strip()

        # 길이 제한
        if len(kw) < 2 or len(kw) > 12:
            return False

        # pure 숫자 제외
        if kw.isdigit():
            return False

        # stopword 제외
        if kw in self.stopwords:
            return False

        # 이미 사용한 키워드 제외
        if kw.lower() in seen:
            return False

        return True

    # ----------------------- 메인: 뉴스 한 건에서 추출 ----------------------- #

    def extract_from_article(
        self,
        title: str,
        content: Optional[str] = None,
        top_n: Optional[int] = None,
        with_scores: bool = False,
    ):
        """
        단일 뉴스 기사(제목 + 본문)에서 상위 키워드 리스트 반환
        
        - top_n: 이 호출에서만 사용할 개수 (None이면 self.top_n 사용)
        - with_scores: True면 [(키워드, 점수)] 형태로 반환
        """
        if top_n is None:
            top_n = self.top_n

        text = self._build_input_text(title, content)

        try:
            # 1차: KeyBERT로 후보 뽑기
            raw_keywords = self.keybert.extract_keywords(
                text,
                keyphrase_ngram_range=(1, 1),      # 단어 단위
                stop_words=list(self.stopwords),
                use_mmr=True,                      # 다양성
                diversity=0.3,
                top_n=max(top_n * 2, 10),          # 충분히 많이 뽑고 나중에 필터링
            )

            cleaned = []   # [(kw_clean, score)]
            seen = set()

            for kw, score in raw_keywords:
                kw = kw.strip()
                # 조사 꼬리만 가볍게 정리
                kw_clean = self._remove_josa_tail(kw)

                if self._is_valid_keyword(kw_clean, seen):
                    cleaned.append((kw_clean, score))
                    seen.add(kw_clean.lower())

                if len(cleaned) >= top_n:
                    break

            # 2차: 너무 적으면 fallback 명사 추출로 보완 
            if len(cleaned) < top_n:
                simple_nouns = self._extract_simple_nouns(text)
                for noun in simple_nouns:
                    if noun not in self.stopwords and noun.lower() not in seen:
                        cleaned.append((noun, 0.0))  # fallback은 score 0.0 처리
                        seen.add(noun.lower())
                    if len(cleaned) >= top_n:
                        break

            cleaned = cleaned[:top_n]

            if with_scores:
                return cleaned
            else:
                return [kw for kw, _ in cleaned]

        except Exception as e:
            print(f"키워드 추출 중 오류 발생: {e}")
            # fallback일 때도 with_scores 옵션 맞춰서 반환
            fallback = self._extract_simple_nouns(text)[:top_n]
            if with_scores:
                return [(kw, 0.0) for kw in fallback]
            else:
                return fallback


if __name__ == "__main__":
    extractor = KoNewsKeywordExtractor(top_n=5)

    title = "올해 마지막 연준 금리 결정 카운트다운, 경제학자 85% 0.25%p 인하"
    with open("news2.txt", "r", encoding="utf-8") as file:
        content = file.read()
    
    keywords_with_scores = extractor.extract_from_article(
        title,
        content,
        top_n=5,
        with_scores=True,
    )

    for kw, score in keywords_with_scores:
        print(f"{kw}\t{score:.4f}")


