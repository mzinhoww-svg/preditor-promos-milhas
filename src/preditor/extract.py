from __future__ import annotations

"""Camada determinística de extração (regex + pydantic).

Texto é sempre DADO; instruções eventualmente presentes são descartadas.
"""
import re
import unicodedata
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

PROGRAMS: tuple[str, ...] = ("livelo", "esfera", "latam_pass", "smiles", "azul_fidelidade")
_PROGRAM_LITERALS = Literal["livelo", "esfera", "latam_pass", "smiles", "azul_fidelidade"]
_EVENT_TYPES: tuple[str, ...] = ("transfer_bonus", "purchase_discount", "boosted_accrual")
_TYPE_LITERAL = Literal["transfer_bonus", "purchase_discount", "boosted_accrual"]

_PROGRAM_ALIASES: dict[str, str] = {
    "livelo": "livelo",
    "esfera": "esfera",
    "latam_pass": "latam(?:\\s*pass|_pass|pass)",
    "smiles": "smiles",
    "azul_fidelidade": "azul(?:\\s*fidelidade|_fidelidade)",
}

# regex públicos (spec)
PAR = r"\blivelo\b.{0,120}\bsmiles\b|\bsmiles\b.{0,120}\blivelo\b"
PAR_RE = re.compile(PAR, re.IGNORECASE | re.DOTALL)

BONUS_CTX = r"b[ôo]nus|bonificad[ao]|transfer[êe]ncia"
BONUS_CTX_RE = re.compile(BONUS_CTX, re.IGNORECASE)

BONUS_PCT = r"(?:at[ée]\s+)?(?<!\d)(\d{1,3}(?:,\d+)?)\s?%(?=\s*(?:de\s+)?(?:b[ôo]nus|bonifica|na\s+transfer))|b[ôo]nus\s+de\s+(?:at[ée]\s+)?(\d{1,3}(?:,\d+)?)\s?%"
BONUS_PCT_RE = re.compile(BONUS_PCT, re.IGNORECASE)

DATA_NUM = r"(?<!\d)([0-3]?\d)/([01]?\d)(?:/(20\d{2}|\d{2}))?(?!\d)"
DATA_NUM_RE = re.compile(DATA_NUM, re.IGNORECASE)

MONTHS_PT = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

DATA_EXT = r"(?<!\d)([0-3]?\d)\s+de\s+(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de\s+(20\d{2}))?"
DATA_EXT_RE = re.compile(DATA_EXT, re.IGNORECASE)

SEGMENTO = r"exclusiv[oa]\s+(?:para|do|da|de)|clube(?:\s+(?:livelo|smiles|latam|azul|esfera))?|cart[ãa]o\s+\w+|diamante"
SEGMENTO_RE = re.compile(SEGMENTO, re.IGNORECASE)


