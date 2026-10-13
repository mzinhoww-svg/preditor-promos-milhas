from __future__ import annotations

"""Camada determinística de extração (regex + pydantic)."""
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PROGRAMS: tuple[str, ...] = ("livelo", "esfera", "latam_pass", "smiles", "azul_fidelidade")

_PROGRAM_ALIASES: dict[str, re.Pattern[str]] = {
    "livelo": re.compile(r"livelo", re.IGNORECASE),
    "esfera": re.compile(r"esfera", re.IGNORECASE),
    "latam_pass": re.compile(r"latam\s*pass|latam_pass|latampass", re.IGNORECASE),
    "smiles": re.compile(r"smiles", re.IGNORECASE),
    "azul_fidelidade": re.compile(r"azul\s*fidelidade|azul_fidelidade", re.IGNORECASE),
}

_EVENT_TYPES: tuple[str, ...] = ("transfer_bonus", "purchase_discount", "boosted_accrual")

PAR = r"\blivelo\b.{0,120}\bsmiles\b|\bsmiles\b.{0,120}\blivelo\b"
PAR_RE = re.compile(PAR, re.IGNORECASE | re.DOTALL)

BONUS_CTX = r"b[ôo]nus|bonificad[ao]|transfer[êe]ncia"
BONUS_CTX_RE = re.compile(BONUS_CTX, re.IGNORECASE)

BONUS_PCT = r"(?:at[ée]\s+)?(?<!\d)(\d{2,3})\s?%(?=\s*(?:de\s+)?(?:b[ôo]nus|bonifica|na\s+transfer))|b[ôo]nus\s+de\s+(?:at[ée]\s+)?(\d{2,3})\s?%"
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

SEGMENTO = r"clube\s+(?:livelo|smiles|latam|azul|esfera)|exclusiv[oa]\s+para|somente\s+para\s+(?:clientes|assinantes|membros)|cart[ãa]o\s+\w+|diamante|ouro|prata|p[úu]blico"
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
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _current_year() -> int:
    return date.today().year


def _fix_year(y: str | None) -> int:
    if y is None:
        return _current_year()
    y = y.strip()
    if len(y) == 2:
        return 2000 + int(y)
    return int(y)


def _make_date(day, month, year) -> str | None:
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
        y = _fix_year(None if year is None else str(year))
        dt = date(y, int(m), int(d))
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


def _collect_dates(text_norm: str) -> list[str]:
    candidates = []
    for m in DATA_NUM_RE.finditer(text_norm):
        candidates.append({"pos": m.start(), "day": m.group(1), "month": m.group(2),
                          "year": m.group(3)})
    for m in DATA_EXT_RE.finditer(text_norm):
        candidates.append({"pos": m.start(), "day": m.group(1), "month": m.group(2),
                          "year": m.group(3)})
    candidates.sort(key=lambda c: c["pos"])
    explicit_years = [(c["pos"], c["year"]) for c in candidates if c["year"]]
    normalized = []
    for c in candidates:
        year = c["year"]
        if not year and explicit_years:
            nearest = min(explicit_years, key=lambda y: abs(y[0] - c["pos"]))
            year = nearest[1]
        iso = _make_date(c["day"], c["month"], year)
        if iso:
            normalized.append((c["pos"], iso))
    out = []
    for _pos, iso in sorted(normalized, key=lambda x: x[0]):
        if not out or out[-1] != iso:
            out.append(iso)
    return out


def _near_promo_context(text_norm: str, pos: int, window: int = 90) -> bool:
    seg = text_norm[max(0, pos - window): pos + window].lower()
    keys = ("bônus", "bonus", "bonifica", "transfer", "compra", "desconto",
            "acúmulo", "acumulo", "turbinado", "ponto", "milha", "%", "/",
            " de ", " a ", "até", "ate")
    return any(k in seg for k in keys)


