# src/core/decimal_utils.py
"""
Finansal Hassasiyet ve Yuvarlama Yardımcıları (Decimal Utilities)
Muhasebe ve FinTech standartlarına uygun Decimal dönüşümleri ve kuruş yuvarlama.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Optional, Union

CURRENCY_QUANT = Decimal('0.01')      # 2 ondalık basamak (Kuruş)
QUANTITY_QUANT = Decimal('0.001')     # 3 ondalık basamak (Miktar/Stok)
RATE_QUANT = Decimal('0.01')          # 2 ondalık basamak (Vergi / İskonto oranı)


def to_decimal(val: Any, default: Union[str, Decimal] = Decimal('0.00')) -> Decimal:
    """
    Herhangi bir değeri (float, int, str, Decimal) kayıpsız bir şekilde Decimal'e dönüştürür.
    Float dönüşümünde IEEE-754 kayıplarını önlemek için str() üzerinden dönüştürür.
    """
    if val is None:
        return Decimal(str(default))
    if isinstance(val, Decimal):
        return val
    try:
        if isinstance(val, float):
            # float -> str -> Decimal (Doğrudan float2decimal IEEE-754 sapmasını önler)
            return Decimal(str(round(val, 6)))
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(str(default))


def round_currency(val: Any) -> Decimal:
    """
    Finansal tutarı kuruş seviyesinde (0.01) ROUND_HALF_UP kuralına göre yuvarlar.
    Örnek: 19.995 -> 20.00, 19.994 -> 19.99
    """
    d = to_decimal(val)
    return d.quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)


def round_quantity(val: Any) -> Decimal:
    """
    Stok ve kalem miktarlarını (0.001) ROUND_HALF_UP kuralına göre yuvarlar.
    """
    d = to_decimal(val, default=Decimal('0.000'))
    return d.quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)


def round_rate(val: Any) -> Decimal:
    """
    Vergi veya iskonto oranını (0.01) yuvarlar.
    """
    d = to_decimal(val, default=Decimal('0.00'))
    return d.quantize(RATE_QUANT, rounding=ROUND_HALF_UP)
