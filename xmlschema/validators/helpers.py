#
# Copyright (c), 2016-2026, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from decimal import Decimal
from math import isinf, isnan
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Any, Optional, SupportsInt, SupportsFloat, TYPE_CHECKING, Union
from xml.etree.ElementTree import Element
from elementpath import datatypes

import xmlschema.names as nm
from xmlschema.aliases import ElementType, SchemaType
from xmlschema.exceptions import XMLSchemaValueError
from xmlschema.translation import gettext as _
from .exceptions import XMLSchemaValidationError

if TYPE_CHECKING:
    from xmlschema.validators import XsdAnnotation, XsdComponent  # noqa: F401

XSD_FINAL_ATTRIBUTE_VALUES = {'restriction', 'extension', 'list', 'union'}
XSD_BOOLEAN_MAP = {
    'false': False, '0': False,
    'true': True, '1': True
}


def get_xsd_annotation(elem: ElementType,
                       schema: SchemaType,
                       parent: Optional['XsdComponent'] = None) -> Optional['XsdAnnotation']:
    """
    Returns the XSD annotation from the 1st child element of the provided element,
    `None` if it doesn't exist.
    """
    for child in elem:
        if child.tag == nm.XSD_ANNOTATION:
            return schema.builders.annotation_class(
                child, schema, parent, parent_elem=elem
            )
        elif not callable(child.tag):
            return None
    else:
        return None


def get_schema_annotations(schema: SchemaType) -> list['XsdAnnotation']:
    annotations = []
    annotation_class = schema.builders.annotation_class

    for elem in schema.source.root:
        if elem.tag == nm.XSD_ANNOTATION:
            annotations.append(annotation_class(elem, schema))
        elif elem.tag in nm.SCHEMA_DECLARATION_TAGS or elem.tag == nm.XSD_DEFAULT_OPEN_CONTENT:
            annotation = get_xsd_annotation(elem, schema)
            if annotation is not None:
                annotations.append(annotation)

    return annotations


def parse_xsd_derivation(elem: Element,
                         name: str,
                         choices: Union[None, set[str], tuple[str, ...]] = None,
                         validator: Union[None, SchemaType, 'XsdComponent'] = None) -> str:
    """
    Get a derivation attribute (maybe 'block', 'blockDefault', 'final' or 'finalDefault')
    checking the items with the values arguments. Returns a string.

    :param elem: the Element instance.
    :param name: the attribute name.
    :param choices: a set of admitted values when the attribute value is not '#all'.
    :param validator: optional schema or a component (element or type) to report \
    a parse error instead of raising a `ValueError`.
    """
    try:
        value = elem.attrib[name]
    except KeyError:
        return ''

    if choices is None:
        choices = XSD_FINAL_ATTRIBUTE_VALUES

    items = value.split()
    if len(items) == 1 and items[0] == '#all':
        return ' '.join(choices)
    elif not all(s in choices for s in items):
        msg = _("wrong value {!r} for attribute {!r}").format(value, name)
        if validator is None:
            raise ValueError(msg)
        validator.parse_error(msg)
        return ''
    return value


def parse_xpath_default_namespace(validator: Union[SchemaType, 'XsdComponent']) -> str:
    """
    Parse XSD 1.1 xpathDefaultNamespace attribute for schema, alternative, assert, assertion
    and selector declarations, checking if the value is conforming to the specification. In
    case the attribute is missing or for wrong attribute values defaults to ''.
    """
    try:
        value = validator.elem.attrib['xpathDefaultNamespace']
    except KeyError:
        return ''

    value = value.strip()
    if value == '##local':
        return ''
    elif value == '##defaultNamespace':
        return validator.default_namespace
    elif value == '##targetNamespace':
        return validator.target_namespace
    elif len(value.split()) == 1:
        return value
    else:
        admitted_values = ('##defaultNamespace', '##targetNamespace', '##local')
        msg = _("wrong value {0!r} for 'xpathDefaultNamespace' "
                "attribute, can be (anyURI | {1}).")
        validator.parse_error(msg.format(value, ' | '.join(admitted_values)))
        return ''


def parse_target_namespace(validator: Union[SchemaType, 'XsdComponent']) -> str:
    """
    XSD 1.1 targetNamespace attribute in schema, elements and attributes declarations.
    """
    try:
        target_namespace = validator.elem.attrib['targetNamespace'].strip()
    except KeyError:
        return ''

    if target_namespace == nm.XMLNS_NAMESPACE:
        # https://www.w3.org/TR/xmlschema11-1/#sec-nss-special
        msg = _(f"The namespace {nm.XMLNS_NAMESPACE} cannot be used as 'targetNamespace'")
        raise XMLSchemaValueError(msg)
    elif not target_namespace and validator.elem.tag == nm.XSD_SCHEMA:
        # https://www.w3.org/TR/2004/REC-xmlschema-1-20041028/structures.html#element-schema
        msg = _("the attribute 'targetNamespace' cannot be an empty string")
        validator.parse_error(msg)

    return target_namespace