def _programs_in(text_norm: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for prog, rx in _PROGRAM_ALIASES.items():
        for m in rx.finditer(text_norm):
            if _near_promo_context(text_norm, m.start()):
                found.append((m.start(), prog))
    found.sort()
    seen: set[str] = set()
    ordered: list[str] = []
    for _pos, prog in found:
        if prog not in seen:
            seen.add(prog)
            ordered.append(prog)
    return ordered


def _detect_pair(text_norm: str) -> tuple[str | None, str | None]:
    progs = _programs_in(text_norm)
    if len(progs) >= 2:
        for origin in progs:
            for dest in progs:
                if origin == dest:
                    continue
                origin_rx = _PROGRAM_ALIASES[origin].pattern
                dest_rx = _PROGRAM_ALIASES[dest].pattern
                pat = re.compile(rf"{origin_rx}.{{0,120}}?(?:para|->|→|a\b|em\b).{{0,40}}?{dest_rx}", re.IGNORECASE | re.DOTALL)
                if pat.search(text_norm):
                    return origin, dest
        return progs[0], progs[1]
    if len(progs) == 1:
        return None, None
    return None, None


def _detect_type(text_norm: str) -> str | None:
    low = text_norm.lower()
    if any(k in low for k in ("compra", "desconto", "comprar")):
        return "purchase_discount"
    if any(k in low for k in ("acúmulo", "acumulo", "turbinado", "acumule", "turbinad")):
        return "boosted_accrual"
    if any(k in low for k in ("bônus", "bonus", "bonifica", "transferência", "transferencia", "transfira")):
        return "transfer_bonus"
    progs = _programs_in(text_norm)
    if len(progs) >= 2:
        return "transfer_bonus"
    return None


def _extract_bonus(text_norm: str) -> tuple[int | None, bool]:
    segmented = False
    tn = text_norm
    if SEGMENTO_RE.search(tn):
        segmented = True
    plus_total = None
    for a, b in re.findall(r"(\d{2,3})\s*%\s*\+\s*(\d{1,3})\s*%", tn, flags=re.IGNORECASE):
        plus_total = int(a) + int(b)
    nums: list[int] = []
    for m in BONUS_PCT_RE.finditer(tn):
        val = m.group(1) or m.group(2)
        if val:
            nums.append(int(val))
    if not nums:
        for m in re.finditer(r"(\d{2,3})\s?%", tn):
            nums.append(int(m.group(1)))
    base: int | None = max(nums) if nums else None
    if plus_total is not None:
        if base is None or plus_total > base:
            base = plus_total
        segmented = True
    if base is not None:
        base = max(base, 1)
        if base > 300:
            base = None
    return base, segmented


def _detect_segmented(text_norm: str, segmented_flag: bool) -> bool:
    if segmented_flag:
        return True
    return bool(SEGMENTO_RE.search(text_norm))


def _segment_label(text_norm: str, segmented: bool) -> str | None:
    if not segmented:
        return None
    low = text_norm.lower()
    if "clube" in low:
        return "clube"
    if "público" in low or "publico" in low:
        return "publico"
    if SEGMENTO_RE.search(text_norm):
        return "segmentado"
    return None


def _all_dates_valid(text_norm: str) -> bool:
    for m in DATA_NUM_RE.finditer(text_norm):
        if _make_date(m.group(1), m.group(2), m.group(3)) is None:
            return False
    for m in DATA_EXT_RE.finditer(text_norm):
        if _make_date(m.group(1), m.group(2), m.group(3)) is None:
            return False
    return True


def _parse_date_field(text_norm: str, dates: list[str]) -> tuple[str | None, str | None]:
    inicio: str | None = None
    fim: str | None = None
    low = text_norm.lower()
    if len(dates) >= 2:
        inicio = dates[0]
        fim = dates[1]
    elif len(dates) == 1:
        d0 = dates[0]
        if any(k in low for k in ("até", "ate", "válido até", "valido ate", "termina", "encerra")):
            fim = d0
        elif any(k in low for k in ("a partir de", "desde", "início", "inicio", "começa", "comeca")):
            inicio = d0
        else:
            inicio = d0
    return inicio, fim


class Offer(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    origem: str | None = Field(default=None, alias="origin")
    destino: str | None = Field(default=None, alias="destination")
    tipo: str | None = Field(default=None, alias="type")
    bonus_pct: int | None = None
    inicio: str | None = Field(default=None, alias="start")
    fim: str | None = Field(default=None, alias="end")
    segmentada: bool = Field(default=False, alias="segmented")
    segmento: str | None = Field(default=None, alias="segment_label")

    def __init__(self, /, **data: Any) -> None:
        mapping = {
            "origem": "origem", "origin": "origem",
            "destino": "destino", "destination": "destino",
            "tipo": "tipo", "type": "tipo", "event_type": "tipo",
            "bonus_pct": "bonus_pct", "bonus": "bonus_pct",
            "inicio": "inicio", "start": "inicio", "start_at": "inicio",
            "start_date": "inicio",
            "fim": "fim", "end": "fim", "end_at": "fim", "end_date": "fim",
            "segmentada": "segmentada", "segmented": "segmentada",
            "is_segmented": "segmentada",
            "segmento": "segmento", "segment_label": "segmento", "segment": "segmento",
        }
        translated: dict[str, Any] = {}
        for k, v in data.items():
            key = mapping.get(k, k)
            translated[key] = v
        super().__init__(**translated)

    @property
    def origin(self) -> str | None:
        return self.origem

    @origin.setter
    def origin(self, v: Any) -> None:
        self.origem = v

    @property
    def destination(self) -> str | None:
        return self.destino

    @destination.setter
    def destination(self, v: Any) -> None:
        self.destino = v

    @property
    def type(self) -> str | None:
        return self.tipo

    @type.setter
    def type(self, v: Any) -> None:
        self.tipo = v

    @property
    def event_type(self) -> str | None:
        return self.tipo

    @event_type.setter
    def event_type(self, v: Any) -> None:
        self.tipo = v

    @property
    def start(self) -> str | None:
        return self.inicio

    @property
    def start_at(self):
        v = self.inicio
        return _to_date(v) if v is not None else None

    @property
    def start_date(self):
        return self.start_at

    @property
    def end(self) -> str | None:
        return self.fim

    @property
    def end_at(self):
        v = self.fim
        return _to_date(v) if v is not None else None

    @property
    def end_date(self):
        return self.end_at

    @property
    def segmented(self) -> bool:
        return self.segmentada

    @segmented.setter
    def segmented(self, v: Any) -> None:
        self.segmentada = bool(v)

    @property
    def segment_label(self) -> str | None:
        return self.segmento

    def is_valid(self, first_seen_at: Any = None, reference_date: Any = None) -> bool:
        ok, _ = validate_offer(self, first_seen_at=first_seen_at, reference_date=reference_date)
        return ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "origem": self.origem,
            "destino": self.destino,
            "tipo": self.tipo,
            "bonus_pct": self.bonus_pct,
            "inicio": self.inicio,
            "fim": self.fim,
            "segmentada": self.segmentada,
            "segmento": self.segmento,
        }


def _to_date(value: Any):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ofertas: list[Offer] = Field(default_factory=list, alias="offers")

    def __init__(self, /, **data: Any) -> None:
        mapping = {
            "ofertas": "ofertas", "offers": "ofertas", "items": "ofertas",
            "results": "ofertas", "promotions": "ofertas", "promoções": "ofertas",
            "oferta": "ofertas",
        }
        translated: dict[str, Any] = {}
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
    def offers(self) -> list[Offer]:
        return self.ofertas

    @offers.setter
    def offers(self, v: Any) -> None:
        if isinstance(v, (Offer, dict)):
            self.ofertas = [v if isinstance(v, Offer) else Offer(**v)]
        else:
            self.ofertas = list(v or [])

    @property
    def items(self) -> list[Offer]:
        return self.ofertas

    @property
    def promotions(self) -> list[Offer]:
        return self.ofertas

    @property
    def results(self) -> list[Offer]:
        return self.ofertas

    def to_dict(self) -> dict[str, Any]:
        return {"ofertas": [o.to_dict() for o in self.ofertas]}


OfferExtraction = Extraction
ExtractionResult = Extraction
PromoExtraction = Extraction
ExtractedPromotion = Offer
ExtractedOffer = Offer
Promotion = Offer
OfferSchema = Offer
PromoOffer = Offer
PromotionOffer = Offer


def _sanitize(text_norm: str) -> str:
    """Trata instruções embutidas como dado: descarta sentenças com gatilhos
    típicos de prompt injection, preservando o trecho factual."""
    triggers = ("ignore", "ignorar", "disregard", "override", "jailbreak",
                "instruç", "instruc", "system prompt", "voce e", "você é",
                "you are", "act as", "finja", "pretend")
    parts = re.split(r"(?<=[.!?])\s+", text_norm)
    kept = [p for p in parts if not any(t in p.lower() for t in triggers)]
    out = " ".join(kept).strip()
    return out if out else text_norm


def _build_offer(text_norm: str) -> Offer | None:
    text_norm = _sanitize(text_norm)
    origin, dest = _detect_pair(text_norm)
    tipo = _detect_type(text_norm)
    bonus_pct, segmented_plus = _extract_bonus(text_norm)
    segmented = _detect_segmented(text_norm, segmented_plus)
    if not _all_dates_valid(text_norm):
        return None
    dates = _collect_dates(text_norm)
    inicio, fim = _parse_date_field(text_norm, dates)
    segmento = _segment_label(text_norm, segmented)
    if origin is None and dest is None and tipo is None and bonus_pct is None and not dates:
        return None
    if tipo is None and bonus_pct is None and not dates and origin is None and dest is None:
        return None
    if origin is not None and origin == dest:
        dest = None
    if origin is not None and origin not in PROGRAMS:
        origin = None
    if dest is not None and dest not in PROGRAMS:
        dest = None
    if tipo is not None and tipo not in _EVENT_TYPES:
        tipo = None
    if inicio is not None and _to_date(inicio) is None:
        inicio = None
    if fim is not None and _to_date(fim) is None:
        fim = None
    return Offer(
        origem=origin,
        destino=dest,
        tipo=tipo,
        bonus_pct=bonus_pct,
        inicio=inicio,
        fim=fim,
        segmentada=segmented,
        segmento=segmento,
    )


def extract(text: Any, first_seen_at: Any = None, **kwargs: Any) -> Extraction:
    tn = _sanitize(normalize(text))
    offers: list[Offer] = []
    if tn:
        offer = _build_offer(tn)
        if offer is not None and not (offer.origem is None and offer.destino is None and offer.tipo is None
                                      and offer.bonus_pct is None and offer.inicio is None and offer.fim is None):
            offers.append(offer)
    return Extraction(ofertas=offers)


def extract_text(*a: Any, **k: Any) -> Extraction:
    return extract(*a, **k)


def extract_promo(*a: Any, **k: Any) -> Offer | None:
    ex = extract(*a, **k)
    return ex.ofertas[0] if ex.ofertas else None


def extract_promotion(*a: Any, **k: Any) -> Offer | None:
    return extract_promo(*a, **k)


def extract_promotions(*a: Any, **k: Any) -> list[Offer]:
    return extract(*a, **k).ofertas


def extract_offers(*a: Any, **k: Any) -> list[Offer]:
    return extract(*a, **k).ofertas


def parse(*a: Any, **k: Any) -> Extraction:
    return extract(*a, **k)


def parse_promotion(*a: Any, **k: Any) -> Offer | None:
    return extract_promo(*a, **k)


def regex_extract(text: Any) -> dict[str, Any]:
    tn = _sanitize(normalize(text))
    origin, dest = _detect_pair(tn)
    dates = _collect_dates(tn)
    inicio, fim = _parse_date_field(tn, dates)
    bonus_pct, seg_plus = _extract_bonus(tn)
    segmented = _detect_segmented(tn, seg_plus)
    return {
        "origem": origin,
        "destino": dest,
        "tipo": _detect_type(tn),
        "bonus_pct": bonus_pct,
        "inicio": inicio,
        "fim": fim,
        "segmentada": segmented,
        "segmento": _segment_label(tn, segmented),
        "normalizado": tn,
        "datas": dates,
        "programas": _programs_in(tn),
    }


def validate_offer(offer, first_seen_at=None, reference_date=None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
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
    if first_seen_at is not None:
        fs = first_seen_at
        if isinstance(fs, str):
            try:
                fs = date.fromisoformat(fs)
            except ValueError:
                fs = None
        if isinstance(fs, datetime):
            fs = fs.date()
        if isinstance(fs, date) and start_date:
            if start_date > fs + timedelta(days=30):
                reasons.append("inicio_muito_futuro")
            if start_date < fs - timedelta(days=7):
                reasons.append("inicio_muito_passado")
    if o.origem == "livelo" and o.destino == "smiles" and o.tipo == "transfer_bonus" and o.bonus_pct is not None and (o.bonus_pct < 10 or o.bonus_pct > 150):
        reasons.append("bonus_pct_fora_faixa")
    if o.bonus_pct is not None and (o.bonus_pct < 1 or o.bonus_pct > 300):
        reasons.append("bonus_pct_invalido")
    return (len(reasons) == 0, reasons)


def validate_business_rules(*a, **k) -> tuple[bool, list[str]]:
    if a and isinstance(a[0], (Offer, dict)):
        offer = a[0]
        first_seen = k.get("first_seen_at", k.get("first_seen", None))
        if len(a) > 1:
            first_seen = a[1]
        return validate_offer(offer, first_seen_at=first_seen)
    text = k.get("text") or (a[0] if a and isinstance(a[0], str) else None)
    if text is not None:
        off = extract_promo(text)
        return validate_offer(off) if off is not None else (True, [])
    return (True, [])


def has_bonus_pct_in_text(text: Any, bonus: Any) -> bool:
    tn = normalize(text)
    nums = []
    for m in BONUS_PCT_RE.finditer(tn):
        val = m.group(1) or m.group(2)
        if val:
            nums.append(int(val))
    for a, b in re.findall(r"(\d{2,3})\s*%\s*\+\s*(\d{1,3})\s*%", tn):
        nums.append(int(a) + int(b))
    try:
        b = int(bonus)
    except (TypeError, ValueError):
        return False
    return b in nums


def cross_check(text: Any, offer=None) -> bool:
    if isinstance(offer, dict):
        offer = Offer(**offer)
    # allow positional text only?
    if offer is None:
        return True
    if offer.bonus_pct is None:
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