def normalize(text: Any) -> str:
    if text is None:
        return ""
    if isinstance(text, (bytes, bytearray)):
        try:
            s = bytes(text).decode("utf-8")
        except UnicodeDecodeError:
            s = str(text)
    else:
        s = str(text)
    s = unicodedata.normalize("NFKC", s)
    # remove zero-width / BOM que podem burlar gatilhos
    for ch in ("\u200b", "\u200c", "\u200d", "\u200e", "\u200f", "\ufeff"):
        s = s.replace(ch, "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --- helpers ----------------------------------------------------------------
_INJECTION_MARKERS = ("ignore", "disregard", "override", "jailbreak", "system:")
_NEGATION_MARKERS = ("não", "nao", "cancelad", "encerrad", "sem bônus", "sem bonus", "não terá", "nao tera")
_HISTORY_MARKERS = ("antes", "anterior", "antigamente")


def _promo_signal(sentence: str) -> bool:
    low = sentence.lower()
    if "%" in sentence or BONUS_PCT_RE.search(sentence):
        return True
    if _PROGRAM_ALIASES and any(re.search(p, low, re.IGNORECASE) for p in ("livelo", "esfera", "smiles", "azul", "latam")):
        return True
    m = re.search(r"\d{1,2}/\d{1,2}", sentence)
    if not m:
        return False
    low = sentence.lower()
    return bool(any(k in low for k in (" de ", " a ", "até", "ate", "valid", "vig", "período", "periodo")))


def _sanitize_sentence(sentence: str) -> str | None:
    """Remove gatilhos de injeção e histórico; retorna None se sentença descartada."""
    low = sentence.lower()
    if any(m in low for m in _NEGATION_MARKERS):
        return None
    if any(m in low for m in _HISTORY_MARKERS):
        return None
    # trunca em marcador de injeção
    for marker in _INJECTION_MARKERS:
        idx = low.find(marker)
        if idx != -1:
            pre = sentence[:idx].strip(" .,;:-")
            low_pre = pre.lower()
            if _promo_signal(pre):
                sentence = pre
                low = low_pre
            else:
                return None
    # remove sufixos com system:
    if "system:" in low:
        idx = low.find("system:")
        pre = sentence[:idx].strip(" .,;:-")
        if _promo_signal(pre):
            sentence = pre
        else:
            return None
    if any(m in low for m in _NEGATION_MARKERS):
        return None
    return sentence.strip()


def _sanitize(text_norm: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text_norm)
    kept = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        out = _sanitize_sentence(s)
        if out and _promo_signal(out):
            kept.append(out)
    if not kept:
        return ""
    return " ".join(kept)


def _to_date(value: Any):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _first_seen_sp_date(first_seen_at: Any) -> date | None:
    """Normaliza first_seen_at para date em America/Sao_Paulo; None se invalido/ausente."""
    if first_seen_at is None:
        return None
    dt = None
    if isinstance(first_seen_at, datetime):
        dt = first_seen_at
    elif isinstance(first_seen_at, date):
        return first_seen_at
    elif isinstance(first_seen_at, str):
        v = first_seen_at.strip()
        try:
            dt = datetime.fromisoformat(v)
        except ValueError:
            # aceitar date-only
            try:
                return date.fromisoformat(v)
            except ValueError:
                return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    try:
        return dt.astimezone(ZoneInfo("America/Sao_Paulo")).date()
    except (ValueError, OSError):
        return dt.date()


def _closest_year(fs_date: date, month: int, day: int) -> int:
    """Escolhe o ano em {fs-1, fs, fs+1} mais proximo, respeitando fs-7 para inicio."""
    candidates = []
    for y in (fs_date.year - 1, fs_date.year, fs_date.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        candidates.append((abs((d - fs_date).days), y, d))
    if not candidates:
        return fs_date.year
    # preferir data <= fs_date + 30 e >= fs_date - 7 quando possivel
    filtered = [c for c in candidates if (fs_date - timedelta(days=7)) <= c[2] <= (fs_date + timedelta(days=30))]
    pool = filtered if filtered else candidates
    pool.sort(key=lambda c: (c[0], c[1]))
    return pool[0][1]


def _make_date(day, month, year, fs_date: date | None, inferred: bool = False) -> str | None:
    try:
        d = int(day)
        if isinstance(month, str) and not month.isdigit():
            key = month.lower().strip()
            if key not in MONTHS_PT:
                alt = key.replace("c", "ç")
                if alt in MONTHS_PT:
                    key = alt
            m = MONTHS_PT.get(key, 0)
        else:
            m = int(month)
        if year is None or str(year).strip() == "":
            if fs_date is None:
                return None
            y = _closest_year(fs_date, int(m), int(d))
        else:
            y_raw = str(year).strip()
            if len(y_raw) == 2:
                y = 2000 + int(y_raw)
            else:
                y = int(y_raw)
        dt = date(int(y), int(m), int(d))
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


def _collect_dates(text_norm: str, first_seen_at: Any = None) -> list[str]:
    """Coleta datas ISO com causa point-in-time; None se first_seen ausente/invalido para datas sem ano."""
    fs_date = _first_seen_sp_date(first_seen_at)

    candidates = []
    for m in DATA_NUM_RE.finditer(text_norm):
        candidates.append((m.start(), m.group(1), m.group(2), m.group(3)))
    for m in DATA_EXT_RE.finditer(text_norm):
        candidates.append((m.start(), m.group(1), m.group(2), m.group(3)))

    explicit_years = []
    resolved = []  # (pos, iso, year_was_explicit)
    for pos, day, month, year in candidates:
        explicit = (year is not None and str(year).strip() != "")
        if not explicit:
            left = text_norm[max(0, pos - 40):pos].lower()
            right = text_norm[pos:pos + 20].lower()
            ctx = left + right
            if not any(k in ctx for k in (" de ", " a ", "até", "ate", "valid", "vig", "período", "periodo")):
                continue
        y = year
        if explicit:
            iso = _make_date(day, month, y, None)
        else:
            if fs_date is None:
                continue
            iso = _make_date(day, month, None, fs_date)
        if iso is None:
            continue
        if explicit:
            explicit_years.append((pos, iso))
        resolved.append((pos, iso, explicit))

    out = []
    for pos, iso, explicit in sorted(resolved, key=lambda x: x[0]):
        if not out or out[-1] != iso:
            out.append(iso)

    # rollover: +1 ano apenas se o ano do fim foi omitido
    if len(out) >= 2:
        try:
            d0 = date.fromisoformat(out[0])
            d1 = date.fromisoformat(out[1])
            if d1 < d0:
                second_explicit = any(iso == out[1] and exp for (_p, iso, exp) in resolved)
                if not second_explicit and fs_date is not None:
                    out[1] = d1.replace(year=d1.year + 1).isoformat()
        except ValueError:
            pass
    return out


def _programs_in(text_norm: str) -> list[str]:
    found = []
    for prog, rx_pat in [("livelo", r"livelo"), ("esfera", r"esfera"), ("latam_pass", r"latam\s*pass|latam_pass|latampass"),
                        ("smiles", r"smiles"), ("azul_fidelidade", r"azul\s*fidelidade|azul_fidelidade")]:
        for m in re.finditer(rx_pat, text_norm, re.IGNORECASE):
            found.append((m.start(), prog))
    found.sort()
    seen = set()
    ordered = []
    for _pos, prog in found:
        if prog not in seen:
            seen.add(prog)
            ordered.append(prog)
    return ordered


def _directional_pair(sentence: str) -> tuple[str | None, str | None]:
    aliases = {
        "livelo": r"livelo", "esfera": r"esfera",
        "latam_pass": r"latam\s*pass|latam_pass|latampass",
        "smiles": r"smiles",
        "azul_fidelidade": r"azul\s*fidelidade|azul_fidelidade",
    }
    progs = _programs_in(sentence)
    if len(progs) < 2:
        # N4: so vira destino em compra/desconto; demais casos sao None (N1 sem inventar)
        if len(progs) == 1 and any(k in sentence.lower() for k in ("compra", "desconto", "comprar")):
            return None, progs[0]
        return None, None
    # "X para Y" / "X -> Y" / "X a Y"
    for origin in progs:
        for dest in progs:
            if origin == dest:
                continue
            origin_rx = aliases[origin]
            dest_rx = aliases[dest]
            pat = re.compile(rf"{origin_rx}.{{0,80}}?(?:para|->|→|\ba\b).{{0,40}}?{dest_rx}", re.IGNORECASE | re.DOTALL)
            if pat.search(sentence):
                return origin, dest
    # conjunção " e " => sem direção
    if re.search(r"\be\b", sentence.lower()):
        return None, None
    return None, None


def _detect_type(sentence: str) -> str | None:
    low = sentence.lower()
    if any(k in low for k in ("bônus", "bonus", "bonifica")):
        return "transfer_bonus"
    if any(k in low for k in ("desconto", "compra")) and "bôn" not in low and "bonus" not in low:
        return "purchase_discount"
    if any(k in low for k in ("desconto",)):
        return "purchase_discount"
    if any(k in low for k in ("acúmulo", "acumulo", "turbinado", "acumule", "turbinad")):
        return "boosted_accrual"
    progs = _programs_in(sentence)
    if len(progs) >= 2:
        return "transfer_bonus"
    return None


def _extract_bonus(sentence: str, segmented_flag: list[bool]) -> int | float | None:
    segmented_flag[0] = False
    plus_total = None
    for a, b in re.findall(r"(\d{1,3}(?:,\d+)?)\s*%[^.]*?\+\s*(\d{1,3}(?:,\d+)?)\s*%", sentence, flags=re.IGNORECASE):
        try:
            plus_total = float(a.replace(",", ".")) + float(b.replace(",", "."))
        except ValueError:
            plus_total = None
        segmented_flag[0] = True
        break
    nums = []
    for m in BONUS_PCT_RE.finditer(sentence):
        val = m.group(1) or m.group(2)
        if val:
            try:
                nums.append(float(val.replace(",", ".")))
            except ValueError:
                pass
    base = max(nums) if nums else None
    if plus_total is not None:
        if base is None or plus_total > base:
            base = plus_total
        segmented_flag[0] = True
    if base is not None:
        # int when integral
        if float(base).is_integer():
            base = int(base)
        if base < 1 or base > 300:
            base = None
    return base


def _detect_segmented(sentence: str) -> bool:
    low = sentence.lower()
    if "clube" in low:
        return True
    if re.search(r"exclusiv[oa]\s+(?:para|do|da|de)", low):
        return True
    if re.search(r"cart[ãa]o\s+\w+", low):
        return True
    return bool("diamante" in low and "exclus" in low)


def _segment_label(sentence: str, segmented: bool) -> str | None:
    if not segmented:
        return None
    low = sentence.lower()
    if "clube" in low:
        return "clube"
    if "cartão" in low or "cartao" in low:
        return "cartao"
    return "segmentado"


# --- pydantic models --------------------------------------------------------
class Offer(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    origem: _PROGRAM_LITERALS | None = Field(default=None, alias="origin")
    destino: _PROGRAM_LITERALS | None = Field(default=None, alias="destination")
    tipo: _TYPE_LITERAL | None = Field(default=None, alias="type")
    bonus_pct: float | None = Field(default=None, ge=1, le=300)
    inicio: str | None = Field(default=None, alias="start", pattern=r"^20[2-3][0-9]-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
    fim: str | None = Field(default=None, alias="end", pattern=r"^20[2-3][0-9]-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
    segmentada: bool = Field(default=False, alias="segmented")
    segmento: str | None = Field(default=None, alias="segment_label")

    def __init__(self, /, **data: Any) -> None:
        mapping = {
            "origem": "origem", "origin": "origem",
            "destino": "destino", "destination": "destino",
            "tipo": "tipo", "type": "tipo", "event_type": "tipo",
            "bonus_pct": "bonus_pct", "bonus": "bonus_pct",
            "inicio": "inicio", "start": "inicio", "start_at": "inicio",
            "start_date": "inicio", "fim": "fim", "end": "fim",
            "end_at": "fim", "end_date": "fim", "segmentada": "segmentada",
            "segmented": "segmentada", "is_segmented": "segmentada",
            "segmento": "segmento", "segment_label": "segmento", "segment": "segmento",
        }
        translated = {}
        for k, v in data.items():
            key = mapping.get(k, k)
            translated[key] = v
        super().__init__(**translated)

    # alias properties EN
    @property
    def origin(self):
        return self.origem

    @origin.setter
    def origin(self, v):
        self.origem = v

    @property
    def destination(self):
        return self.destino

    @destination.setter
    def destination(self, v):
        self.destino = v

    @property
    def type(self):
        return self.tipo

    @type.setter
    def type(self, v):
        self.tipo = v

    @property
    def event_type(self):
        return self.tipo

    @event_type.setter
    def event_type(self, v):
        self.tipo = v

    @property
    def start(self):
        return self.inicio

    @property
    def start_at(self):
        return self.inicio

    @property
    def start_date(self):
        return self.inicio

    @property
    def end(self):
        return self.fim

    @property
    def end_at(self):
        return self.fim

    @property
    def end_date(self):
        return self.fim

    @property
    def segmented(self):
        return self.segmentada

    @segmented.setter
    def segmented(self, v):
        self.segmentada = bool(v)

    @property
    def segment_label(self):
        return self.segmento

    def is_valid(self, first_seen_at=None, reference_date=None, mode="live"):
        ok, _ = validate_offer(self, first_seen_at=first_seen_at, mode=mode)
        return ok

    def to_dict(self):
        return {
            "origem": self.origem, "destino": self.destino, "tipo": self.tipo,
            "bonus_pct": self.bonus_pct, "inicio": self.inicio, "fim": self.fim,
            "segmentada": self.segmentada, "segmento": self.segmento,
        }


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ofertas: list[Offer] = Field(default_factory=list, alias="offers")

    def __init__(self, /, **data):
        mapping = {
            "ofertas": "ofertas", "offers": "ofertas", "items": "ofertas",
            "results": "ofertas", "promotions": "ofertas", "promoções": "ofertas",
            "oferta": "ofertas",
        }
        translated = {}
        for k, v in data.items():
            key = mapping.get(k, k)
            if key == "ofertas" and isinstance(v, (Offer, dict)) and not isinstance(v, list):
                v = [v]
            if key == "ofertas" and v is None:
                v = []
            translated[key] = v
        if "ofertas" not in translated and not translated:
            translated["ofertas"] = []
        super().__init__(**translated)

    @property
    def offers(self):
        return self.ofertas

    @offers.setter
    def offers(self, v):
        if isinstance(v, (Offer, dict)):
            self.ofertas = [v if isinstance(v, Offer) else Offer(**v)]
        else:
            self.ofertas = list(v or [])

    @property
    def items(self):
        return self.ofertas

    @property
    def promotions(self):
        return self.ofertas

    @property
    def results(self):
        return self.ofertas

    def to_dict(self):
        return {"ofertas": [o.to_dict() for o in self.ofertas]}


# aliases classes
OfferExtraction = Extraction
ExtractionResult = Extraction
PromoExtraction = Extraction
ExtractedPromotion = Offer
ExtractedOffer = Offer
Promotion = Offer
OfferSchema = Offer
PromoOffer = Offer
PromotionOffer = Offer


def _has_invalid_date(sentence: str, first_seen_at: Any = None) -> bool:
    fs_date = _first_seen_sp_date(first_seen_at)
    for m in DATA_NUM_RE.finditer(sentence):
        y = m.group(3)
        # invalid if explicit year invalid OR (no year & no fs)
        if y and str(y).strip():
            if _make_date(m.group(1), m.group(2), y, None) is None:
                return True
        else:
            if fs_date is None:
                return True
            if _make_date(m.group(1), m.group(2), None, fs_date) is None:
                return True
    for m in DATA_EXT_RE.finditer(sentence):
        y = m.group(3)
        if y and str(y).strip():
            if _make_date(m.group(1), m.group(2), y, None) is None:
                return True
        else:
            if fs_date is None:
                return True
            if _make_date(m.group(1), m.group(2), None, fs_date) is None:
                return True
    return False



_BONUS_CONFLICT_CACHE: set[str] = set()


def detect_bonus_conflict(text: Any) -> bool:
    """Retorna True se houver mais de um percentual de bônus distinto (sem soma additive)."""
    tn = normalize(text)
    vals = []
    for m in BONUS_PCT_RE.finditer(tn):
        v = m.group(1) or m.group(2)
        if v:
            try:
                vals.append(float(v.replace(",", ".")))
            except ValueError:
                pass
    distinct = {round(x, 3) for x in vals}
    # additive plus patterns não contam como conflito
    if re.search(r"\d{1,3}(?:,\d+)?\s*%[^.]*?\+\s*\d{1,3}(?:,\d+)?\s*%", tn):
        return False
    return len(distinct) > 1


has_bonus_conflict = detect_bonus_conflict

def _build_offer(sentence: str, first_seen_at: Any = None) -> Offer | None:
    sentence = sentence.strip()
    if not sentence:
        return None
    norm = normalize(sentence)
    cleaned = _sanitize_sentence(norm)
    if not cleaned:
        return None
    if _has_invalid_date(cleaned, first_seen_at):
        return None
    if not _promo_signal(cleaned):
        return None
    origin, dest = _directional_pair(cleaned)
    tipo = _detect_type(cleaned)
    segmented_flag = [False]
    bonus = _extract_bonus(cleaned, segmented_flag)
    segmented = _detect_segmented(cleaned) or segmented_flag[0]
    conflict = detect_bonus_conflict(cleaned)
    if conflict:
        segmento = "bonus_conflitante"
    else:
        segmento = _segment_label(cleaned, segmented)
    dates = _collect_dates(cleaned, first_seen_at)
    if len(dates) >= 2:
        inicio = dates[0]
        fim = dates[1]
    elif len(dates) == 1:
        d0 = dates[0]
        lowc = cleaned.lower()
        if any(k in lowc for k in ("até", "ate", "válido", "valido", "validade", "termina", "encerra")):
            inicio = None
            fim = d0
        else:
            inicio = d0
            fim = None
    else:
        inicio = None
        fim = None

    # require tipo + bonus/desconto ligado
    if tipo is None:
        return None
    if bonus is None and not (dates and any(k in cleaned.lower() for k in ("bônus", "bonus", "bonifica", "desconto"))):
        return None
    # require some promotion signal
    if bonus is None and not dates and origin is None and dest is None and tipo is None:
        return None
    if bonus is None and not dates and tipo is None:
        return None
    # drop if negation (already handled)
    try:
        return Offer(
            origem=origin,
            destino=dest,
            tipo=tipo,
            bonus_pct=bonus,
            inicio=inicio,
            fim=fim,
            segmentada=segmented,
            segmento=segmento,
        )
    except (ValueError, TypeError):
        return None


def extract(text: Any, first_seen_at: Any = None, **kwargs: Any) -> Extraction:
    if "first_seen" in kwargs and first_seen_at is None:
        first_seen_at = kwargs.pop("first_seen")
    if "reference_date" in kwargs and first_seen_at is None:
        first_seen_at = kwargs.pop("reference_date")
    if "first_seen_at" in kwargs and first_seen_at is None:
        first_seen_at = kwargs.pop("first_seen_at")
    tn = _sanitize(normalize(text))
    offers = []
    if tn:
        off = _build_offer(tn, first_seen_at=first_seen_at)
        if off is not None and not (off.origem is None and off.destino is None and off.tipo is None
                                        and off.bonus_pct is None and off.inicio is None and off.fim is None):
            offers.append(off)
    # dedup
    uniq = []
    seen_keys = set()
    for o in offers:
        key = (o.origem, o.destino, o.tipo, o.bonus_pct, o.inicio, o.fim)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        uniq.append(o)
    return Extraction(ofertas=uniq)


# aliases
def extract_text(*a, **k):
    return extract(*a, **k)

def extract_promo(*a, **k):
    ex = extract(*a, **k)
    return ex.ofertas[0] if ex.ofertas else None

def extract_promotion(*a, **k):
    return extract_promo(*a, **k)

def extract_promotions(*a, **k):
    return extract(*a, **k).ofertas

def extract_offers(*a, **k):
    return extract(*a, **k).ofertas

def parse(*a, **k):
    return extract(*a, **k)

def parse_promotion(*a, **k):
    return extract_promo(*a, **k)

def regex_extract(text: Any, first_seen_at: Any = None, **kwargs: Any) -> dict[str, Any]:
    first_seen_at = first_seen_at or kwargs.get("first_seen_at") or kwargs.get("first_seen")
    tn = _sanitize(normalize(text))
    origin, dest = _directional_pair(tn)
    dates = _collect_dates(tn, first_seen_at)
    inicio = dates[0] if dates else None
    fim = dates[1] if len(dates) >= 2 else None
    seg_flag = [False]
    bonus = _extract_bonus(tn, seg_flag)
    segmented = _detect_segmented(tn) or seg_flag[0]
    return {
        "origem": origin,
        "destino": dest,
        "tipo": _detect_type(tn),
        "bonus_pct": bonus,
        "inicio": inicio,
        "fim": fim,
        "segmentada": segmented,
        "segmento": _segment_label(tn, segmented),
        "normalizado": tn,
        "datas": dates,
        "programas": _programs_in(tn),
    }


def validate_offer(offer, first_seen_at=None, reference_date=None, mode="live",
                  **kwargs) -> tuple[bool, list[str]]:
    if first_seen_at is None:
        first_seen_at = kwargs.get("first_seen_at", kwargs.get("first_seen"))
    if reference_date is not None:
        first_seen_at = reference_date
    reasons = []
    o = offer if isinstance(offer, Offer) else Offer(**(offer or {}))
    start_date = _to_date(o.inicio)
    end_date = _to_date(o.fim)
    if o.inicio is not None and start_date is None:
        reasons.append("inicio_invalido")
    if o.fim is not None and end_date is None:
        reasons.append("fim_invalido")
    if start_date and end_date:
        if end_date < start_date:
            reasons.append("fim_antes_inicio")
        if (end_date - start_date).days > 90:
            reasons.append("janela_maior_90")
    # campos ausentes
    if o.origem is None or o.destino is None or o.tipo is None:
        reasons.append("campos_ausentes")
    if o.inicio is None and o.fim is None and o.bonus_pct is None:
        reasons.append("oferta_vazia")
    if first_seen_at is not None:
        fs = first_seen_at
        if isinstance(fs, str):
            try:
                fs = date.fromisoformat(fs)
            except ValueError:
                fs = None
        if isinstance(fs, datetime):
            fs = fs.date()
        if isinstance(fs, date) and start_date is not None:
            tol_past = 365 if mode == "backfill" else 7
            tol_future = 365 if mode == "backfill" else 30
            if start_date > fs + timedelta(days=tol_future):
                reasons.append("inicio_muito_futuro")
            if start_date < fs - timedelta(days=tol_past):
                reasons.append("inicio_muito_passado")
    if o.bonus_pct is not None and (o.bonus_pct < 1 or o.bonus_pct > 300):
        reasons.append("bonus_pct_invalido")
    if o.tipo == "transfer_bonus" and o.origem == "livelo" and o.destino == "smiles" and o.bonus_pct is not None and (o.bonus_pct < 10 or o.bonus_pct > 150):
        reasons.append("bonus_pct_fora_faixa")
    return len(reasons) == 0, reasons


def validate_business_rules(*a, **k):
    if a and isinstance(a[0], (Offer, dict)):
        offer = a[0]
        first_seen = k.get("first_seen_at", k.get("first_seen", None))
        if len(a) > 1:
            first_seen = a[1]
        return validate_offer(offer, first_seen_at=first_seen, **{kk: vv for kk, vv in k.items() if kk not in ("first_seen_at", "first_seen")})
    textv = k.get("text") or (a[0] if a and isinstance(a[0], str) else None)
    if textv is not None:
        off = extract_promo(textv, first_seen_at=k.get("first_seen_at"))
        return validate_offer(off) if off is not None else (False, ["sem_oferta"])
    return (True, [])


def has_bonus_pct_in_text(text: Any, bonus: Any) -> bool:
    tn = normalize(text)
    nums = []
    for m in BONUS_PCT_RE.finditer(tn):
        val = m.group(1) or m.group(2)
        if val:
            try:
                nums.append(float(val.replace(",", ".")))
            except ValueError:
                pass
    for a, b in re.findall(r"(\d{1,3}(?:,\d+)?)\s*%\s*\+\s*(\d{1,3}(?:,\d+)?)\s*%", tn):
        try:
            nums.append(float(a.replace(",", ".")) + float(b.replace(",", ".")))
        except ValueError:
            pass
    try:
        b = float(str(bonus).replace(",", "."))
    except (TypeError, ValueError):
        return False
    return any(abs(n - b) < 1e-9 for n in nums)


def cross_check(text: Any, offer=None) -> bool:
    if isinstance(offer, dict):
        try:
            offer = Offer(**offer)
        except (ValueError, TypeError):
            return False
    if offer is None or offer.bonus_pct is None:
        return True
    if not re.search(r"\d+\s*%", normalize(text)):
        return False
    return has_bonus_pct_in_text(text, offer.bonus_pct)


extract_regex = regex_extract
normalize_text = normalize
extract_one = extract_promo
extract_list = extract_promotions
extract_all = extract_offers
parse_text = parse
parse_offer = parse_promotion


__all__ = [
    "BONUS_CTX",
    "BONUS_CTX_RE",
    "BONUS_PCT",
    "BONUS_PCT_RE",
    "DATA_EXT",
    "DATA_EXT_RE",
    "DATA_NUM",
    "DATA_NUM_RE",
    "PAR",
    "PAR_RE",
    "PROGRAMS",
    "SEGMENTO",
    "SEGMENTO_RE",
    "ExtractedOffer",
    "ExtractedPromotion",
    "Extraction",
    "ExtractionResult",
    "Offer",
    "OfferExtraction",
    "OfferSchema",
    "PromoExtraction",
    "PromoOffer",
    "Promotion",
    "PromotionOffer",
    "cross_check",
    "extract",
    "extract_all",
    "extract_list",
    "extract_offers",
    "extract_one",
    "extract_promo",
    "extract_promotion",
    "extract_promotions",
    "extract_regex",
    "extract_text",
    "has_bonus_pct_in_text",
    "normalize",
    "normalize_text",
    "parse",
    "parse_offer",
    "parse_promotion",
    "parse_text",
    "regex_extract",
    "validate_business_rules",
    "validate_offer",
]