#
# XSD built-in types validator functions

def decimal_validator(value: Union[Decimal, int, float, str]) -> None:
    try:
        if not isinstance(value, (Decimal, float)):
            datatypes.DecimalProxy.validate(value)
        elif isinf(value) or isnan(value):
            raise ValueError()
    except (ValueError, TypeError):
        raise XMLSchemaValidationError(decimal_validator, value,
                                       _("value is not a valid xs:decimal")) from None


def qname_validator(value: str) -> None:
    if datatypes.QName.pattern.match(value) is None:
        raise XMLSchemaValidationError(qname_validator, value,
                                       _("value is not an xs:QName"))


def byte_validator(value: int) -> None:
    if not (-2**7 <= value < 2 ** 7):
        raise XMLSchemaValidationError(int_validator, value,
                                       _("value must be {:s}").format("-128 <= x < 128"))


def short_validator(value: int) -> None:
    if not (-2**15 <= value < 2 ** 15):
        raise XMLSchemaValidationError(short_validator, value,
                                       _("value must be {:s}").format("-2^15 <= x < 2^15"))


def int_validator(value: int) -> None:
    if not (-2**31 <= value < 2 ** 31):
        raise XMLSchemaValidationError(int_validator, value,
                                       _("value must be {:s}").format("-2^31 <= x < 2^31"))


def long_validator(value: int) -> None:
    if not (-2**63 <= value < 2 ** 63):
        raise XMLSchemaValidationError(long_validator, value,
                                       _("value must be {:s}").format("-2^63 <= x < 2^63"))


def unsigned_byte_validator(value: int) -> None:
    if not (0 <= value < 2 ** 8):
        raise XMLSchemaValidationError(unsigned_byte_validator, value,
                                       _("value must be {:s}").format("0 <= x < 256"))


def unsigned_short_validator(value: int) -> None:
    if not (0 <= value < 2 ** 16):
        raise XMLSchemaValidationError(unsigned_short_validator, value,
                                       _("value must be {:s}").format("0 <= x < 2^16"))


def unsigned_int_validator(value: int) -> None:
    if not (0 <= value < 2 ** 32):
        raise XMLSchemaValidationError(unsigned_int_validator, value,
                                       _("value must be {:s}").format("0 <= x < 2^32"))


def unsigned_long_validator(value: int) -> None:
    if not (0 <= value < 2 ** 64):
        raise XMLSchemaValidationError(unsigned_long_validator, value,
                                       _("value must be {:s}").format("0 <= x < 2^64"))


def negative_int_validator(value: int) -> None:
    if value >= 0:
        raise XMLSchemaValidationError(negative_int_validator, value,
                                       _("value must be negative"))


def positive_int_validator(value: int) -> None:
    if value <= 0:
        raise XMLSchemaValidationError(positive_int_validator, value,
                                       _("value must be positive"))


def non_positive_int_validator(value: int) -> None:
    if value > 0:
        raise XMLSchemaValidationError(non_positive_int_validator, value,
                                       _("value must be non positive"))


def non_negative_int_validator(value: int) -> None:
    if value < 0:
        raise XMLSchemaValidationError(non_negative_int_validator, value,
                                       _("value must be non negative"))


def hex_binary_validator(value: Union[str, datatypes.HexBinary]) -> None:
    if not isinstance(value, datatypes.HexBinary) and \
            datatypes.HexBinary.pattern.match(value) is None:
        raise XMLSchemaValidationError(hex_binary_validator, value,
                                       _("not an hexadecimal number"))


def base64_binary_validator(value: Union[str, datatypes.Base64Binary]) -> None:
    if isinstance(value, datatypes.Base64Binary):
        return
    value = value.replace(' ', '')
    if not value:
        return

    match = datatypes.Base64Binary.pattern.match(value)
    if match is None or match.group(0) != value:
        raise XMLSchemaValidationError(base64_binary_validator, value,
                                       _("not a base64 encoding"))


def error_type_validator(value: object) -> None:
    raise XMLSchemaValidationError(error_type_validator, value,
                                   _("no value is allowed for xs:error type"))


#
# XSD builtin decoding functions

def boolean_to_python(value: str) -> bool:
    try:
        return XSD_BOOLEAN_MAP[value]
    except KeyError:
        raise XMLSchemaValueError(_('{!r} is not a boolean value').format(value))


def python_to_boolean(value: object) -> str:
    if isinstance(value, str):
        if value in XSD_BOOLEAN_MAP:
            return value
        raise XMLSchemaValueError(_('{!r} is not a boolean value').format(value))
    return str(value).lower()


def python_to_float(value: Union[SupportsFloat, str]) -> str:
    if isinstance(value, str):
        if value in ('NaN', 'INF', '-INF'):
            return value
        return str(float(value))
    elif isnan(value):
        return "NaN"
    if value == float("inf"):
        return "INF"
    if value == float("-inf"):
        return "-INF"
    return str(value)


def python_to_int(value: Union[SupportsInt, str]) -> str:
    return str(int(value))


#
# Adapters for Python standard library native types used in encoding.
#
# The library's own elementpath datatypes (AbstractDateTime/Duration/AbstractBinary
# subclasses) are already part of the builtin 'instance_types', so they keep their
# existing encode path. These adapters only bridge the parallel standard library
# classes (datetime/date/time/timedelta and bytes-like objects) that inbound post
# processing or other code may place directly into the data handed to encoding.

# Number of days assumed for one month when a timedelta (which has no calendar
# notion) has to be expressed as an xs:yearMonthDuration.
_DAYS_PER_MONTH = 30


def _to_xsd_timezone(tz: tzinfo) -> datatypes.Timezone:
    """
    Normalize a standard library tzinfo to an elementpath Timezone.

    XSD timezone offsets are restricted to whole minutes in the range [-14:00,
    +14:00]. A sub-minute remainder of a stdlib offset cannot be represented, so
    it is truncated toward zero (the wall-clock fields are preserved rather than
    shifting the instant). Offsets outside the XSD range raise ValueError, which
    the encode path reports through the standard encode error contract.
    """
    offset = tz.utcoffset(None)
    if offset is None:
        raise ValueError(_("timezone provides no UTC offset"))

    total_minutes = offset.days * 24 * 60 + offset.seconds // 60
    return datatypes.Timezone(timedelta(
        hours=total_minutes // 60, minutes=total_minutes % 60
    ))


def native_datetime_to_xsd(obj: Union[datetime, date, time],
                           datatype: type,
                           xsd_name: str) -> Any:
    """
    Convert a standard library datetime/date/time object into the elementpath
    datatype instance expected by the target builtin type.

    Returns None when the native object has no natural representation for the
    target type (e.g. a date for xs:time), so the caller reports a regular encode
    error instead of forcing a lossy or ambiguous conversion.
    """
    if xsd_name in (nm.XSD_DATETIME, nm.XSD_DATE_TIME_STAMP):
        if isinstance(obj, datetime):
            tz = _to_xsd_timezone(obj.tzinfo) if obj.tzinfo is not None else None
            return datatype(obj.year, obj.month, obj.day, obj.hour, obj.minute,
                            obj.second, obj.microsecond, tz)
        return None

    if xsd_name == nm.XSD_DATE:
        if isinstance(obj, date):
            tz = _to_xsd_timezone(obj.tzinfo) if isinstance(obj, datetime) \
                and obj.tzinfo is not None else None
            return datatype(obj.year, obj.month, obj.day, tz)
        return None

    if xsd_name == nm.XSD_TIME:
        if isinstance(obj, time):
            tz = _to_xsd_timezone(obj.tzinfo) if obj.tzinfo is not None else None
            return datatype(obj.hour, obj.minute, obj.second, obj.microsecond, tz)
        return None

    return None


def native_timedelta_to_xsd(obj: timedelta,
                            datatype: type,
                            xsd_name: str) -> Any:
    """
    Convert a standard library datetime.timedelta into an XSD duration value.

    A timedelta is an exact day/hour/minute/second/microsecond span, so it maps
    losslessly to xs:duration / xs:dayTimeDuration (months always 0). For
    xs:yearMonthDuration, which can only hold whole months, the span is converted
    using a 30-day month and rounded half-away-from-zero to the nearest whole
    month; this is inherently lossy and documented as such.
    """
    if xsd_name == nm.XSD_YEAR_MONTH_DURATION:
        # Work on whole 30-day units with integer arithmetic to avoid float drift.
        total_days = obj.days
        sign = -1 if total_days < 0 else 1
        months = (abs(total_days) + _DAYS_PER_MONTH // 2) // _DAYS_PER_MONTH
        return datatype(months=sign * months)

    # xs:duration and xs:dayTimeDuration both accept a day/time (seconds) component.
    day_time = datatypes.DayTimeDuration.fromtimedelta(obj)
    if xsd_name == nm.XSD_DAY_TIME_DURATION:
        return datatype(seconds=day_time.seconds)
    return datatype(months=0, seconds=day_time.seconds)


def native_binary_to_xsd(obj: Union[bytes, bytearray, memoryview],
                         datatype: type) -> Any:
    """
    Encode a standard library bytes-like object as the lexical value of the
    target xs:hexBinary / xs:base64Binary type and wrap it in the matching
    elementpath datatype, so later facet validation sees a proper binary value.
    """
    raw = bytes(obj)
    return datatype(datatype.encoder(raw))

