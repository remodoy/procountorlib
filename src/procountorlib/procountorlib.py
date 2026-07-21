import base64
import enum
import json
import random
import string
import typing
from abc import abstractmethod
from datetime import datetime, timedelta, date, UTC, timezone
from decimal import Decimal
from typing import Dict, ByteString, List, Optional
from enum import Enum
from urllib.parse import urlparse, urlunparse, urlencode

import simplejson
import requests
from requests.adapters import HTTPAdapter, Retry
import logging


logger = logging.getLogger("ProcountorAPI")


KNOWN_PROCOUNTOR_ERRORS = {
    "CLOSED_FISCAL_PERIOD": {
        "/api/invoices": "Procountor rejected invoice, fiscal period is closed."
    },
    "Forbidden": {
        "/api/fiscalyears": "Permission denied while creating new purchase invoice, please check API user permissions. "
        "All rights for 'New purchase invoice' and view rights for 'Basic company info' and "
        "'Basic accounting info'.",
        "/api/invoices": "Permission denied while creating new purchase invoice, please check API user permissions. "
        "All rights for 'New purchase invoice' and view rights for 'Basic company info' and "
        "'Basic accounting info'.",
    },
}


VAT_STATUS_DOMESTIC = 1
VAT_STATUS_NO_HANDLING = 12


class BankReferenceCodeType(Enum):
    RF = "RF"
    FI = "FI"
    OCR = "OCR"
    KID = "KID"
    GIK01 = "GIK01"
    GIK04 = "GIK04"
    GIK15 = "GIK15"
    FIK71 = "FIK71"
    FIK73 = "FIK73"
    FIK75 = "FIK75"


class Unit(Enum):
    CM = "CM"
    LOT = ("LOT",)
    GRAM = "GRAM"
    HOUR = "HOUR"
    PERSON = "PERSON"
    LINEAR_METER = "LINEAR_METER"
    KILOGRAM = "KILOGRAM"
    MONTH = "MONTH"
    KILOMETER = "KILOMETER"
    PIECE = "PIECE"
    KILOWATT_HOUR = "KILOWATT_HOUR"
    LITER = "LITER"
    BOX = "BOX"
    METER = "METER"
    SQUARE_METER = "SQUARE_METER"
    CUBIC_METER = "CUBIC_METER"
    SALE_UNIT = "SALE_UNIT"
    MINUTE = "MINUTE"
    MILLIMETER = "MILLIMETER"
    PARCEL = "PARCEL"
    BOTTLE = "BOTTLE"
    CAN = "CAN"
    BAG = "BAG"
    DAY = "DAY"
    ROLL = "ROLL"
    PAGE = "PAGE"
    SACK = "SACK"
    SERIES = "SERIES"
    TUBE = "TUBE"
    TON = "TON"
    YEAR = "YEAR"
    WEEK = "WEEK"
    FULL_DAY = "FULL_DAY"
    KILOBIT = "KILOBIT"
    MEGABIT = "MEGABIT"
    GIGABIT = "GIGABIT"
    TERABIT = "TERABIT"
    SQUARE_CENTIMETRE = "SQUARE_CENTIMETRE"
    CENTILITRE = "CENTILITRE"
    CUP = "CUP"
    DECILITRE = "DECILITRE"
    GALLON_UK = "GALLON_UK"
    GALLON_US = "GALLON_US"
    MILLILITRE = "MILLILITRE"
    PINT_UK = "PINT_UK"
    PINT_US = "PINT_US"
    AMPERE = "AMPERE"
    AMPERE_HOUR = "AMPERE_HOUR"
    AMPERE_MINUTE = "AMPERE_MINUTE"
    KILOAMPERE_HOUR = "KILOAMPERE_HOUR"
    KILOVOLT = "KILOVOLT"
    MILLIVOLT = "MILLIVOLT"
    MILLIAMPERE_HOUR = "MILLIAMPERE_HOUR"
    FOOT = "FOOT"
    INCH = "INCH"
    MILE = "MILE"
    YARD = "YARD"
    EXAJOULE = "EXAJOULE"
    GIGAJOULE = "GIGAJOULE"
    JOULE = "JOULE"
    JOULE_PER_SECOND = "JOULE_PER_SECOND"
    KILOJOULE = "KILOJOULE"
    MILLIJOULE = "MILLIJOULE"
    PETAJOULE = "PETAJOULE"
    TERAJOULE = "TERAJOULE"
    GRAM_PER_CUBIC_METRE = "GRAM_PER_CUBIC_METRE"
    GRAM_PER_SQUARE_METRE = "GRAM_PER_SQUARE_METRE"
    KILOGRAM_PER_CUBIC_METRE = "KILOGRAM_PER_CUBIC_METRE"
    KILOGRAM_PER_SQUARE_METRE = "KILOGRAM_PER_SQUARE_METRE"
    MILLIGRAM = "MILLIGRAM"
    MILLIGRAM_PER_CUBIC_METRE = "MILLIGRAM_PER_CUBIC_METRE"
    OUNCE = "OUNCE"
    POUND = "POUND"
    STONE_UK = "STONE_UK"
    DOZEN = "DOZEN"
    DOZEN_PACK = "DOZEN_PACK"
    EIGHT_PACK = "EIGHT_PACK"
    FIVE_PACK = "FIVE_PACK"
    FOUR_PACK = "FOUR_PACK"
    HUNDRED = "HUNDRED"
    JAR = "JAR"
    NINE_PACK = "NINE_PACK"
    NUMBER_OF_WORDS = "NUMBER_OF_WORDS"
    PAIR = "PAIR"
    PALLET = "PALLET"
    PLATE = "PLATE"
    SET = "SET"
    SEVEN_PACK = "SEVEN_PACK"
    SIX_PACK = "SIX_PACK"
    TEN_PACK = "TEN_PACK"
    THREE_PACK = "THREE_PACK"
    TWO_PACK = "TWO_PACK"
    WRAP = "WRAP"
    GIGAWATT = "GIGAWATT"
    GIGAWATT_HOUR = "GIGAWATT_HOUR"
    KILOWATT = "KILOWATT"
    MEGAWATT_HOUR = "MEGAWATT_HOUR"
    MILLIWATT = "MILLIWATT"
    TERAWATT = "TERAWATT"
    TERAWATT_HOUR = "TERAWATT_HOUR"
    WATT = "WATT"
    WATT_HOUR = "WATT_HOUR"
    BAR = "BAR"
    KILOPASCAL = "KILOPASCAL"
    PASCAL = "PASCAL"
    KILOBYTE = "KILOBYTE"
    MEGABYTE = "MEGABYTE"
    GIGABYTE = "GIGABYTE"
    SECOND = "SECOND"
    HECTARE = "HECTARE"
    NO_UNIT = "NO_UNIT"


class InvoiceChannel(Enum):
    EMAIL = "EMAIL"
    MAIL = "MAIL"
    ELECTRONIC_INVOICE = "ELECTRONIC_INVOICE"
    EDIFACT = "EDIFACT"
    PAPER_INVOICE = "PAPER_INVOICE"
    NO_SENDING = "NO_SENDING"


class AttachmentReferenceType(Enum):
    INVOICE = "INVOICE"
    LEDGERRECEIPT = "LEDGERRECEIPT"
    BANKSTATEMENTEVENT = "BANKSTATEMENTEVENT"
    SALES_PRODUCT_REGISTER = "SALES_PRODUCT_REGISTER"
    PURCHASE_PRODUCT_REGISTER = "PURCHASE_PRODUCT_REGISTER"
    CUSTOMER_BUSINESS_PARTNER_REGISTER = "CUSTOMER_BUSINESS_PARTNER_REGISTER"
    SUPPLIER_BUSINESS_PARTNER_REGISTER = "SUPPLIER_BUSINESS_PARTNER_REGISTER"
    PERSON_BUSINESS_PARTNER_REGISTER = "PERSON_BUSINESS_PARTNER_REGISTER"
    EMPLOYEE_INFO = "EMPLOYEE_INFO"
    ENVIRONMENT = "ENVIRONMENT"
    FINANCIAL_STATEMENT = "FINANCIAL_STATEMENT"
    NETS_COLLECTION = "NETS_COLLECTION"
    REFERENCE_PAYMENT = "REFERENCE_PAYMENT"
    INVOICEDRAFT_ITEM = "INVOICEDRAFT_ITEM"
    COST_RECEIPT = "COST_RECEIPT"


class PaymentMethod(Enum):
    BANK_TRANSFER = "BANK_TRANSFER"
    DIRECT_DEBIT = "DIRECT_DEBIT"
    DIRECT_PAYMENT = "DIRECT_PAYMENT"
    CLEARING = "CLEARING"
    CREDIT_CARD_CHARGE = "CREDIT_CARD_CHARGE"
    FOREIGN_PAYMENT = "FOREIGN_PAYMENT"
    OTHER = "OTHER"
    CASH = "CASH"
    DOMESTIC_PAYMENT_PLUSGIRO = "DOMESTIC_PAYMENT_PLUSGIRO"
    DOMESTIC_PAYMENT_BANKGIRO = "DOMESTIC_PAYMENT_BANKGIRO"
    DOMESTIC_PAYMENT_CREDITOR = "DOMESTIC_PAYMENT_CREDITOR"
    DKLMPKRE = "DKLMPKRE"
    NETS = "NETS"


class Country(Enum):
    AFGHANISTAN = "AFGHANISTAN"
    ALBANIA = "ALBANIA"
    ALGERIA = "ALGERIA"
    AMERICAN_SAMOA = "AMERICAN_SAMOA"
    ANDORRA = "ANDORRA"
    ANGOLA = "ANGOLA"
    ANGUILLA = "ANGUILLA"
    ANTARCTICA = "ANTARCTICA"
    ANTIGUA_AND_BARBUDA = "ANTIGUA_AND_BARBUDA"
    ARGENTINA = "ARGENTINA"
    ARMENIA = "ARMENIA"
    ARUBA = "ARUBA"
    AUSTRALIA = "AUSTRALIA"
    AUSTRIA = "AUSTRIA"
    AZERBAIJAN = "AZERBAIJAN"
    BAHAMAS = "BAHAMAS"
    BAHRAIN = "BAHRAIN"
    BANGLADESH = "BANGLADESH"
    BARBADOS = "BARBADOS"
    BELARUS = "BELARUS"
    BELGIUM = "BELGIUM"
    BELIZE = "BELIZE"
    BENIN = "BENIN"
    BERMUDA = "BERMUDA"
    BHUTAN = "BHUTAN"
    PLURINATIONAL_STATE_OF_BOLIVIA = "PLURINATIONAL_STATE_OF_BOLIVIA"
    SINT_EUSTATIUS_AND_SABA_BONAIRE = "SINT_EUSTATIUS_AND_SABA_BONAIRE"
    BOSNIA_AND_HERZEGOVINA = "BOSNIA_AND_HERZEGOVINA"
    BOTSWANA = "BOTSWANA"
    BOUVET_ISLAND = "BOUVET_ISLAND"
    BRAZIL = "BRAZIL"
    BRITISH_INDIAN_OCEAN_TERRITORY = "BRITISH_INDIAN_OCEAN_TERRITORY"
    BRUNEI_DARUSSALAM = "BRUNEI_DARUSSALAM"
    BULGARIA = "BULGARIA"
    BURKINA_FASO = "BURKINA_FASO"
    BURUNDI = "BURUNDI"
    CABO_VERDE = "CABO_VERDE"
    CAMBODIA = "CAMBODIA"
    CAMEROON = "CAMEROON"
    CANADA = "CANADA"
    CAYMAN_ISLANDS = "CAYMAN_ISLANDS"
    CENTRAL_AFRICAN_REPUBLIC = "CENTRAL_AFRICAN_REPUBLIC"
    CHAD = "CHAD"
    CHILE = "CHILE"
    CHINA = "CHINA"
    CHRISTMAS_ISLAND = "CHRISTMAS_ISLAND"
    COCOS_KEELING_ISLANDS = "COCOS_KEELING_ISLANDS"
    COLOMBIA = "COLOMBIA"
    COMOROS = "COMOROS"
    CONGO = "CONGO"
    THE_DEMOCRATIC_REPUBLIC_OF_THE_CONGO = "THE_DEMOCRATIC_REPUBLIC_OF_THE_CONGO"
    COOK_ISLANDS = "COOK_ISLANDS"
    COSTA_RICA = "COSTA_RICA"
    CROATIA = "CROATIA"
    CUBA = "CUBA"
    CURACAO = "CURACAO"
    CYPRUS = "CYPRUS"
    CZECH_REPUBLIC = "CZECH_REPUBLIC"
    COTE_D_IVOIRE = "COTE_D_IVOIRE"
    DENMARK = "DENMARK"
    DJIBOUTI = "DJIBOUTI"
    DOMINICA = "DOMINICA"
    DOMINICAN_REPUBLIC = "DOMINICAN_REPUBLIC"
    ECUADOR = "ECUADOR"
    EGYPT = "EGYPT"
    EL_SALVADOR = "EL_SALVADOR"
    EQUATORIAL_GUINEA = "EQUATORIAL_GUINEA"
    ERITREA = "ERITREA"
    ESTONIA = "ESTONIA"
    ETHIOPIA = "ETHIOPIA"
    FALKLAND_ISLANDS_MALVINAS = "FALKLAND_ISLANDS_MALVINAS"
    FAROE_ISLANDS = "FAROE_ISLANDS"
    FIJI = "FIJI"
    FINLAND = "FINLAND"
    FRANCE = "FRANCE"
    FRENCH_GUIANA = "FRENCH_GUIANA"
    FRENCH_POLYNESIA = "FRENCH_POLYNESIA"
    FRENCH_SOUTHERN_TERRITORIES = "FRENCH_SOUTHERN_TERRITORIES"
    GABON = "GABON"
    GAMBIA = "GAMBIA"
    GEORGIA = "GEORGIA"
    GERMANY = "GERMANY"
    GHANA = "GHANA"
    GIBRALTAR = "GIBRALTAR"
    GREECE = "GREECE"
    GREENLAND = "GREENLAND"
    GRENADA = "GRENADA"
    GUADELOUPE = "GUADELOUPE"
    GUAM = "GUAM"
    GUATEMALA = "GUATEMALA"
    GUERNSEY = "GUERNSEY"
    GUINEA = "GUINEA"
    GUINEA_BISSAU = "GUINEA_BISSAU"
    GUYANA = "GUYANA"
    HAITI = "HAITI"
    HEARD_ISLAND_AND_MCDONALD_ISLANDS = "HEARD_ISLAND_AND_MCDONALD_ISLANDS"
    HOLY_SEE_VATICAN_CITY_STATE = "HOLY_SEE_VATICAN_CITY_STATE"
    HONDURAS = "HONDURAS"
    HONG_KONG = "HONG_KONG"
    HUNGARY = "HUNGARY"
    ICELAND = "ICELAND"
    INDIA = "INDIA"
    INDONESIA = "INDONESIA"
    ISLAMIC_REPUBLIC_OF_IRAN = "ISLAMIC_REPUBLIC_OF_IRAN"
    IRAQ = "IRAQ"
    IRELAND = "IRELAND"
    ISLE_OF_MAN = "ISLE_OF_MAN"
    ISRAEL = "ISRAEL"
    ITALY = "ITALY"
    JAMAICA = "JAMAICA"
    JAPAN = "JAPAN"
    JERSEY = "JERSEY"
    JORDAN = "JORDAN"
    KAZAKHSTAN = "KAZAKHSTAN"
    KENYA = "KENYA"
    KIRIBATI = "KIRIBATI"
    DEMOCRATIC_PEOPLE_S_REPUBLIC_OF_KOREA = "DEMOCRATIC_PEOPLE_S_REPUBLIC_OF_KOREA"
    REPUBLIC_OF_KOREA = "REPUBLIC_OF_KOREA"
    KOSOVO_TEMPORARY = "KOSOVO_TEMPORARY"
    KUWAIT = "KUWAIT"
    KYRGYZSTAN = "KYRGYZSTAN"
    LAO_PEOPLE_S_DEMOCRATIC_REPUBLIC = "LAO_PEOPLE_S_DEMOCRATIC_REPUBLIC"
    LATVIA = "LATVIA"
    LEBANON = "LEBANON"
    LESOTHO = "LESOTHO"
    LIBERIA = "LIBERIA"
    LIBYA = "LIBYA"
    LIECHTENSTEIN = "LIECHTENSTEIN"
    LITHUANIA = "LITHUANIA"
    LUXEMBOURG = "LUXEMBOURG"
    MACAO = "MACAO"
    THE_FORMER_YUGOSLAV_REPUBLIC_OF_MACEDONIA = (
        "THE_FORMER_YUGOSLAV_REPUBLIC_OF_MACEDONIA"
    )
    MADAGASCAR = "MADAGASCAR"
    MALAWI = "MALAWI"
    MALAYSIA = "MALAYSIA"
    MALDIVES = "MALDIVES"
    MALI = "MALI"
    MALTA = "MALTA"
    MARSHALL_ISLANDS = "MARSHALL_ISLANDS"
    MARTINIQUE = "MARTINIQUE"
    MAURITANIA = "MAURITANIA"
    MAURITIUS = "MAURITIUS"
    MAYOTTE = "MAYOTTE"
    MEXICO = "MEXICO"
    FEDERATED_STATES_OF_MICRONESIA = "FEDERATED_STATES_OF_MICRONESIA"
    REPUBLIC_OF_MOLDOVA = "REPUBLIC_OF_MOLDOVA"
    MONACO = "MONACO"
    MONGOLIA = "MONGOLIA"
    MONTENEGRO = "MONTENEGRO"
    MONTSERRAT = "MONTSERRAT"
    MOROCCO = "MOROCCO"
    MOZAMBIQUE = "MOZAMBIQUE"
    MYANMAR = "MYANMAR"
    NAMIBIA = "NAMIBIA"
    NAURU = "NAURU"
    NEPAL = "NEPAL"
    NETHERLANDS = "NETHERLANDS"
    NEW_CALEDONIA = "NEW_CALEDONIA"
    NEW_ZEALAND = "NEW_ZEALAND"
    NICARAGUA = "NICARAGUA"
    NIGER = "NIGER"
    NIGERIA = "NIGERIA"
    NIUE = "NIUE"
    NORFOLK_ISLAND = "NORFOLK_ISLAND"
    NORTHERN_IRELAND_TEMPORARY = "NORTHERN_IRELAND_TEMPORARY"
    NORTHERN_MARIANA_ISLANDS = "NORTHERN_MARIANA_ISLANDS"
    NORWAY = "NORWAY"
    OMAN = "OMAN"
    PAKISTAN = "PAKISTAN"
    PALAU = "PALAU"
    STATE_OF_PALESTINE = "STATE_OF_PALESTINE"
    PANAMA = "PANAMA"
    PAPUA_NEW_GUINEA = "PAPUA_NEW_GUINEA"
    PARAGUAY = "PARAGUAY"
    PERU = "PERU"
    PHILIPPINES = "PHILIPPINES"
    PITCAIRN = "PITCAIRN"
    POLAND = "POLAND"
    PORTUGAL = "PORTUGAL"
    PUERTO_RICO = "PUERTO_RICO"
    QATAR = "QATAR"
    ROMANIA = "ROMANIA"
    RUSSIAN_FEDERATION = "RUSSIAN_FEDERATION"
    RWANDA = "RWANDA"
    REUNION = "REUNION"
    SAINT_BARTHELEMY = "SAINT_BARTHELEMY"
    ASCENSION_AND_TRISTAN_DA_CUNHA_SAINT_HELENA = (
        "ASCENSION_AND_TRISTAN_DA_CUNHA_SAINT_HELENA"
    )
    SAINT_KITTS_AND_NEVIS = "SAINT_KITTS_AND_NEVIS"
    SAINT_LUCIA = "SAINT_LUCIA"
    SAINT_MARTIN_FRENCH_PART = "SAINT_MARTIN_FRENCH_PART"
    SAINT_PIERRE_AND_MIQUELON = "SAINT_PIERRE_AND_MIQUELON"
    SAINT_VINCENT_AND_THE_GRENADINES = "SAINT_VINCENT_AND_THE_GRENADINES"
    SAMOA = "SAMOA"
    SAN_MARINO = "SAN_MARINO"
    SAO_TOME_AND_PRINCIPE = "SAO_TOME_AND_PRINCIPE"
    SAUDI_ARABIA = "SAUDI_ARABIA"
    SENEGAL = "SENEGAL"
    SERBIA = "SERBIA"
    SEYCHELLES = "SEYCHELLES"
    SIERRA_LEONE = "SIERRA_LEONE"
    SINGAPORE = "SINGAPORE"
    SINT_MAARTEN_DUTCH_PART = "SINT_MAARTEN_DUTCH_PART"
    SLOVAKIA = "SLOVAKIA"
    SLOVENIA = "SLOVENIA"
    SOLOMON_ISLANDS = "SOLOMON_ISLANDS"
    SOMALIA = "SOMALIA"
    SOUTH_AFRICA = "SOUTH_AFRICA"
    SOUTH_GEORGIA_AND_THE_SOUTH_SANDWICH_ISLANDS = (
        "SOUTH_GEORGIA_AND_THE_SOUTH_SANDWICH_ISLANDS"
    )
    SOUTH_SUDAN = "SOUTH_SUDAN"
    SPAIN = "SPAIN"
    SRI_LANKA = "SRI_LANKA"
    SUDAN = "SUDAN"
    SURINAME = "SURINAME"
    SVALBARD_AND_JAN_MAYEN = "SVALBARD_AND_JAN_MAYEN"
    SWAZILAND = "SWAZILAND"
    SWEDEN = "SWEDEN"
    SWITZERLAND = "SWITZERLAND"
    SYRIAN_ARAB_REPUBLIC = "SYRIAN_ARAB_REPUBLIC"
    PROVINCE_OF_CHINA_TAIWAN = "PROVINCE_OF_CHINA_TAIWAN"
    TAJIKISTAN = "TAJIKISTAN"
    UNITED_REPUBLIC_OF_TANZANIA = "UNITED_REPUBLIC_OF_TANZANIA"
    THAILAND = "THAILAND"
    TIMOR_LESTE = "TIMOR_LESTE"
    TOGO = "TOGO"
    TOKELAU = "TOKELAU"
    TONGA = "TONGA"
    TRINIDAD_AND_TOBAGO = "TRINIDAD_AND_TOBAGO"
    TUNISIA = "TUNISIA"
    TURKEY = "TURKEY"
    TURKMENISTAN = "TURKMENISTAN"
    TURKS_AND_CAICOS_ISLANDS = "TURKS_AND_CAICOS_ISLANDS"
    TUVALU = "TUVALU"
    UGANDA = "UGANDA"
    UKRAINE = "UKRAINE"
    UNITED_ARAB_EMIRATES = "UNITED_ARAB_EMIRATES"
    UNITED_KINGDOM_OF_GREAT_BRITAIN_AND_NORTHERN_IRELAND = (
        "UNITED_KINGDOM_OF_GREAT_BRITAIN_AND_NORTHERN_IRELAND"
    )
    UNITED_STATES_MINOR_OUTLYING_ISLANDS = "UNITED_STATES_MINOR_OUTLYING_ISLANDS"
    UNITED_STATES_OF_AMERICA = "UNITED_STATES_OF_AMERICA"
    URUGUAY = "URUGUAY"
    UZBEKISTAN = "UZBEKISTAN"
    VANUATU = "VANUATU"
    BOLIVARIAN_REPUBLIC_OF_VENEZUELA = "BOLIVARIAN_REPUBLIC_OF_VENEZUELA"
    VIET_NAM = "VIET_NAM"
    BRITISH_VIRGIN_ISLANDS = "BRITISH_VIRGIN_ISLANDS"
    U_S_VIRGIN_ISLANDS = "U_S_VIRGIN_ISLANDS"
    WALLIS_AND_FUTUNA = "WALLIS_AND_FUTUNA"
    WESTERN_SAHARA = "WESTERN_SAHARA"
    YEMEN = "YEMEN"
    ZAMBIA = "ZAMBIA"
    ZIMBABWE = "ZIMBABWE"
    ALAND_ISLANDS = "ALAND_ISLANDS"


class CountryCodes(Enum):
    """
    Country codes to Procountor Country
    """

    AF = Country.AFGHANISTAN
    AL = Country.ALBANIA
    DZ = Country.ALGERIA
    AS = Country.AMERICAN_SAMOA
    AD = Country.ANDORRA
    AO = Country.ANGOLA
    AI = Country.ANGUILLA
    AQ = Country.ANTARCTICA
    AG = Country.ANTIGUA_AND_BARBUDA
    AR = Country.ARGENTINA
    AM = Country.ARMENIA
    AW = Country.ARUBA
    AU = Country.AUSTRALIA
    AT = Country.AUSTRIA
    AZ = Country.AZERBAIJAN
    BS = Country.BAHAMAS
    BH = Country.BAHRAIN
    BD = Country.BANGLADESH
    BB = Country.BARBADOS
    BY = Country.BELARUS
    BE = Country.BELGIUM
    BZ = Country.BELIZE
    BJ = Country.BENIN
    BM = Country.BERMUDA
    BT = Country.BHUTAN
    BO = Country.PLURINATIONAL_STATE_OF_BOLIVIA
    BQ = Country.SINT_EUSTATIUS_AND_SABA_BONAIRE
    BA = Country.BOSNIA_AND_HERZEGOVINA
    BW = Country.BOTSWANA
    BV = Country.BOUVET_ISLAND
    BR = Country.BRAZIL
    IO = Country.BRITISH_INDIAN_OCEAN_TERRITORY
    BN = Country.BRUNEI_DARUSSALAM
    BG = Country.BULGARIA
    BF = Country.BURKINA_FASO
    BI = Country.BURUNDI
    CV = Country.CABO_VERDE
    KH = Country.CAMBODIA
    CM = Country.CAMEROON
    CA = Country.CANADA
    KY = Country.CAYMAN_ISLANDS
    CF = Country.CENTRAL_AFRICAN_REPUBLIC
    TD = Country.CHAD
    CL = Country.CHILE
    CN = Country.CHINA
    CX = Country.CHRISTMAS_ISLAND
    CC = Country.COCOS_KEELING_ISLANDS
    CO = Country.COLOMBIA
    KM = Country.COMOROS
    CD = Country.CONGO
    CG = Country.THE_DEMOCRATIC_REPUBLIC_OF_THE_CONGO
    CK = Country.COOK_ISLANDS
    CR = Country.COSTA_RICA
    HR = Country.CROATIA
    CU = Country.CUBA
    CW = Country.CURACAO
    CY = Country.CYPRUS
    CZ = Country.CZECH_REPUBLIC
    CI = Country.COTE_D_IVOIRE
    DK = Country.DENMARK
    DJ = Country.DJIBOUTI
    DM = Country.DOMINICA
    DO = Country.DOMINICAN_REPUBLIC
    EC = Country.ECUADOR
    EG = Country.EGYPT
    SV = Country.EL_SALVADOR
    GQ = Country.EQUATORIAL_GUINEA
    ER = Country.ERITREA
    EE = Country.ESTONIA
    ET = Country.ETHIOPIA
    FK = Country.FALKLAND_ISLANDS_MALVINAS
    FO = Country.FAROE_ISLANDS
    FJ = Country.FIJI
    FI = Country.FINLAND
    FR = Country.FRANCE
    GF = Country.FRENCH_GUIANA
    PF = Country.FRENCH_POLYNESIA
    TF = Country.FRENCH_SOUTHERN_TERRITORIES
    GA = Country.GABON
    GM = Country.GAMBIA
    GE = Country.GEORGIA
    DE = Country.GERMANY
    GH = Country.GHANA
    GI = Country.GIBRALTAR
    GR = Country.GREECE
    GL = Country.GREENLAND
    GD = Country.GRENADA
    GP = Country.GUADELOUPE
    GU = Country.GUAM
    GT = Country.GUATEMALA
    GG = Country.GUERNSEY
    GN = Country.GUINEA
    GW = Country.GUINEA_BISSAU
    GY = Country.GUYANA
    HT = Country.HAITI
    HM = Country.HEARD_ISLAND_AND_MCDONALD_ISLANDS
    VA = Country.HOLY_SEE_VATICAN_CITY_STATE
    HN = Country.HONDURAS
    HK = Country.HONG_KONG
    HU = Country.HUNGARY
    IS = Country.ICELAND
    IN = Country.INDIA
    ID = Country.INDONESIA
    IR = Country.ISLAMIC_REPUBLIC_OF_IRAN
    IQ = Country.IRAQ
    IE = Country.IRELAND
    IM = Country.ISLE_OF_MAN
    IL = Country.ISRAEL
    IT = Country.ITALY
    JM = Country.JAMAICA
    JP = Country.JAPAN
    JE = Country.JERSEY
    JO = Country.JORDAN
    KZ = Country.KAZAKHSTAN
    KE = Country.KENYA
    KI = Country.KIRIBATI
    KP = Country.DEMOCRATIC_PEOPLE_S_REPUBLIC_OF_KOREA
    KR = Country.REPUBLIC_OF_KOREA
    XK = Country.KOSOVO_TEMPORARY
    KW = Country.KUWAIT
    KG = Country.KYRGYZSTAN
    LA = Country.LAO_PEOPLE_S_DEMOCRATIC_REPUBLIC
    LV = Country.LATVIA
    LB = Country.LEBANON
    LS = Country.LESOTHO
    LR = Country.LIBERIA
    LY = Country.LIBYA
    LI = Country.LIECHTENSTEIN
    LT = Country.LITHUANIA
    LU = Country.LUXEMBOURG
    MO = Country.MACAO
    MG = Country.MADAGASCAR
    MW = Country.MALAWI
    MY = Country.MALAYSIA
    MV = Country.MALDIVES
    ML = Country.MALI
    MT = Country.MALTA
    MH = Country.MARSHALL_ISLANDS
    MQ = Country.MARTINIQUE
    MR = Country.MAURITANIA
    MU = Country.MAURITIUS
    YT = Country.MAYOTTE
    MX = Country.MEXICO
    FM = Country.FEDERATED_STATES_OF_MICRONESIA
    MD = Country.REPUBLIC_OF_MOLDOVA
    MC = Country.MONACO
    MN = Country.MONGOLIA
    ME = Country.MONTENEGRO
    MS = Country.MONTSERRAT
    MA = Country.MOROCCO
    MZ = Country.MOZAMBIQUE
    MM = Country.MYANMAR
    NA = Country.NAMIBIA
    NR = Country.NAURU
    NP = Country.NEPAL
    NL = Country.NETHERLANDS
    NC = Country.NEW_CALEDONIA
    NZ = Country.NEW_ZEALAND
    NI = Country.NICARAGUA
    NE = Country.NIGER
    NG = Country.NIGERIA
    NU = Country.NIUE
    NF = Country.NORFOLK_ISLAND
    MP = Country.NORTHERN_MARIANA_ISLANDS
    NO = Country.NORWAY
    OM = Country.OMAN
    PK = Country.PAKISTAN
    PW = Country.PALAU
    PS = Country.STATE_OF_PALESTINE
    PA = Country.PANAMA
    PG = Country.PAPUA_NEW_GUINEA
    PY = Country.PARAGUAY
    PE = Country.PERU
    PH = Country.PHILIPPINES
    PN = Country.PITCAIRN
    PL = Country.POLAND
    PT = Country.PORTUGAL
    PR = Country.PUERTO_RICO
    QA = Country.QATAR
    MK = Country.THE_FORMER_YUGOSLAV_REPUBLIC_OF_MACEDONIA
    RO = Country.ROMANIA
    RU = Country.RUSSIAN_FEDERATION
    RW = Country.RWANDA
    RE = Country.REUNION
    BL = Country.SAINT_BARTHELEMY
    SH = Country.ASCENSION_AND_TRISTAN_DA_CUNHA_SAINT_HELENA
    KN = Country.SAINT_KITTS_AND_NEVIS
    LC = Country.SAINT_LUCIA
    MF = Country.SAINT_MARTIN_FRENCH_PART
    PM = Country.SAINT_PIERRE_AND_MIQUELON
    VC = Country.SAINT_VINCENT_AND_THE_GRENADINES
    WS = Country.SAMOA
    SM = Country.SAN_MARINO
    ST = Country.SAO_TOME_AND_PRINCIPE
    SA = Country.SAUDI_ARABIA
    SN = Country.SENEGAL
    RS = Country.SERBIA
    SC = Country.SEYCHELLES
    SL = Country.SIERRA_LEONE
    SG = Country.SINGAPORE
    SX = Country.SINT_MAARTEN_DUTCH_PART
    SK = Country.SLOVAKIA
    SI = Country.SLOVENIA
    SB = Country.SOLOMON_ISLANDS
    SO = Country.SOMALIA
    ZA = Country.SOUTH_AFRICA
    GS = Country.SOUTH_GEORGIA_AND_THE_SOUTH_SANDWICH_ISLANDS
    SS = Country.SOUTH_SUDAN
    ES = Country.SPAIN
    LK = Country.SRI_LANKA
    SD = Country.SUDAN
    SR = Country.SURINAME
    SJ = Country.SVALBARD_AND_JAN_MAYEN
    SW = Country.SWAZILAND
    SE = Country.SWEDEN
    CH = Country.SWITZERLAND
    SY = Country.SYRIAN_ARAB_REPUBLIC
    TW = Country.PROVINCE_OF_CHINA_TAIWAN
    TJ = Country.TAJIKISTAN
    TZ = Country.UNITED_REPUBLIC_OF_TANZANIA
    TH = Country.THAILAND
    TL = Country.TIMOR_LESTE
    TG = Country.TOGO
    TK = Country.TOKELAU
    TO = Country.TONGA
    TT = Country.TRINIDAD_AND_TOBAGO
    TN = Country.TUNISIA
    TR = Country.TURKEY
    TM = Country.TURKMENISTAN
    TC = Country.TURKS_AND_CAICOS_ISLANDS
    TV = Country.TUVALU
    UG = Country.UGANDA
    UA = Country.UKRAINE
    AE = Country.UNITED_ARAB_EMIRATES
    GB = Country.UNITED_KINGDOM_OF_GREAT_BRITAIN_AND_NORTHERN_IRELAND
    UM = Country.UNITED_STATES_MINOR_OUTLYING_ISLANDS
    US = Country.UNITED_STATES_OF_AMERICA
    UY = Country.URUGUAY
    UZ = Country.UZBEKISTAN
    VU = Country.VANUATU
    VE = Country.BOLIVARIAN_REPUBLIC_OF_VENEZUELA
    VN = Country.VIET_NAM
    VG = Country.BRITISH_VIRGIN_ISLANDS
    VI = Country.U_S_VIRGIN_ISLANDS
    WF = Country.WALLIS_AND_FUTUNA
    EH = Country.WESTERN_SAHARA
    YE = Country.YEMEN
    ZM = Country.ZAMBIA
    ZW = Country.ZIMBABWE
    AX = Country.ALAND_ISLANDS


class Currency(Enum):
    AED = "AED"
    AFN = "AFN"
    ALL = "ALL"
    AMD = "AMD"
    ANG = "ANG"
    AOA = "AOA"
    ARS = "ARS"
    AUD = "AUD"
    AWG = "AWG"
    AZN = "AZN"
    BAM = "BAM"
    BBD = "BBD"
    BDT = "BDT"
    BGN = "BGN"
    BHD = "BHD"
    BIF = "BIF"
    BMD = "BMD"
    BND = "BND"
    BOB = "BOB"
    BOV = "BOV"
    BRL = "BRL"
    BSD = "BSD"
    BTN = "BTN"
    BWP = "BWP"
    BYN = "BYN"
    BZD = "BZD"
    CAD = "CAD"
    CDF = "CDF"
    CHE = "CHE"
    CHF = "CHF"
    CHW = "CHW"
    CLF = "CLF"
    CLP = "CLP"
    CNY = "CNY"
    COP = "COP"
    COU = "COU"
    CRC = "CRC"
    CUC = "CUC"
    CUP = "CUP"
    CVE = "CVE"
    CZK = "CZK"
    DJF = "DJF"
    DKK = "DKK"
    DOP = "DOP"
    DZD = "DZD"
    EGP = "EGP"
    ERN = "ERN"
    ETB = "ETB"
    EUR = "EUR"
    FJD = "FJD"
    FKP = "FKP"
    GBP = "GBP"
    GEL = "GEL"
    GHS = "GHS"
    GIP = "GIP"
    GMD = "GMD"
    GNF = "GNF"
    GTQ = "GTQ"
    GYD = "GYD"
    HKD = "HKD"
    HNL = "HNL"
    HRK = "HRK"
    HTG = "HTG"
    HUF = "HUF"
    IDR = "IDR"
    ILS = "ILS"
    INR = "INR"
    IQD = "IQD"
    IRR = "IRR"
    ISK = "ISK"
    JMD = "JMD"
    JOD = "JOD"
    JPY = "JPY"
    KES = "KES"
    KGS = "KGS"
    KHR = "KHR"
    KMF = "KMF"
    KPW = "KPW"
    KRW = "KRW"
    KWD = "KWD"
    KYD = "KYD"
    KZT = "KZT"
    LAK = "LAK"
    LBP = "LBP"
    LKR = "LKR"
    LRD = "LRD"
    LSL = "LSL"
    LYD = "LYD"
    MAD = "MAD"
    MDL = "MDL"
    MGA = "MGA"
    MKD = "MKD"
    MMK = "MMK"
    MNT = "MNT"
    MOP = "MOP"
    MRO = "MRO"
    MUR = "MUR"
    MVR = "MVR"
    MWK = "MWK"
    MXN = "MXN"
    MXV = "MXV"
    MYR = "MYR"
    MZN = "MZN"
    NAD = "NAD"
    NGN = "NGN"
    NIO = "NIO"
    NOK = "NOK"
    NPR = "NPR"
    NZD = "NZD"
    OMR = "OMR"
    PAB = "PAB"
    PEN = "PEN"
    PGK = "PGK"
    PHP = "PHP"
    PKR = "PKR"
    PLN = "PLN"
    PYG = "PYG"
    QAR = "QAR"
    RON = "RON"
    RSD = "RSD"
    RUB = "RUB"
    RWF = "RWF"
    SAR = "SAR"
    SBD = "SBD"
    SCR = "SCR"
    SDG = "SDG"
    SEK = "SEK"
    SGD = "SGD"
    SHP = "SHP"
    SLL = "SLL"
    SOS = "SOS"
    SRD = "SRD"
    SSP = "SSP"
    STN = "STN"
    SVC = "SVC"
    SYP = "SYP"
    SZL = "SZL"
    THB = "THB"
    TJS = "TJS"
    TMT = "TMT"
    TND = "TND"
    TOP = "TOP"
    TRY = "TRY"
    TTD = "TTD"
    TWD = "TWD"
    TZS = "TZS"
    UAH = "UAH"
    UGX = "UGX"
    USD = "USD"
    USN = "USN"
    UYI = "UYI"
    UYU = "UYU"
    UYW = "UYW"
    UZS = "UZS"
    VES = "VES"
    VND = "VND"
    VUV = "VUV"
    WST = "WST"
    XAF = "XAF"
    XAG = "XAG"
    XAU = "XAU"
    XBA = "XBA"
    XBB = "XBB"
    XBC = "XBC"
    XBD = "XBD"
    XCD = "XCD"
    XDR = "XDR"
    XOF = "XOF"
    XPD = "XPD"
    XPF = "XPF"
    XPT = "XPT"
    XSU = "XSU"
    XTS = "XTS"
    XUA = "XUA"
    XXX = "XXX"
    YER = "YER"
    ZAR = "ZAR"
    ZMW = "ZMW"
    ZWL = "ZWL"


class InvoiceType(Enum):
    SALES_INVOICE = "SALES_INVOICE"
    PURCHASE_INVOICE = "PURCHASE_INVOICE"
    TRAVEL_INVOICE = "TRAVEL_INVOICE"
    BILL_OF_CHARGES = "BILL_OF_CHARGES"


class ProductType(Enum):
    SALES = "SALES"
    PURCHASE = "PURCHASE"
    TRAVEL = "TRAVEL"


class InvoiceStatus(Enum):
    EMPTY = "EMPTY"
    UNFINISHED = "UNFINISHED"
    NOT_SENT = "NOT_SENT"
    SENT = "SENT"
    RECEIVED = "RECEIVED"
    PAID = "PAID"
    PAYMENT_DENIED = "PAYMENT_DENIED"
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    INVALIDATED = "INVALIDATED"
    PAYMENT_QUEUED = "PAYMENT_QUEUED"
    PARTLY_PAID = "PARTLY_PAID"
    PAYMENT_SENT_TO_BANK = "PAYMENT_SENT_TO_BANK"
    MARKED_PAID = "MARKED_PAID"
    STARTED = "STARTED"
    INVOICED = "INVOICED"
    OVERRIDDEN = "OVERRIDDEN"
    DELETED = "DELETED"
    UNSAVED = "UNSAVED"
    PAYMENT_TRANSACTION_REMOVED = "PAYMENT_TRANSACTION_REMOVED"


class LedgerReceiptStatus(Enum):
    APPROVED = "APPROVED"
    DELETED = "DELETED"
    EMPTY = "EMPTY"
    INVALIDATED = "INVALIDATED"
    INVOICED = "INVOICED"
    MARKED_PAID = "MARKED_PAID"
    NOT_SENT = "NOT_SENT"
    OVERRIDDEN = "OVERRIDDEN"
    PAID = "PAID"
    PARTLY_PAID = "PARTLY_PAID"
    PAYMENT_DENIED = "PAYMENT_DENIED"
    PAYMENT_QUEUED = "PAYMENT_QUEUED"
    PAYMENT_SENT_TO_BANK = "PAYMENT_SENT_TO_BANK"
    PAYMENT_TRANSACTION_REMOVED = "PAYMENT_TRANSACTION_REMOVED"
    RECEIVED = "RECEIVED"
    SENT = "SENT"
    STARTED = "STARTED"
    UNFINISHED = "UNFINISHED"
    UNSAVED = "UNSAVED"
    VERIFIED = "VERIFIED"


class TrackingPeriodStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PENDING = "PENDING"


class InvoiceLanguage(Enum):
    FINNISH = "FINNISH"
    ENGLISH = "ENGLISH"
    SWEDISH = "SWEDISH"
    ESTONIAN = "ESTONIAN"
    NORWEGIAN = "NORWEGIAN"
    DANISH = "DANISH"


class PartnerType(Enum):
    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"
    PERSON = "PERSON"


class LedgerReceiptType(Enum):
    JOURNAL = "JOURNAL"
    PURCHASE_INVOICE = "PURCHASE_INVOICE"
    SALES_INVOICE = "SALES_INVOICE"
    PERIODIC_TAX_RETURN = "PERIODIC_TAX_RETURN"
    TRAVEL_INVOICE = "TRAVEL_INVOICE"
    BILL_OF_CHARGES = "BILL_OF_CHARGES"
    VAT_FORM = "VAT_FORM"
    SALARY = "SALARY"
    EMPLOYER_CONTRIBUTION = "EMPLOYER_CONTRIBUTION"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    SALES_ORDER = "SALES_ORDER"
    BANK_STATEMENT_AS_RECEIPT = "BANK_STATEMENT_AS_RECEIPT"
    RECEIPT_FOR_OPENING_ACCOUNTS = "RECEIPT_FOR_OPENING_ACCOUNTS"
    REFERENCE_PAYMENT = "REFERENCE_PAYMENT"
    TRACKING_PERIOD_OPENING_RECEIPT = "TRACKING_PERIOD_OPENING_RECEIPT"
    VAT_SUMMARY = "VAT_SUMMARY"


class DimensionItemStatus(Enum):
    PASSIVE = "P"


class LedgerReceiptVATType(Enum):
    PURCHASE = "PURCHASE"
    SALES = "SALES"


class TransactionType(Enum):
    ENTRY = "ENTRY"
    RECONCILIATION_ENTRY = "RECONCILIATION_ENTRY"
    REVERSING_ENTRY = "REVERSING_ENTRY"


class BaseSalaryType(Enum):
    COMPENSATION = "COMPENSATION"
    HOURLY = "HOURLY"
    ONE_DAY = "ONE_DAY"
    ONE_MONTH = "ONE_MONTH"
    ONE_MONTH_TOTAL = "ONE_MONTH_TOTAL"
    ONE_WEEK = "ONE_WEEK"
    PAYMENT_BY_JOB = "PAYMENT_BY_JOB"
    TWO_WEEKS = "TWO_WEEKS"


class TravelExpensesSpecialHandling(Enum):
    NONE = "NONE"
    NON_PROFIT_ORGANISATION = "NON_PROFIT_ORGANISATION"
    RECIPIENT_OF_COMPENSATION_FOR_WORK = "RECIPIENT_OF_COMPENSATION_FOR_WORK"


class EarnerType(Enum):
    EMPLOYED_WITH_ASSISTANCE_FROM_THE_STATE_EMPLOYMENT_FUND = (
        "EMPLOYED_WITH_ASSISTANCE_FROM_THE_STATE_EMPLOYMENT_FUND"
    )
    JOINT_OWNER_WITH_PAYER = "JOINT_OWNER_WITH_PAYER"
    PARTIAL_OWNER = "PARTIAL_OWNER"
    KEY_EMPLOYEE = "KEY_EMPLOYEE"
    ORGANISATION = "ORGANISATION"
    PERSON_WORKING_IN_A_FRONTIER_DISTRICT = "PERSON_WORKING_IN_A_FRONTIER_DISTRICT"
    PERSON_WORKING_ABROAD = "PERSON_WORKING_ABROAD"
    ATHLETE = "ATHLETE"
    PERFORMING_ARTIST = "PERFORMING_ARTIST"
    SELF_EMPLOYED_PERSON_NO_OBLIGATION_TO_TAKE_OUT_YEL_OR_MYEL_INSURANCE = (
        "SELF_EMPLOYED_PERSON_NO_OBLIGATION_TO_TAKE_OUT_YEL_OR_MYEL_INSURANCE"
    )
    INVOICING_SERVICE_CLIENT = "INVOICING_SERVICE_CLIENT"


class SalaryChannel(Enum):
    NO_SENDING = "NO_SENDING"
    MAIL = "MAIL"
    EMAIL = "EMAIL"
    MOBILE = "MOBILE"
    ESALARY = "ESALARY"


class SalarySlipStatus(Enum):
    APPROVED = "APPROVED"
    CREATED = "CREATED"
    INVALIDATED = "INVALIDATED"
    IN_CORRECTION = "IN_CORRECTION"
    PAID = "PAID"
    PAYMENT_QUEUED = "PAYMENT_QUEUED"
    REJECTED = "REJECTED"
    REPORTED = "REPORTED"
    REPORTED_AND_PAID = "REPORTED_AND_PAID"
    REPORTED_AND_PAYMENT_QUEUED = "REPORTED_AND_PAYMENT_QUEUED"
    VERIFIED = "VERIFIED"


class SalarySlipPaidStatusDetails(Enum):
    MARKED_PAID = "MARKED_PAID"
    PAYMENT_SENT_TO_BANK = "PAYMENT_SENT_TO_BANK"
    PARTLY_PAID = "PARTLY_PAID"


class IncomesRegisterReportingSetting(Enum):
    DO_NOT_REPORT_DATA_ON_SLIP = "DO_NOT_REPORT_DATA_ON_SLIP"
    EARNINGS_REPORTED_ELSEWHERE = "EARNINGS_REPORTED_ELSEWHERE"
    FORM_BOTH_REPORTS = "FORM_BOTH_REPORTS"


class HolidayBonusCalculationBasis(Enum):
    AVERAGE_DAILY = "AVERAGE_DAILY"
    AVERAGE_HOURLY = "AVERAGE_HOURLY"
    MONTHLY_PLUS_SHIFT_COMPENSATIONS = "MONTHLY_PLUS_SHIFT_COMPENSATIONS"
    MONTHLY_WITH_STANDARD_DIVIDER = "MONTHLY_WITH_STANDARD_DIVIDER"
    MONTHLY_WITH_WORKDAY_DIVIDER = "MONTHLY_WITH_WORKDAY_DIVIDER"
    PERCENTAGE_BASED = "PERCENTAGE_BASED"
    PERCENTAGE_FOR_CONSTRUCTION_14_PLUS_4_5 = "PERCENTAGE_FOR_CONSTRUCTION_14_PLUS_4_5"
    PERCENTAGE_FOR_CONSTRUCTION_18_5_OR_14_PLUS_4_5 = "PERCENTAGE_FOR_CONSTRUCTION_18_5_OR_14_PLUS_4_5"
    RIGHT_FOR_TIME_OFF = "RIGHT_FOR_TIME_OFF"


class CarAgeGroup(Enum):
    A = "A"
    ABROAD = "ABROAD"
    B = "B"
    C = "C"


class EmploymentType_(Enum):
    PERMANENT = "PERMANENT"
    FIXED_TERM = "FIXED_TERM"
    TEMPORARY = "TEMPORARY"
    PART_TIME = "PART_TIME"
    TRAINEE = "TRAINEE"
    PENSIONER = "PENSIONER"
    NOT_EMPLOYED = "NOT_EMPLOYED"


class EmploymentTerminationReason(Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EMPLOYEES_RESIGNATION = "EMPLOYEES_RESIGNATION"
    OTHER = "OTHER"
    TERMINATION_GROUNDS = "TERMINATION_GROUNDS"
    FINANCIAL_AND_PRODUCTION_GROUNDS = "FINANCIAL_AND_PRODUCTION_GROUNDS"
    JOINT_AGREEMENT = "JOINT_AGREEMENT"
    RETIREMENT = "RETIREMENT"
    FIXED_TERM_EMPLOYMENT_TERMINATION = "FIXED_TERM_EMPLOYMENT_TERMINATION"


class WorkingTimeType(Enum):
    DAYS = "DAYS"
    HOURS = "HOURS"


class EmploymentWorkType(Enum):
    FULL_TIME = "FULL_TIME"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    PART_TIME = "PART_TIME"


class PensionInsuranceType(Enum):
    MYEL = "MYEL"
    NONE = "NONE"
    TYEL = "TYEL"
    YEL = "YEL"


class InsuranceNoObligationExceptionType(Enum):
    NO_OBLIGATION_TO_PROVIDE_INSURANCE_EARNINGS_RELATED_PENSION_INSURANCE = (
        "NO_OBLIGATION_TO_PROVIDE_INSURANCE_EARNINGS_RELATED_PENSION_INSURANCE"
    )
    NO_OBLIGATION_TO_PROVIDE_INSURANCE_HEALTH_INSURANCE = (
        "NO_OBLIGATION_TO_PROVIDE_INSURANCE_HEALTH_INSURANCE"
    )
    NO_OBLIGATION_TO_PROVIDE_INSURANCE_UNEMPLOYMENT_INSURANCE = (
        "NO_OBLIGATION_TO_PROVIDE_INSURANCE_UNEMPLOYMENT_INSURANCE"
    )
    NO_OBLIGATION_TO_PROVIDE_INSURANCE_ACCIDENT_AND_OCCUPATIONAL_DISEASE_INSURANCE = (
        "NO_OBLIGATION_TO_PROVIDE_INSURANCE_ACCIDENT_AND_OCCUPATIONAL_DISEASE_INSURANCE"
    )


class InsuranceNotSubjectExceptionType(Enum):
    NOT_SUBJECT_TO_FINNISH_SOCIAL_SEC_EARNINGS_RELATED_PENSION_INSURANCE = (
        "NOT_SUBJECT_TO_FINNISH_SOCIAL_SEC_EARNINGS_RELATED_PENSION_INSURANCE"
    )
    NOT_SUBJECT_TO_FINNISH_SOCIAL_SEC_HEALTH_INSURANCE = (
        "NOT_SUBJECT_TO_FINNISH_SOCIAL_SEC_HEALTH_INSURANCE"
    )
    NOT_SUBJECT_TO_FINNISH_SOCIAL_SEC_UNEMPLOYMENT_INSURANCE = (
        "NOT_SUBJECT_TO_FINNISH_SOCIAL_SEC_UNEMPLOYMENT_INSURANCE"
    )
    NOT_SUBJECT_TO_FINNISH_SOCIAL_SEC_ACCIDENT_AND_OCCUPATIONAL_DISEASE_INSURANCE = (
        "NOT_SUBJECT_TO_FINNISH_SOCIAL_SEC_ACCIDENT_AND_OCCUPATIONAL_DISEASE_INSURANCE"
    )


class SocialSecurityCertificate(Enum):
    FROM_FINLAND_A1 = "FROM_FINLAND_A1"
    NON_SOCIAL_SECURITY = "NON_SOCIAL_SECURITY"
    TO_FINLAND_A1 = "TO_FINLAND_A1"


class SixMonthRuleApplicability(Enum):
    NO = "NO"
    YES = "YES"


class ReceiptValidity(Enum):
    EMPTY = "EMPTY"
    IMMEDIATELY = "IMMEDIATELY"
    OVER_3_YEARS = "OVER_3_YEARS"
    SERVICE_PERIOD = "SERVICE_PERIOD"


class PersonLanguage(Enum):
    ENGLISH = "ENGLISH"
    FINNISH = "FINNISH"
    SWEDISH = "SWEDISH"


class PersonGender(Enum):
    FEMALE = "FEMALE"
    MALE = "MALE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PersonIdentifierType(Enum):
    FI = "FI"
    HETU = "HETU"
    YHD = "YHD"
    NO = "NO"
    AT = "AT"
    BE = "BE"
    BG = "BG"
    CY = "CY"
    HR = "HR"
    CZ = "CZ"
    DK = "DK"
    EE = "EE"
    FR = "FR"
    DE = "DE"
    GB = "GB"
    EL = "EL"
    HU = "HU"
    IE = "IE"
    IT = "IT"
    LV = "LV"
    LT = "LT"
    LU = "LU"
    MT = "MT"
    NL = "NL"
    PL = "PL"
    PT = "PT"
    RO = "RO"
    SK = "SK"
    SI = "SI"
    ES = "ES"
    SE = "SE"
    XI = "XI"


class ProductVersion(Enum):
    BACKOFFICE = "BACKOFFICE"
    BACKOFFICE_BASIC = "BACKOFFICE_BASIC"
    BACKOFFICE_PLUS = "BACKOFFICE_PLUS"
    BACKOFFICE_PREMIUM = "BACKOFFICE_PREMIUM"
    FINAGO_SOLO = "FINAGO_SOLO"
    FINANCIALS_ALKU = "FINANCIALS_ALKU"
    FINANCIALS_BASIC = "FINANCIALS_BASIC"
    FINANCIALS_ENTERPRISE = "FINANCIALS_ENTERPRISE"
    FINANCIALS_GOLD = "FINANCIALS_GOLD"
    FINANCIALS_LIGHT = "FINANCIALS_LIGHT"
    FINANCIALS_MAX = "FINANCIALS_MAX"
    FINANCIALS_PLATINUM = "FINANCIALS_PLATINUM"
    FINANCIALS_PLUS = "FINANCIALS_PLUS"
    FINANCIALS_PREMIUM = "FINANCIALS_PREMIUM"
    FINANCIALS_SILVER = "FINANCIALS_SILVER"
    FINANCIALS_UNLIMITED = "FINANCIALS_UNLIMITED"
    FLEX = "FLEX"
    SALES_GOLD = "SALES_GOLD"
    SALES_PLATINUM = "SALES_PLATINUM"
    SALES_SILVER = "SALES_SILVER"


class BrnType(Enum):
    ASSN = "ASSN"
    DK = "DK"
    FI = "FI"
    HETU = "HETU"
    NO = "NO"
    PN = "PN"
    SE = "SE"
    SSN = "SSN"
    YHD = "YHD"


class OperationType(Enum):
    BROKEN = "BROKEN"
    CEASED = "CEASED"
    CLOSED = "CLOSED"
    DEMONSTRATION = "DEMONSTRATION"
    EDUCATIONAL = "EDUCATIONAL"
    ELISA_PURCHASE = "ELISA_PURCHASE"
    PRODUCTION = "PRODUCTION"
    SPECIAL = "SPECIAL"
    TRIAL = "TRIAL"


class CurrencyRateSearchDensity(Enum):
    DAILY_EXCHANGE_RATE = "DAILY_EXCHANGE_RATE"
    LAST_DAY_OF_THE_MONTH = "LAST_DAY_OF_THE_MONTH"
    PROCOUNTOR_FIXED_RATE = "PROCOUNTOR_FIXED_RATE"


def find_country_by_code(code):
    try:
        return CountryCodes[code].value
    except KeyError:
        return None


class ProcountorBaseException(Exception):
    def __init__(self, *args, human_readable_error=None):
        super().__init__(*args)
        self.human_readable_error = human_readable_error


class ProcountorAPIException(ProcountorBaseException):
    pass


class ProcountorAPIValidationError(ProcountorBaseException):
    pass


class ProcountorRefreshTokenExpired(ProcountorBaseException):
    pass


class ProcountorAPIObject(object):
    @abstractmethod
    def as_dict(self):
        raise NotImplementedError  # pragma: no cover


class InfoMessage(ProcountorAPIObject):
    def __init__(self, message: Optional[str] = None):
        self.message: Optional[str] = message

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.message is not None:
            data["message"] = self.message
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, typing.Any]) -> "InfoMessage":
        return cls(
            message=data.get("message", None)
        )


class CompanySettings(ProcountorAPIObject):
    def __init__(
        self,
        invoice_discussion_enabled: Optional[bool] = None,
    ):
        self.invoice_discussion_enabled = invoice_discussion_enabled

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.invoice_discussion_enabled is not None:
            data["invoiceDiscussionEnabled"] = self.invoice_discussion_enabled
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, typing.Any]) -> "CompanySettings":
        return cls(
            invoice_discussion_enabled=data.get("invoiceDiscussionEnabled", None),
        )


class CompanyAddress(ProcountorAPIObject):
    def __init__(
        self,
        specifier: Optional[str] = None,
        po_box: Optional[str] = None,
        street: Optional[str] = None,
        zip: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[Country] = None,
    ):
        self.specifier: Optional[str] = specifier
        self.po_box: Optional[str] = po_box
        self.street: Optional[str] = street
        self.zip: Optional[str] = zip
        self.city: Optional[str] = city
        self.country: Optional[Country] = country

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.specifier is not None:
            data["specifier"] = self.specifier
        if self.po_box is not None:
            data["poBox"] = self.po_box
        if self.street is not None:
            data["street"] = self.street
        if self.zip is not None:
            data["zip"] = self.zip
        if self.city is not None:
            data["city"] = self.city
        if self.country is not None:
            data["country"] = self.country.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, typing.Any]) -> "CompanyAddress":
        country = None
        if "country" in data and data["country"] is not None:
            country = Country(data["country"])
        return cls(
            specifier=data.get("specifier", None),
            po_box=data.get("poBox", None),
            street=data.get("street", None),
            zip=data.get("zip", None),
            city=data.get("city", None),
            country=country,
        )


class CompanyBillingAddress(ProcountorAPIObject):
    def __init__(
        self,
        street: Optional[str] = None,
        zip: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[Country] = None,
    ):
        self.street: Optional[str] = street
        self.zip: Optional[str] = zip
        self.city: Optional[str] = city
        self.country: Optional[Country] = country

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.street is not None:
            data["street"] = self.street
        if self.zip is not None:
            data["zip"] = self.zip
        if self.city is not None:
            data["city"] = self.city
        if self.country is not None:
            data["country"] = self.country.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, typing.Any]) -> "CompanyBillingAddress":
        country = None
        if "country" in data and data["country"] is not None:
            country = Country(data["country"])
        return cls(
            street=data.get("street", None),
            zip=data.get("zip", None),
            city=data.get("city", None),
            country=country,
        )


class BusinessIdentifier(ProcountorAPIObject):
    def __init__(
        self,
        brn_type: Optional[BrnType] = None,
        code: Optional[str] = None,
    ):
        self.brn_type: Optional[BrnType] = brn_type
        self.code: Optional[str] = code

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.brn_type is not None:
            data["brnType"] = self.brn_type.value
        if self.code is not None:
            data["code"] = self.code
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, typing.Any]) -> "BusinessIdentifier":
        brn_type = None
        if "brnType" in data and data["brnType"] is not None:
            brn_type = BrnType(data["brnType"])
        return cls(
            brn_type=brn_type,
            code=data.get("code", None),
        )


class Company(ProcountorAPIObject):
    def __init__(
        self,
        id: int,
        name: str,
        country: Optional[Country] = None,
        product_version: Optional[ProductVersion] = None,
        operation_type: Optional[OperationType] = None,
        accounting_office_name: Optional[str] = None,
        accounting_office_id: Optional[int] = None,
        company_address: Optional[CompanyAddress] = None,
        billing_address: Optional[CompanyBillingAddress] = None,
        mva: Optional[bool] = None,
        in_trade_register: Optional[bool] = None,
        business_identifier: Optional[BusinessIdentifier] = None,
        accounting_coa_languages: Optional[typing.List[str]] = None,
        company_currency: Optional[str] = None,
        currency_rate_search_density: Optional[CurrencyRateSearchDensity] = None,
    ):
        self.id: int = id
        self.name: str = name
        self.country: Optional[Country] = country
        self.product_version: Optional[ProductVersion] = product_version
        self.operation_type: Optional[OperationType] = operation_type
        self.accounting_office_name: Optional[str] = accounting_office_name
        self.accounting_office_id: Optional[int] = accounting_office_id
        self.company_address: Optional[CompanyAddress] = company_address
        self.billing_address: Optional[CompanyBillingAddress] = billing_address
        self.mva: Optional[bool] = mva
        self.in_trade_register: Optional[bool] = in_trade_register
        self.business_identifier: Optional[BusinessIdentifier] = business_identifier
        self.accounting_coa_languages: Optional[typing.List[str]] = accounting_coa_languages
        self.company_currency: Optional[str] = company_currency
        self.currency_rate_search_density: Optional[CurrencyRateSearchDensity] = currency_rate_search_density

    def as_dict(self) -> typing.Dict:
        data = {
            "id": self.id,
            "name": self.name,
        }
        if self.country is not None:
            data["country"] = self.country.value
        if self.product_version is not None:
            data["productVersion"] = self.product_version.value
        if self.operation_type is not None:
            data["operationType"] = self.operation_type.value
        if self.accounting_office_name is not None:
            data["accountingOfficeName"] = self.accounting_office_name
        if self.accounting_office_id is not None:
            data["accountingOfficeId"] = self.accounting_office_id
        if self.company_address is not None:
            data["companyAddress"] = self.company_address.as_dict()
        if self.billing_address is not None:
            data["billingAddress"] = self.billing_address.as_dict()
        if self.mva is not None:
            data["mva"] = self.mva
        if self.in_trade_register is not None:
            data["inTradeRegister"] = self.in_trade_register
        if self.business_identifier is not None:
            data["businessIdentifier"] = self.business_identifier.as_dict()
        if self.accounting_coa_languages is not None:
            data["accountingCoaLanguages"] = self.accounting_coa_languages
        if self.company_currency is not None:
            data["companyCurrency"] = self.company_currency
        if self.currency_rate_search_density is not None:
            data["currencyRateSearchDensity"] = self.currency_rate_search_density.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, typing.Any]) -> "Company":
        country = None
        if "country" in data and data["country"] is not None:
            country = Country(data["country"])
        product_version = None
        if "productVersion" in data and data["productVersion"] is not None:
            product_version = ProductVersion(data["productVersion"])
        operation_type = None
        if "operationType" in data and data["operationType"] is not None:
            operation_type = OperationType(data["operationType"])
        company_address = None
        if "companyAddress" in data and data["companyAddress"] is not None:
            company_address = CompanyAddress.from_dict(data["companyAddress"])
        billing_address = None
        if "billingAddress" in data and data["billingAddress"] is not None:
            billing_address = CompanyBillingAddress.from_dict(data["billingAddress"])
        business_identifier = None
        if "businessIdentifier" in data and data["businessIdentifier"] is not None:
            business_identifier = BusinessIdentifier.from_dict(data["businessIdentifier"])
        currency_rate_search_density = None
        if "currencyRateSearchDensity" in data and data["currencyRateSearchDensity"] is not None:
            currency_rate_search_density = CurrencyRateSearchDensity(data["currencyRateSearchDensity"])
        return cls(
            id=data["id"],
            name=data["name"],
            country=country,
            product_version=product_version,
            operation_type=operation_type,
            accounting_office_name=data.get("accountingOfficeName", None),
            accounting_office_id=data.get("accountingOfficeId", None),
            company_address=company_address,
            billing_address=billing_address,
            mva=data.get("mva", None),
            in_trade_register=data.get("inTradeRegister", None),
            business_identifier=business_identifier,
            accounting_coa_languages=data.get("accountingCoaLanguages", None),
            company_currency=data.get("companyCurrency", None),
            currency_rate_search_density=currency_rate_search_density,
        )


class SessionInfo(ProcountorAPIObject):
    def __init__(
        self,
        company_id: Optional[int] = None,
        name: Optional[str] = None,
        country: Optional[Country] = None,
        product_version: Optional[ProductVersion] = None,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
        company_settings: Optional[CompanySettings] = None,
    ):
        self.company_id = company_id
        self.name = name
        self.country = country
        self.product_version = product_version
        self.user_id = user_id
        self.user_name = user_name
        self.company_settings = company_settings

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.company_id is not None:
            data["companyId"] = self.company_id
        if self.name is not None:
            data["name"] = self.name
        if self.country is not None:
            data["country"] = self.country.value
        if self.product_version is not None:
            data["productVersion"] = self.product_version.value
        if self.user_id is not None:
            data["userId"] = self.user_id
        if self.user_name is not None:
            data["userName"] = self.user_name
        if self.company_settings is not None:
            data["companySettings"] = self.company_settings.as_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, typing.Any]) -> "SessionInfo":
        company_settings = None
        if "companySettings" in data and data["companySettings"] is not None:
            company_settings = CompanySettings.from_dict(data["companySettings"])
        country = None
        if "country" in data and data["country"] is not None:
            country = Country(data["country"])
        product_version = None
        if "productVersion" in data and data["productVersion"] is not None:
            product_version = ProductVersion(data["productVersion"])
        return cls(
            company_id=data.get("companyId", None),
            name=data.get("name", None),
            country=country,
            product_version=product_version,
            user_id=data.get("userId", None),
            user_name=data.get("userName", None),
            company_settings=company_settings,
        )


def python_to_procountor_name(name):
    out = ""
    uppercase_next = False
    for char in name:
        if char == "_":
            uppercase_next = True
            continue
        if uppercase_next:
            uppercase_next = False
            char = char.upper()
        out += char
    return out


def value_from_type(value, type_hint):
    if value is None:
        return value
    if hasattr(type_hint, "__class__"):
        if type_hint.__class__ == typing._UnionGenericAlias:
            return value_from_type(value, type_hint.__args__[0])
        if type_hint.__class__ == enum.EnumType:
            return type_hint(value)
    return value


def auto_as_dict(obj):
    return {
        python_to_procountor_name(k): v.as_dict() if hasattr(v, "as_dict") else v.value if hasattr(v, "value") else v
        for k, v in vars(obj).items()
        if v is not None
    }


def auto_from_dict(obj, data):
    # Get valid keys from init function
    valid_keys = {
        python_to_procountor_name(name): (name, typehint)
        for name, typehint in typing.get_type_hints(obj.__init__).items()
    }
    opts = {
        valid_keys[k][0]: value_from_type(v, valid_keys[k][1])
        for k, v in data.items()
        if k in valid_keys
    }
    return obj(**opts)


class InvoicePhysicalAddress(ProcountorAPIObject):
    def __init__(
        self,
        name,
        specifier: str = None,
        street: str = None,
        zip: str = None,
        city: str = None,
        country: Country = None,
        subdivision: str = None,
    ):
        if country and not isinstance(country, Country):
            raise ProcountorAPIValidationError("Invalid country {}".format(country))
        self._data = {
            "name": name,
        }
        if specifier:
            self._data["specifier"] = specifier
        if street:
            self._data["street"] = street
        if zip:
            self._data["zip"] = zip
        if city:
            self._data["city"] = city
        if country:
            self._data["country"] = country.value
        if subdivision:
            self._data["subdivision"] = subdivision

    def __getattr__(self, item):
        if item in self._data:
            return self._data[item]
        raise AttributeError(
            "'{}' object has no attribute '{}'".format(self.__class__.__name__, item)
        )

    def as_dict(self) -> Dict:
        return self._data

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            specifier=data.get("specifier", None),
            street=data.get("street", None),
            zip=data.get("zip", None),
            city=data.get("city", None),
            country=Country(data.get("country", None)),
            subdivision=data.get("subdivision", None)
        )


class CounterPartyAddress(InvoicePhysicalAddress):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "street" not in self._data:
            raise ProcountorAPIValidationError("street is mandatory for counter party")
        if "city" not in self._data:
            raise ProcountorAPIValidationError("city is mandatory for counter party")
        if "zip" not in self._data:
            raise ProcountorAPIValidationError("zip is mandatory for counter party")
        if "country" not in self._data:
            raise ProcountorAPIValidationError("country is mandatory for counter party")


class InvoiceBankAccount(ProcountorAPIObject):
    def __init__(self, account_number: str, bic: str = None):
        self.account_number = account_number.replace(" ", "").strip()
        self.bic = bic

    def as_dict(self) -> Dict:
        data = {"accountNumber": self.account_number}
        if self.bic:
            data["bic"] = self.bic
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            account_number=data["accountNumber"],
            bic=data.get("bic", None),
        )


class EInvoiceAddress(ProcountorAPIObject):
    def __init__(
        self,
        operator: typing.Optional[str] = None,
        address: typing.Optional[str] = None,
        ediId: typing.Optional[str] = None,
    ):
        self.operator = operator
        self.address = address
        self.ediId = ediId

    def as_dict(self) -> typing.Dict:
        data = {
        }

        if self.operator is not None:
            data["operator"] = self.operator
        if self.address is not None:
            data["address"] = self.address
        if self.ediId is not None:
            data["ediId"] = self.ediId

        return data

    @classmethod
    def from_dict(cls, data) -> "EInvoiceAddress":
        params = {
        }

        if "operator" in data:
            params["operator"] = data["operator"]
        if "address" in data:
            params["address"] = data["address"]
        if "ediId" in data:
            params["ediId"] = data["ediId"]

        return cls(**params)


class InvoiceCounterParty(ProcountorAPIObject):
    def __init__(
        self,
        contact_person: str = None,
        business_id: str = None,
        address: InvoicePhysicalAddress = None,
        bank_account: InvoiceBankAccount = None,
        customer_number: str = None,
        tax_code: str = None,
        einvoice_address: EInvoiceAddress = None,
        email: str = None,
    ):
        self.contact_person = contact_person
        self.business_id = business_id
        self.customer_number = customer_number
        self.address = address
        self.bank_account = bank_account
        self.tax_code = tax_code
        self.einvoice_address = einvoice_address
        self.email = email

    def as_dict(self) -> Dict:
        data = {
            "contactPersonName": self.contact_person,
            "identifier": self.business_id,
        }
        if self.customer_number:
            data["customerNumber"] = self.customer_number
        if self.address:
            data["counterPartyAddress"] = self.address.as_dict()
        if self.bank_account:
            data["bankAccount"] = self.bank_account.as_dict()
        if self.tax_code:
            data["taxCode"] = self.tax_code
        if self.email:
            data["email"] = self.email
        if self.einvoice_address:
            data["einvoiceAddress"] = self.einvoice_address.as_dict()
        return data

    @classmethod
    def from_dict(cls, data):
        address = None
        bank_account = None
        einvoice_address = None
        if "address" in data:
            address = EInvoiceAddress.from_dict(data["address"])
        if "bankAccount" in data:
            bank_account = InvoiceBankAccount.from_dict(data["bankAccount"])
        if "einvoiceAddress" in data:
            einvoice_address = EInvoiceAddress.from_dict(data["einvoiceAddress"])

        return cls(
            contact_person=data.get("contactPersonName", None),
            business_id=data.get("identifier", None),
            customer_number=data.get("customerNumber", None),
            address=address,
            bank_account=bank_account,
            email=data.get("email", None),
            tax_code=data.get("taxCode", None),
            einvoice_address=einvoice_address,
        )


class InvoicePaymentInfo(ProcountorAPIObject):
    def __init__(
        self,
        due_date: typing.Union[datetime, date],
        payment_method: PaymentMethod,
        currency: Currency,
        currency_rate: Decimal,
        bank_reference_code: str = None,
        bank_account: InvoiceBankAccount = None,
        bank_reference_code_type: BankReferenceCodeType = None,
        clearing_code: str = None,
    ):
        """
        Invoice Payment Info object
        """
        self.payment_method = payment_method or PaymentMethod.BANK_TRANSFER
        if not isinstance(self.payment_method, PaymentMethod):
            raise ProcountorAPIValidationError("Invalid payment method")
        if not isinstance(currency, Currency):
            raise ProcountorAPIValidationError("Invalid currency")
        if self.payment_method == PaymentMethod.BANK_TRANSFER and not bank_account:
            raise ProcountorAPIValidationError(
                "Bank account is required for BANK_TRANSFER method"
            )
        self.currency = currency
        self.bank_account = bank_account
        self.due_date = due_date
        self.clearing_code = clearing_code
        self.currency_rate = currency_rate
        self.bank_reference_code = bank_reference_code
        if bank_reference_code_type:
            if not isinstance(bank_reference_code_type, BankReferenceCodeType):
                raise ProcountorAPIValidationError(
                    "Invalid bank reference code type: {}".format(
                        bank_reference_code_type
                    )
                )
        self.bank_reference_code_type = bank_reference_code_type

    def as_dict(self) -> Dict:
        data = {
            "paymentMethod": self.payment_method.value,
            "currency": self.currency.value,
            "dueDate": self.due_date.strftime("%Y-%m-%d"),
        }
        if self.currency_rate is not None:
            data["currencyRate"] = self.currency_rate
        if self.bank_account:
            data["bankAccount"] = self.bank_account.as_dict()
        if self.bank_reference_code is not None:
            data["bankReferenceCode"] = self.bank_reference_code
        if self.bank_reference_code_type:
            data["bankReferenceCodeType"] = self.bank_reference_code_type.value
        if self.clearing_code:
            data["clearingCode"] = self.clearing_code
        if self.currency_rate:
            data["currencyRate"] = self.currency_rate
        return data

    @classmethod
    def from_dict(cls, data):
        bank_account = None
        bank_account_dict = data.get("bankAccount")
        if bank_account_dict:
            bank_account = InvoiceBankAccount.from_dict(bank_account_dict)
        bank_reference_code_type = None
        bank_reference_code_type_value = data.get("bankReferenceCodeType", None)
        if bank_reference_code_type_value:
            bank_reference_code_type = BankReferenceCodeType(bank_reference_code_type_value)

        return cls(
            payment_method=PaymentMethod(data["paymentMethod"]),
            currency=Currency(data["currency"]),
            due_date=data["dueDate"],
            clearing_code=data.get("clearingCode", None),
            bank_account=bank_account,
            bank_reference_code=data.get("bankReferenceCode", None),
            bank_reference_code_type=bank_reference_code_type,
            currency_rate=data.get("currencyRate", None),
        )


class BusinessPartnerPaymentInfo(ProcountorAPIObject):
    def __init__(
        self,
        factoringContractId: int,
        payment_method: PaymentMethod,
        bankAccount: typing.Optional[str] = None,
        paymentTermDays: typing.Optional[str] = None,
        paymentTermPercentage: typing.Optional[Decimal] = None,
        penalInterestRate: typing.Optional[Decimal] = None,
        discountPercentage: typing.Optional[Decimal] = None,
        currency: typing.Optional[Currency] = None,
        deliveryMethod: typing.Optional[str] = None,
        clearingCode: typing.Optional[str] = None,
        bic: typing.Optional[str] = None,
        customerAccountNumber: typing.Optional[str] = None,
    ):
        self.factoringContractId = factoringContractId
        self.payment_method = payment_method
        self.bankAccount = bankAccount
        self.paymentTermDays = paymentTermDays
        self.paymentTermPercentage = paymentTermPercentage
        self.penalInterestRate = penalInterestRate
        self.discountPercentage = discountPercentage
        self.currency = currency
        self.deliveryMethod = deliveryMethod
        self.clearingCode = clearingCode
        self.bic = bic
        self.customerAccountNumber = customerAccountNumber

    def as_dict(self) -> typing.Dict:
        data = {
            "factoringContractId": self.factoringContractId,
            "payment_method": self.payment_method,
        }

        if self.bankAccount is not None:
            data["bankAccount"] = self.bankAccount
        if self.paymentTermDays is not None:
            data["paymentTermDays"] = self.paymentTermDays
        if self.paymentTermPercentage is not None:
            data["paymentTermPercentage"] = self.paymentTermPercentage
        if self.penalInterestRate is not None:
            data["penalInterestRate"] = self.penalInterestRate
        if self.discountPercentage is not None:
            data["discountPercentage"] = self.discountPercentage
        if self.currency is not None:
            data["currency"] = self.currency
        if self.deliveryMethod is not None:
            data["deliveryMethod"] = self.deliveryMethod
        if self.clearingCode is not None:
            data["clearingCode"] = self.clearingCode
        if self.bic is not None:
            data["bic"] = self.bic
        if self.customerAccountNumber is not None:
            data["customerAccountNumber"] = self.customerAccountNumber

        return data

    @classmethod
    def from_dict(cls, data) -> "BusinessPartnerPaymentInfo":
        params = {
           "factoringContractId": data["factoringContractId"],
           "payment_method": data["paymentMethod"],
        }

        if "bankAccount" in data:
            params["bankAccount"] = data["bankAccount"]
        if "paymentTermDays" in data:
            params["paymentTermDays"] = data["paymentTermDays"]
        if "paymentTermPercentage" in data:
            params["paymentTermPercentage"] = data["paymentTermPercentage"]
        if "penalInterestRate" in data:
            params["penalInterestRate"] = data["penalInterestRate"]
        if "discountPercentage" in data:
            params["discountPercentage"] = data["discountPercentage"]
        if "currency" in data:
            params["currency"] = data["currency"]
        if "deliveryMethod" in data:
            params["deliveryMethod"] = data["deliveryMethod"]
        if "clearingCode" in data:
            params["clearingCode"] = data["clearingCode"]
        if "bic" in data:
            params["bic"] = data["bic"]
        if "customerAccountNumber" in data:
            params["customerAccountNumber"] = data["customerAccountNumber"]

        return cls(**params)


class InvoiceRow(ProcountorAPIObject):
    def __init__(
        self,
        product: str,
        quantity: Decimal,
        unit: Unit,
        unit_price: Decimal,
        discount_percent: Decimal,
        vat_percent: Decimal,
        product_id: str = None,
        product_code: str = None,
        vat_status: int = None,
        comment: str = None,
        start_date: datetime.date = None,
        end_date: datetime.date = None,
    ):
        """
        :param product: Product name.
        :param quantity: Product quantity.
        :param unit: Product unit.
        :param unit_price: Product unit price. This value is affected by the "unit prices include VAT" setting on the
        invoice.
        :param discount_percent: Product discount percentage.
        :param vat_percent: Product VAT percentage. Must be a percentage currently in use for the company.
        :param product_id: Unique identifier for a product. Links the invoice row to a product in the product register.
        Note that all other fields (name, price, ...) of an invoice row can be modified independently of the information
        in the product register. If one wants to use accounts from product register, accountingByRow must be true.
        :param product_code: Product code.
        :param vat_status: Product VAT status.
        :param comment: Invoice row comment. Visible on the invoice. Use \\ as line break. maxLength: 255
        """
        self.product = product
        self.quantity = quantity
        if not isinstance(unit, Unit):
            raise ProcountorAPIValidationError("Invalid unit: {}".format(unit))
        self.unit = unit
        self.unit_price = unit_price
        self.discount_percent = discount_percent
        self.vat_percent = vat_percent
        self.comment = comment
        self.vat_status = vat_status
        self.product_code = product_code
        self.product_id = product_id
        self.start_date = start_date
        self.end_date = end_date

    def as_dict(self):
        data = {
            "product": self.product,
            "quantity": self.quantity,
            "unit": self.unit.value,
            "unitPrice": self.unit_price,
            "discountPercent": self.discount_percent,
            "vatPercent": self.vat_percent,
        }
        if self.product_id:
            data["productId"] = self.product_id
        if self.comment:
            data["comment"] = self.comment
        if self.product_code:
            data["productCode"] = self.product_code
        if self.vat_status:
            data["vatStatus"] = self.vat_status
        if self.start_date:
            data["startDate"] = self.start_date.strftime("%Y-%m-%d")
        if self.end_date:
            data["endDate"] = self.end_date.strftime("%Y-%m-%d")
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            product=data["product"],
            quantity=Decimal(data["quantity"]),
            unit=Unit(data["unit"]),
            unit_price=Decimal(data["unitPrice"]),
            discount_percent=Decimal(data["discountPercent"]),
            vat_percent=Decimal(data["vatPercent"]),
            product_id=data.get("productId", None),
            product_code=data.get("productCode", None),
            vat_status=data.get("vatStatus", None),
            comment=data.get("comment", None),
            start_date=data.get("startDate", None),
            end_date=data.get("endDate", None),
        )


class AttachmentMetadata(ProcountorAPIObject):
    def __init__(
        self,
        name: str,
        reference_type: AttachmentReferenceType,
        reference_id: int,
        mime_type: str,
    ):
        self.name = name
        self.reference_type = reference_type
        if not isinstance(self.reference_type, AttachmentReferenceType):
            raise ProcountorAPIValidationError(
                "Invalid reference type: {}".format(self.reference_type)
            )
        self.reference_id = reference_id
        self.mime_type = mime_type

    def as_dict(self):
        return {
            "name": self.name,
            "referenceType": self.reference_type.value,
            "referenceId": self.reference_id,
            "mimeType": self.mime_type,
            "sendWithInvoice": False,
        }


class ExtraInfo(ProcountorAPIObject):
    def __init__(
        self, accounting_by_row: bool = True, unit_prices_include_vat: bool = False
    ):
        self.accounting_by_row = accounting_by_row
        self.unit_prices_include_vat = unit_prices_include_vat

    def as_dict(self):
        return {
            "accountingByRow": self.accounting_by_row,
            "unitPricesIncludeVat": self.unit_prices_include_vat,
        }

    @classmethod
    def from_dict(cls, param):
        return cls(
            accounting_by_row=param["accountingByRow"],
            unit_prices_include_vat=param["unitPricesIncludeVat"],
        )


class Invoice(ProcountorAPIObject):
    def __init__(
        self,
        date: typing.Union[datetime, date],
        rows: List[InvoiceRow],
        vat_status: int,
        extra_info: ExtraInfo,
        payment_info: InvoicePaymentInfo,
        invoice_channel: InvoiceChannel = None,
        partner_id: int = None,
        status: InvoiceStatus = None,
        counter_party: InvoiceCounterParty = None,
        invoice_type: InvoiceType = None,
        invoice_number: str = None,
        billing_address: InvoicePhysicalAddress = None,
        delivery_address: typing.Union[InvoicePhysicalAddress, Dict, None] = None,
        discount_percent: int = 0,
        additional_information: str = None,
        order_number: str = None,
        order_reference: str = None,
        original_invoice_number: str = None,
        notes: str = None,
        language: InvoiceLanguage = None,
        id: int = None,
        ledger_receipt_id: int = None
    ):
        self.id = id
        self.partner_id = partner_id
        self.date = date
        if invoice_type and not isinstance(invoice_type, InvoiceType):
            raise ProcountorAPIValidationError("Invalid invoice type")
        self.invoice_type = invoice_type or InvoiceType.PURCHASE_INVOICE
        if status and not isinstance(status, InvoiceStatus):
            raise ProcountorAPIValidationError("Invalid invoice status")
        self.status = status or InvoiceStatus.UNFINISHED
        self.counter_party = counter_party
        self.billing_address = billing_address
        self.delivery_address = delivery_address
        self.discount_percent = discount_percent
        self.payment_info = payment_info
        if (
            self.payment_info is None
            and self.invoice_type == InvoiceType.PURCHASE_INVOICE
        ):
            raise ProcountorAPIValidationError(
                "payment_info is required for Purchase Invoice"
            )
        self.order_reference = order_reference
        self.original_invoice_number = original_invoice_number
        self.rows = rows
        self.vat_status = vat_status
        self.invoice_number = invoice_number
        self.invoice_channel = invoice_channel or InvoiceChannel.EMAIL
        if not isinstance(self.invoice_channel, InvoiceChannel):
            raise ProcountorAPIException(
                "Invalid invoice channel type: {}".format(self.invoice_channel)
            )
        self.additional_information = additional_information
        if self.additional_information and len(self.additional_information) > 10000:
            raise ProcountorAPIException(
                "Additional information too long: {} > 10000".format(
                    len(self.additional_information)
                )
            )
        self.extra_info = extra_info
        if self.extra_info and not isinstance(self.extra_info, ExtraInfo):
            raise ProcountorAPIException(
                "Invalid extra info type: {}".format(self.extra_info)
            )
        self.order_number = order_number
        self.notes = notes
        self.language = language
        if not isinstance(self.language, InvoiceLanguage):
            raise ProcountorAPIException(
                "Invalid language type: {}".format(self.language)
            )
        self.ledger_receipt_id = ledger_receipt_id

    def as_dict(self) -> Dict:
        data = {
            "type": self.invoice_type.value,
            "status": self.status.value,
            "date": self.date.strftime("%Y-%m-%d"),
            "invoiceRows": [x.as_dict() for x in self.rows],
            "vatStatus": self.vat_status,
            "invoiceChannel": self.invoice_channel.value,
            "discountPercent": self.discount_percent,
        }
        if self.partner_id:
            data["partnerId"] = self.partner_id
        if self.counter_party:
            data["counterParty"] = self.counter_party.as_dict()
        if self.additional_information:
            data["additionalInformation"] = self.additional_information
        if self.billing_address:
            data["billingAddress"] = self.billing_address.as_dict()
        if self.delivery_address:
            if isinstance(self.delivery_address, dict):
                data["deliveryAddress"] = self.delivery_address
            else:
                data["deliveryAddress"] = self.delivery_address.as_dict()
        if self.payment_info:
            data["paymentInfo"] = self.payment_info.as_dict()
        if self.order_number:
            data["orderNumber"] = self.order_number
        if self.order_reference:
            data["orderReference"] = self.order_reference
        if self.original_invoice_number:
            data["originalInvoiceNumber"] = self.original_invoice_number
        if self.extra_info:
            data["extraInfo"] = self.extra_info.as_dict()
        if self.notes:
            data["notes"] = self.notes
        if self.language:
            data["language"] = self.language.value
        return data

    @classmethod
    def from_dict(cls, data):
        payment_info = None
        extra_info = None
        billing_address = None
        counter_party = None
        delivery_address = None
        language = None
        if "paymentInfo" in data:
            payment_info = InvoicePaymentInfo.from_dict(data["paymentInfo"])
        if "extraInfo" in data:
            extra_info = ExtraInfo.from_dict(data["extraInfo"])
        if "billingAddress" in data:
            billing_address = InvoicePhysicalAddress.from_dict(data["billingAddress"])
        if "counterParty" in data:
            counter_party = InvoiceCounterParty.from_dict(data["counterParty"])
        if "deliveryAddress" in data:
            delivery_address = InvoicePhysicalAddress.from_dict(data["deliveryAddress"])
        if "language" in data:
            language = InvoiceLanguage(data["language"])
        return cls(
            id=data["id"],
            invoice_type=InvoiceType(data["type"]),
            status=InvoiceStatus(data["status"]),
            date=datetime.strptime(data["date"], "%Y-%m-%d").date(),
            rows=[InvoiceRow.from_dict(row) for row in data["invoiceRows"]],
            vat_status=data["vatStatus"],
            invoice_channel=InvoiceChannel(data["invoiceChannel"]),
            discount_percent=data["discountPercent"],
            partner_id=data.get("partnerId", None),
            counter_party=counter_party,
            invoice_number=data.get("invoiceNumber", None),
            additional_information=data.get("additionalInformation", None),
            billing_address=billing_address,
            delivery_address=delivery_address,
            payment_info=payment_info,
            order_number=data.get("orderNumber", None),
            order_reference=data.get("orderReference", None),
            original_invoice_number=data.get("originalInvoiceNumber", None),
            extra_info=extra_info,
            notes=data.get("notes", None),
            language=language,
            ledger_receipt_id=data.get("ledgerReceiptId", None),
        )


class BusinessPartnerBasicInfo(ProcountorAPIObject):
    def __init__(
        self,
        id: int,
        name: str,
        billing_address: Dict,
        invoicing_info: Dict,
        registry_info: Dict,
        partner_type: PartnerType,
        version: typing.Optional[int] = None,
    ):
        self.id = id
        self.partner_type = partner_type
        self.name = name
        self.billing_address = billing_address
        self.invoicing_info = invoicing_info
        self.registry_info = registry_info
        self.version = version

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            name=data["name"],
            billing_address=data["billingAddress"],
            invoicing_info=data["invoicingInfo"],
            registry_info=data["registryInfo"],
            partner_type=PartnerType(data["type"]),
            version=data["version"]
        )

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "billingAddress": self.billing_address,
            "invoicingInfo": self.invoicing_info,
            "registry_info": self.registry_info,
            "type": self.partner_type.value,
            "version": self.version,
        }


class BusinessPartnerAddress(ProcountorAPIObject):
    def __init__(
        self,
        name: str,
        specifier: typing.Optional[str] = None,
        street: typing.Optional[str] = None,
        zip: typing.Optional[str] = None,
        city: typing.Optional[str] = None,
        country: typing.Optional[Country] = None,
        subdivision: typing.Optional[str] = None,
    ):
        self.name = name
        self.specifier = specifier
        self.street = street
        self.zip = zip
        self.city = city
        self.country = country
        self.subdivision = subdivision

    def as_dict(self) -> typing.Dict:
        data = {
            "name": self.name,
        }

        if self.specifier is not None:
            data["specifier"] = self.specifier
        if self.street is not None:
            data["street"] = self.street
        if self.zip is not None:
            data["zip"] = self.zip
        if self.city is not None:
            data["city"] = self.city
        if self.country is not None:
            data["country"] = self.country.value
        if self.subdivision is not None:
            data["subdivision"] = self.subdivision

        return data

    @classmethod
    def from_dict(cls, data) -> "BusinessPartnerAddress":
        params = {
           "name": data["name"],
        }

        if "specifier" in data:
            params["specifier"] = data["specifier"]
        if "street" in data:
            params["street"] = data["street"]
        if "zip" in data:
            params["zip"] = data["zip"]
        if "city" in data:
            params["city"] = data["city"]
        if "subdivision" in data:
            params["subdivision"] = data["subdivision"]
        if "country" in data:
            params["country"] = Country(data["country"])

        return cls(**params)


class InvoicingInfo(ProcountorAPIObject):
    def __init__(
        self,
        customer_number: typing.Optional[str] = None,
        identifier: typing.Optional[str] = None,
        ovt: typing.Optional[str] = None,
        invoice_channel: typing.Optional[InvoiceChannel] = None,
        contact_person: typing.Optional[str] = None,
        language: typing.Optional[InvoiceLanguage] = None,
        email: typing.Optional[str] = None,
        einvoice_operator: typing.Optional[str] = None,
        einvoice_address: typing.Optional[str] = None,
    ):
        self.customer_number = customer_number
        self.identifier = identifier
        self.ovt = ovt
        self.invoice_channel = invoice_channel
        self.contact_person = contact_person
        self.language = language
        self.email = email
        self.einvoice_operator = einvoice_operator
        self.einvoice_address = einvoice_address

    def as_dict(self) -> typing.Dict:
        data = {}

        if self.customer_number is not None:
            data["customerNumber"] = self.customer_number
        if self.identifier is not None:
            data["identifier"] = self.identifier
        if self.ovt is not None:
            data["ovt"] = self.ovt
        if self.invoice_channel is not None:
            data["invoiceChannel"] = self.invoice_channel.value
        if self.contact_person is not None:
            data["contactPerson"] = self.contact_person
        if self.language is not None:
            data["language"] = self.language.value
        if self.email is not None:
            data["email"] = self.email
        if self.einvoice_operator is not None:
            data["einvoiceOperator"] = self.einvoice_operator
        if self.einvoice_address is not None:
            data["einvoiceAddress"] = self.einvoice_address

        return data

    @classmethod
    def from_dict(cls, data) -> "InvoicingInfo":
        params = {}
        if "customerNumber" in data:
            params["customer_number"] = data["customerNumber"]
        if "identifier" in data:
            params["identifier"] = data["identifier"]
        if "ovt" in data:
            params["ovt"] = data["ovt"]
        if "invoiceChannel" in data:
            params["invoice_channel"] = InvoiceChannel(data["invoiceChannel"])
        if "contactPerson" in data:
            params["contact_person"] = data["contactPerson"]
        if "language" in data:
            params["language"] = InvoiceLanguage(data["language"])
        if "email" in data:
            params["email"] = data["email"]
        if "einvoiceOperator" in data:
            params["einvoice_operator"] = data["einvoiceOperator"]
        if "einvoiceAddress" in data:
            params["einvoice_address"] = data["einvoiceAddress"]

        return cls(**params)


class BusinessPartner(ProcountorAPIObject):
    def __init__(
        self,
        name: str,
        partner_type: PartnerType,
        id: typing.Optional[int] = None,
        address: typing.Optional[BusinessPartnerAddress] = None,
        billing_address: typing.Optional[BusinessPartnerAddress] = None,
        delivery_address: typing.Optional[BusinessPartnerAddress] = None,
        invoicing_info: typing.Optional[InvoicingInfo] = None,
        payment_info: typing.Optional[BusinessPartnerPaymentInfo] = None,
        registry_info: typing.Optional[Dict] = None,
        version: typing.Optional[int] = None,
    ):
        self.name = name
        self.partner_type = partner_type
        self.id = id
        self.address = address
        self.billing_address = billing_address
        self.delivery_address = delivery_address
        self.invoicing_info = invoicing_info
        self.payment_info = payment_info
        self.registry_info = registry_info
        self.version = version

    def as_dict(self) -> typing.Dict:
        data = {
            "name": self.name,
            "partner_type": self.partner_type,
        }

        if self.id is not None:
            data["id"] = self.id
        if self.address is not None:
            data["address"] = self.address
        if self.billing_address is not None:
            data["billingAddress"] = self.billing_address
        if self.delivery_address is not None:
            data["deliveryAddress"] = self.delivery_address
        if self.invoicing_info is not None:
            data["invoicingInfo"] = self.invoicing_info
        if self.payment_info is not None:
            data["paymentInfo"] = self.payment_info
        if self.registry_info is not None:
            data["registryInfo"] = self.registry_info
        if self.version is not None:
            data["version"] = self.version

        return data

    @classmethod
    def from_dict(cls, data) -> "BusinessPartner":
        params = {
           "name": data["name"],
           "partner_type": data["type"],
        }

        if "id" in data:
            params["id"] = data["id"]
        if "address" in data:
            params["address"] = BusinessPartnerAddress.from_dict(data["address"])
        if "billingAddress" in data:
            params["billing_address"] = BusinessPartnerAddress.from_dict(data["billingAddress"])
        if "deliveryAddress" in data and data["deliveryAddress"]:
            params["delivery_address"] = BusinessPartnerAddress.from_dict(data["deliveryAddress"])
        if "invoicingInfo" in data:
            params["invoicing_info"] = InvoicingInfo.from_dict(data["invoicingInfo"])
        if "paymentInfo" in data:
            params["payment_info"] = BusinessPartnerPaymentInfo.from_dict(data["paymentInfo"])
        if "registryInfo" in data:
            params["registry_info"] = data["registryInfo"]
        if "version" in data:
            params["version"] = data["version"]
        return cls(**params)


class Product(ProcountorAPIObject):
    def __init__(
        self,
        type: ProductType,
        name: str,
        discount: Decimal,
        price: Decimal,
        active: bool,
        currency: Currency,
        id: typing.Optional[int] = None,
        code: typing.Optional[str] = None,
        unit: typing.Optional[Unit] = None,
        vat: typing.Optional[Decimal] = None,
        default_account: typing.Optional[str] = None,
        vat_status: typing.Optional[int] = None,
        product_group_id: typing.Optional[int] = None
    ):
        self.id = id
        self.type = type
        self.name = name
        self.code = code
        self.unit = unit
        self.discount = discount
        self.price = price
        self.vat = vat
        self.active = active
        self.default_account = default_account
        self.vat_status = vat_status
        self.currency = currency
        self.product_group_id = product_group_id

    def as_dict(self) -> typing.Dict:
        data = {
            "type": self.type.value,
            "name": self.name,
            "discount": self.discount,
            "price": self.price,
            "active": self.active,
            "currency": self.currency.value,
        }

        if self.id is not None:
            data["id"] = self.id
        if self.code is not None:
            data["code"] = self.code
        if self.unit is not None:
            data["unit"] = self.unit.value
        if self.vat is not None:
            data["vat"] = self.vat
        if self.default_account is not None:
            data["defaultAccount"] = self.default_account
        if self.vat_status is not None:
            data["vatStatus"] = self.vat_status
        if self.product_group_id:
            data["productGroupId"] = self.product_group_id

        return data

    @classmethod
    def from_dict(cls, data) -> "Product":
        params = {
           "type": ProductType(data["type"]),
           "name": data["name"],
           "discount": data["discount"],
           "price": data["price"],
           "active": data["active"],
           "currency": Currency(data["currency"]),
        }

        if "id" in data:
            params["id"] = data["id"]
        if "code" in data:
            params["code"] = data["code"]
        if "unit" in data:
            params["unit"] = Unit(data["unit"])
        if "vat" in data:
            params["vat"] = data["vat"]
        if "defaultAccount" in data:
            params["default_account"] = data["defaultAccount"]
        if "vatStatus" in data:
            params["vat_status"] = data["vatStatus"]
        if "productGroupId" in data:
            params["product_group_id"] = data["productGroupId"]

        return cls(**params)


class ProductGroup(ProcountorAPIObject):
    def __init__(
        self,
        id: int,
        name: str,
        type: ProductType,
    ):
        self.id = id
        self.name = name
        self.type = type
        super().__init__()

    def as_dict(self) -> typing.Dict:
        data = {
            "id": self.id,
            "name": self.name,
            "type": self.type.value
        }
        return data

    @classmethod
    def from_dict(cls, data) -> "ProductGroup":
        params = {
            "id": data["id"],
            "name": data["name"],
            "type": ProductType(data["type"])
        }
        return cls(**params)


class DimensionItem(ProcountorAPIObject):
    def __init__(
        self,
        id: int,
        code_name: str,
        status: typing.Optional[DimensionItemStatus] = None,
        description: typing.Optional[str] = None,
    ):
        self.id: int = id
        self.code_name: str = code_name
        self.status: typing.Optional[DimensionItemStatus] = status
        self.description: typing.Optional[str] = description

    def as_dict(self) -> typing.Dict:
        data = {
            "id": self.id,
            "codeName": self.code_name,
        }

        if self.status is not None:
            data["status"] = self.status.value
        if self.description is not None:
            data["description"] = self.description

        return data

    @classmethod
    def from_dict(cls, data) -> "DimensionItem":
        params = {
           "id": data["id"],
           "code_name": data["codeName"],
        }

        if "status" in data:
            params["status"] = DimensionItemStatus(data["status"])
        if "description" in data:
            params["description"] = data["description"]

        return cls(**params)


class Dimension(ProcountorAPIObject):
    def __init__(
        self,
        id: int,
        name: str,
        items: typing.List[DimensionItem],
    ):
        self.id: int = id
        self.name: str = name
        self.items: typing.List[DimensionItem] = items

    def as_dict(self) -> typing.Dict:
        data = {
            "id": self.id,
            "name": self.name,
            "items": [DimensionItem.as_dict(item) for item in self.items],
        }
        return data

    @classmethod
    def from_dict(cls, data) -> "Dimension":
        params = {
           "id": data["id"],
           "name": data["name"],
           "items": [DimensionItem.from_dict(item) for item in data.get("items", [])],
        }

        return cls(**params)


class LedgerAttachment(ProcountorAPIObject):
    def __init__(
        self,
        name: str,
        reference_type: AttachmentReferenceType,
        reference_id: int,
        send_with_invoice: bool,
        id: typing.Optional[int] = None,
        mime_type: typing.Optional[str] = None,
    ):
        self.id: typing.Optional[int] = id
        self.name: str = name
        self.reference_type: AttachmentReferenceType = reference_type
        self.reference_id: int = reference_id
        self.mime_type: typing.Optional[str] = mime_type
        self.send_with_invoice: bool = send_with_invoice

    def as_dict(self) -> typing.Dict:
        data = {
            "name": self.name,
            "referenceType": self.reference_type,
            "referenceId": self.reference_id,
            "sendWithInvoice": self.send_with_invoice,
        }

        if self.id is not None:
            data["id"] = self.id
        if self.mime_type is not None:
            data["mimeType"] = self.mime_type

        return data

    @classmethod
    def from_dict(cls, data) -> "LedgerAttachment":
        params = {
           "name": data["name"],
           "reference_type": data["referenceType"],
           "reference_id": data["referenceId"],
           "send_with_invoice": data["sendWithInvoice"],
        }

        if "id" in data:
            params["id"] = data["id"]
        if "mimeType" in data:
            params["mime_type"] = data["mimeType"]

        return cls(**params)


class DimensionItemValue(ProcountorAPIObject):
    def __init__(
        self,
        dimension_id: int,
        item_id: int,
        value: Decimal,
    ):
        self.dimension_id: int = dimension_id
        self.item_id: int = item_id
        self.value: Decimal = value

    def as_dict(self) -> typing.Dict:
        data = {
            "dimensionId": self.dimension_id,
            "itemId": self.item_id,
            "value": self.value,
        }

        return data

    @classmethod
    def from_dict(cls, data) -> "DimensionItemValue":
        params = {
           "dimension_id": data["dimensionId"],
           "item_id": data["itemId"],
           "value": data["value"],
        }

        return cls(**params)


class LedgerTransaction(ProcountorAPIObject):
    def __init__(
        self,
        transaction_type: TransactionType,
        account: str,
        accountingValue: Decimal,
        vatPercent: Decimal,
        id: typing.Optional[int] = None,
        vat_type: typing.Optional[LedgerReceiptVATType] = None,
        vat_status: typing.Optional[int] = None,
        description: typing.Optional[str] = None,
        balance_code: typing.Optional[str] = None,
        start_date: typing.Optional[str] = None,
        end_date: typing.Optional[str] = None,
        dimension_item_values: List[DimensionItemValue] = None,
    ):
        self.id: typing.Optional[int] = id
        self.transaction_type: TransactionType = transaction_type
        self.account: str = account
        self.accountingValue: Decimal = accountingValue
        self.vatPercent: Decimal = vatPercent
        self.vat_type: typing.Optional[LedgerReceiptVATType] = vat_type
        self.vat_status: typing.Optional[int] = vat_status
        self.description: typing.Optional[str] = description
        self.balance_code: typing.Optional[str] = balance_code
        self.start_date: typing.Optional[str] = start_date
        self.end_date: typing.Optional[str] = end_date
        self.dimension_item_values: List[DimensionItemValue] = dimension_item_values

    def as_dict(self) -> typing.Dict:
        data = {
            "transactionType": self.transaction_type.value,
            "account": self.account,
            "accountingValue": self.accountingValue,
            "vatPercent": self.vatPercent,
        }

        if self.id is not None:
            data["id"] = self.id
        if self.vat_type is not None:
            data["vatType"] = self.vat_type
        if self.vat_status is not None:
            data["vatStatus"] = self.vat_status
        if self.description is not None:
            data["description"] = self.description
        if self.balance_code is not None:
            data["balanceCode"] = self.balance_code
        if self.start_date is not None:
            data["startDate"] = self.start_date
        if self.end_date is not None:
            data["endDate"] = self.end_date
        if self.dimension_item_values is not None:
            data["dimensionItemValues"] = [x.as_dict() for x in self.dimension_item_values]

        return data

    @classmethod
    def from_dict(cls, data) -> "LedgerTransaction":
        params = {
           "transaction_type": TransactionType(data["transactionType"]),
           "account": data["account"],
           "accountingValue": data["accountingValue"],
           "vatPercent": data["vatPercent"],
        }

        if "id" in data:
            params["id"] = data["id"]
        if "vatType" in data:
            params["vat_type"] = data["vatType"]
        if "vatStatus" in data:
            params["vat_status"] = data["vatStatus"]
        if "description" in data:
            params["description"] = data["description"]
        if "balanceCode" in data:
            params["balance_code"] = data["balanceCode"]
        if "startDate" in data:
            params["start_date"] = data["startDate"]
        if "endDate" in data:
            params["end_date"] = data["endDate"]
        if "dimensionItemValues" in data:
            params["dimension_item_values"] = [
                DimensionItemValue.from_dict(d) for d in data["dimensionItemValues"]
            ]

        return cls(**params)

    def add_or_update_dimension_item_value(self, dimension_item_value: DimensionItemValue):
        self.dimension_item_values = [v for v in self.dimension_item_values
                                      if v.dimension_id != dimension_item_value.dimension_id] + [dimension_item_value,]


class LedgerReceipt(ProcountorAPIObject):
    def __init__(
        self,
        id: int,
        type: LedgerReceiptType,
        status: LedgerReceiptStatus,
        name: str,
        receipt_date: str,
        vat_type: LedgerReceiptVATType,
        vat_status: int,
        vat_processing: typing.Optional[Country] = None,
        invoice_id: typing.Optional[int] = None,
        receipt_number: typing.Optional[int] = None,
        invoice_notes: typing.Optional[str] = None,
        invoice_number: typing.Optional[int] = None,
        accountants_notes: typing.Optional[str] = None,
        transaction_description: typing.Optional[str] = None,
        receipt_validity: typing.Optional[str] = None,
        period_start_date: typing.Optional[str] = None,
        period_end_date: typing.Optional[str] = None,
        partner_code: typing.Optional[str] = None,
        version: typing.Optional[str] = None,
        transactions: List[LedgerTransaction] = None,
        attachments: List[LedgerAttachment] = None,
    ):
        self.id: int = id
        self.type: LedgerReceiptType = type
        self.status: LedgerReceiptStatus = status
        self.name: str = name
        self.receipt_date: str = receipt_date
        self.vat_type: LedgerReceiptVATType = vat_type
        self.vat_status: int = vat_status
        self.vat_processing: typing.Optional[Country] = vat_processing
        self.invoice_id: typing.Optional[int] = invoice_id
        self.receipt_number: typing.Optional[int] = receipt_number
        self.invoice_notes: typing.Optional[str] = invoice_notes
        self.invoice_number: typing.Optional[int] = invoice_number
        self.accountants_notes: typing.Optional[str] = accountants_notes
        self.transaction_description: typing.Optional[str] = transaction_description
        self.receipt_validity: typing.Optional[str] = receipt_validity
        self.period_start_date: typing.Optional[str] = period_start_date
        self.period_end_date: typing.Optional[str] = period_end_date
        self.partner_code: typing.Optional[str] = partner_code
        self.version: typing.Optional[str] = version
        self.transactions: List[LedgerTransaction] = transactions
        self.attachments: List[LedgerAttachment] = attachments

    def as_dict(self) -> typing.Dict:
        data = {
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "name": self.name,
            "receiptDate": self.receipt_date,
            "vatType": self.vat_type.value,
            "vatStatus": self.vat_status,
        }

        if self.vat_processing is not None:
            data["vatProcessing"] = self.vat_processing.value
        if self.invoice_id is not None:
            data["invoiceId"] = self.invoice_id
        if self.receipt_number is not None:
            data["receiptNumber"] = self.receipt_number
        if self.invoice_notes is not None:
            data["invoiceNotes"] = self.invoice_notes
        if self.invoice_number is not None:
            data["invoiceNumber"] = self.invoice_number
        if self.accountants_notes is not None:
            data["accountantsNotes"] = self.accountants_notes
        if self.transaction_description is not None:
            data["transactionDescription"] = self.transaction_description
        if self.receipt_validity is not None:
            data["receiptValidity"] = self.receipt_validity
        if self.period_start_date is not None:
            data["periodStartDate"] = self.period_start_date
        if self.period_end_date is not None:
            data["periodEndDate"] = self.period_end_date
        if self.partner_code is not None:
            data["partnerCode"] = self.partner_code
        if self.version is not None:
            data["version"] = self.version
        if self.transactions is not None:
            data["transactions"] = [t.as_dict() for t in self.transactions]
        if self.attachments is not None:
            data["attachments"] = self.attachments

        return data

    @classmethod
    def from_dict(cls, data) -> "LedgerReceipt":
        params = {
           "id": data["id"],
           "type": data["type"],
           "status": LedgerReceiptStatus(data["status"]),
           "name": data["name"],
           "receipt_date": data["receiptDate"],
           "vat_type": LedgerReceiptVATType(data["vatType"]),
           "vat_status": data["vatStatus"],
        }

        if "vatProcessing" in data:
            params["vat_processing"] = Country(data["vatProcessing"])
        if "invoiceId" in data:
            params["invoice_id"] = data["invoiceId"]
        if "receiptNumber" in data:
            params["receipt_number"] = data["receiptNumber"]
        if "invoiceNotes" in data:
            params["invoice_notes"] = data["invoiceNotes"]
        if "invoiceNumber" in data:
            params["invoice_number"] = data["invoiceNumber"]
        if "accountantsNotes" in data:
            params["accountants_notes"] = data["accountantsNotes"]
        if "transactionDescription" in data:
            params["transaction_description"] = data["transactionDescription"]
        if "receiptValidity" in data:
            params["receipt_validity"] = data["receiptValidity"]
        if "periodStartDate" in data:
            params["period_start_date"] = data["periodStartDate"]
        if "periodEndDate" in data:
            params["period_end_date"] = data["periodEndDate"]
        if "partnerCode" in data:
            params["partner_code"] = data["partnerCode"]
        if "version" in data:
            params["version"] = data["version"]
        if "transactions" in data:
            params["transactions"] = [LedgerTransaction.from_dict(d) for d in data.get("transactions", [])]
        if "attachments" in data:
            params["attachments"] = data["attachments"]

        return cls(**params)


class PensionInsurance(ProcountorAPIObject):
    def __init__(
        self,
        pension_insurance_type: PensionInsuranceType,
        pension_contract_id: typing.Optional[int] = None,
        version: typing.Optional[str] = None,
        id: typing.Optional[int] = None,
    ):
        self.id: typing.Optional[int] = id
        self.pension_insurance_type: PensionInsuranceType = pension_insurance_type
        self.pension_contract_id: typing.Optional[int] = pension_contract_id
        self.version: typing.Optional[str] = version

    def as_dict(self) -> typing.Dict:
        data = {
            "type": self.pension_insurance_type.value,
        }
        if self.pension_contract_id is not None:
            data["pensionContractId"] = self.pension_contract_id
        if self.version is not None:
            data["version"] = self.version
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "PensionInsurance":
        return cls(
            id=data.get("id", None),
            pension_insurance_type=PensionInsuranceType(data["type"]),
            pension_contract_id=data.get("pensionContractId", None),
            version=data.get("version", None),
        )


class AccidentInsurance(ProcountorAPIObject):
    def __init__(
        self,
        percent: Decimal,
        occupational_title_id: typing.Optional[str] = None,
        keva_occupational_title_id: typing.Optional[str] = None,
        accident_insurance_policy_id: typing.Optional[int] = None,
        version: typing.Optional[str] = None,
        id: typing.Optional[int] = None,
    ):
        self.id: typing.Optional[int] = id
        self.accident_insurance_policy_id: typing.Optional[int] = accident_insurance_policy_id
        self.percent: Decimal = percent
        self.occupational_title_id: typing.Optional[str] = occupational_title_id
        self.keva_occupational_title_id: typing.Optional[str] = keva_occupational_title_id
        self.version: typing.Optional[str] = version

    def as_dict(self) -> typing.Dict:
        data = {
            "percent": self.percent,
        }
        if self.occupational_title_id is not None:
            data["occupationalTitleId"] = self.occupational_title_id
        if self.keva_occupational_title_id is not None:
            data["kevaOccupationalTitleId"] = self.keva_occupational_title_id
        if self.accident_insurance_policy_id is not None:
            data["accidentInsurancePolicyId"] = self.accident_insurance_policy_id
        if self.version is not None:
            data["version"] = self.version
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "AccidentInsurance":
        return cls(
            id=data.get("id", None),
            accident_insurance_policy_id=data.get("accidentInsurancePolicyId", None),
            percent=data["percent"],
            occupational_title_id=data.get("occupationalTitleId", None),
            keva_occupational_title_id=data.get("kevaOccupationalTitleId", None),
            version=data.get("version", None),
        )


class InsurancesConfiguration(ProcountorAPIObject):
    def __init__(
        self,
        pension_insurance: PensionInsurance,
        accident_insurance: AccidentInsurance,
        pension_voluntarily_paid: bool,
        no_obligation_exception_types: typing.Optional[List[InsuranceNoObligationExceptionType]] = None,
        not_subject_exception_types: typing.Optional[List[InsuranceNotSubjectExceptionType]] = None,
    ):
        self.pension_insurance: PensionInsurance = pension_insurance
        self.accident_insurance: AccidentInsurance = accident_insurance
        self.pension_voluntarily_paid: bool = pension_voluntarily_paid
        self.no_obligation_exception_types: typing.Optional[
            List[InsuranceNoObligationExceptionType]
        ] = no_obligation_exception_types
        self.not_subject_exception_types: typing.Optional[
            List[InsuranceNotSubjectExceptionType]
        ] = not_subject_exception_types

    def as_dict(self) -> typing.Dict:
        data = {
            "pensionInsurance": self.pension_insurance.as_dict(),
            "accidentInsurance": self.accident_insurance.as_dict(),
            "pensionVoluntarilyPaid": self.pension_voluntarily_paid,
        }
        if self.no_obligation_exception_types is not None:
            data["noObligationExceptionTypes"] = [e.value for e in self.no_obligation_exception_types]
        if self.not_subject_exception_types is not None:
            data["notSubjectExceptionTypes"] = [e.value for e in self.not_subject_exception_types]
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "InsurancesConfiguration":
        no_obligation = None
        if "noObligationExceptionTypes" in data:
            no_obligation = [InsuranceNoObligationExceptionType(e) for e in data["noObligationExceptionTypes"]]
        not_subject = None
        if "notSubjectExceptionTypes" in data:
            not_subject = [InsuranceNotSubjectExceptionType(e) for e in data["notSubjectExceptionTypes"]]

        return cls(
            pension_insurance=PensionInsurance.from_dict(data["pensionInsurance"]),
            accident_insurance=AccidentInsurance.from_dict(data["accidentInsurance"]),
            pension_voluntarily_paid=data["pensionVoluntarilyPaid"],
            no_obligation_exception_types=no_obligation,
            not_subject_exception_types=not_subject,
        )


class IncomeConfiguration(ProcountorAPIObject):
    def __init__(
        self,
        base_salary_value: Decimal,
        base_salary_type: BaseSalaryType,
        base_salary_hours: Decimal,
        excluded_from_automated_withholding_percentage_request: bool,
        salary_channel: SalaryChannel,
        travel_expenses_special_handling: TravelExpensesSpecialHandling,
        id: typing.Optional[int] = None,
        compensation_for_work_base_salary_type_code: typing.Optional[int] = None,
        monthly_base_salary: typing.Optional[Decimal] = None,
        personal_hourly_salary: typing.Optional[Decimal] = None,
        earner_types: typing.Optional[List[EarnerType]] = None,
        tax_number: typing.Optional[str] = None,
        version: typing.Optional[str] = None,
    ):
        self.id: typing.Optional[int] = id
        self.base_salary_value: Decimal = base_salary_value
        self.base_salary_type: BaseSalaryType = base_salary_type
        self.base_salary_hours: Decimal = base_salary_hours
        self.compensation_for_work_base_salary_type_code: typing.Optional[
            int
        ] = compensation_for_work_base_salary_type_code
        self.monthly_base_salary: typing.Optional[Decimal] = monthly_base_salary
        self.personal_hourly_salary: typing.Optional[Decimal] = personal_hourly_salary
        self.travel_expenses_special_handling: TravelExpensesSpecialHandling = travel_expenses_special_handling
        self.earner_types: typing.Optional[List[EarnerType]] = earner_types
        self.tax_number: typing.Optional[str] = tax_number
        self.salary_channel: SalaryChannel = salary_channel
        self.excluded_from_automated_withholding_percentage_request: bool = (
            excluded_from_automated_withholding_percentage_request
        )
        self.version: typing.Optional[str] = version

    def as_dict(self) -> typing.Dict:
        data = {
            "baseSalaryValue": self.base_salary_value,
            "baseSalaryType": self.base_salary_type.value,
            "baseSalaryHours": self.base_salary_hours,
            "travelExpensesSpecialHandling": self.travel_expenses_special_handling.value,
            "salaryChannel": self.salary_channel.value,
            "excludedFromAutomatedWithholdingPercentageRequest": (
                self.excluded_from_automated_withholding_percentage_request
            ),
        }
        if self.compensation_for_work_base_salary_type_code is not None:
            data["compensationForWorkBaseSalaryTypeCode"] = self.compensation_for_work_base_salary_type_code
        if self.monthly_base_salary is not None:
            data["monthlyBaseSalary"] = self.monthly_base_salary
        if self.personal_hourly_salary is not None:
            data["personalHourlySalary"] = self.personal_hourly_salary
        if self.earner_types is not None:
            data["earnerTypes"] = [e.value for e in self.earner_types]
        if self.tax_number is not None:
            data["taxNumber"] = self.tax_number
        if self.version is not None:
            data["version"] = self.version
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "IncomeConfiguration":
        earner_types = None
        if "earnerTypes" in data:
            earner_types = [EarnerType(e) for e in data["earnerTypes"]]

        return cls(
            id=data.get("id", None),
            base_salary_value=data["baseSalaryValue"],
            base_salary_type=BaseSalaryType(data["baseSalaryType"]),
            base_salary_hours=data["baseSalaryHours"],
            compensation_for_work_base_salary_type_code=data.get("compensationForWorkBaseSalaryTypeCode", None),
            monthly_base_salary=data.get("monthlyBaseSalary", None),
            personal_hourly_salary=data.get("personalHourlySalary", None),
            travel_expenses_special_handling=TravelExpensesSpecialHandling(data["travelExpensesSpecialHandling"]),
            earner_types=earner_types,
            tax_number=data.get("taxNumber", None),
            salary_channel=SalaryChannel(data["salaryChannel"]),
            excluded_from_automated_withholding_percentage_request=data[
                "excludedFromAutomatedWithholdingPercentageRequest"
            ],
            version=data.get("version", None),
        )


class InternationalSituationsConfiguration(ProcountorAPIObject):
    def __init__(
        self,
        not_subject_to_withholding: bool,
        non_resident_tax_payer: bool,
        id: typing.Optional[int] = None,
        social_security_certificate: typing.Optional[SocialSecurityCertificate] = None,
        tax_identification_number: typing.Optional[str] = None,
        six_month_rule_applicability: typing.Optional[SixMonthRuleApplicability] = None,
        country: typing.Optional[Country] = None,
        version: typing.Optional[str] = None,
    ):
        self.id: typing.Optional[int] = id
        self.social_security_certificate: typing.Optional[SocialSecurityCertificate] = social_security_certificate
        self.not_subject_to_withholding: bool = not_subject_to_withholding
        self.non_resident_tax_payer: bool = non_resident_tax_payer
        self.tax_identification_number: typing.Optional[str] = tax_identification_number
        self.six_month_rule_applicability: typing.Optional[SixMonthRuleApplicability] = six_month_rule_applicability
        self.country: typing.Optional[Country] = country
        self.version: typing.Optional[str] = version

    def as_dict(self) -> typing.Dict:
        data = {
            "notSubjectToWithholding": self.not_subject_to_withholding,
            "nonResidentTaxPayer": self.non_resident_tax_payer,
        }
        if self.social_security_certificate is not None:
            data["socialSecurityCertificate"] = self.social_security_certificate.value
        if self.tax_identification_number is not None:
            data["taxIdentificationNumber"] = self.tax_identification_number
        if self.six_month_rule_applicability is not None:
            data["sixMonthRuleApplicability"] = self.six_month_rule_applicability.value
        if self.country is not None:
            data["country"] = self.country.value
        if self.version is not None:
            data["version"] = self.version
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "InternationalSituationsConfiguration":
        return cls(
            id=data.get("id", None),
            social_security_certificate=(
                SocialSecurityCertificate(data["socialSecurityCertificate"])
                if "socialSecurityCertificate" in data
                else None
            ),
            not_subject_to_withholding=data["notSubjectToWithholding"],
            non_resident_tax_payer=data["nonResidentTaxPayer"],
            tax_identification_number=data.get("taxIdentificationNumber", None),
            six_month_rule_applicability=(
                SixMonthRuleApplicability(data["sixMonthRuleApplicability"])
                if "sixMonthRuleApplicability" in data
                else None
            ),
            country=Country(data["country"]) if "country" in data else None,
            version=data.get("version", None),
        )


class AverageDailyActualWorkdays(ProcountorAPIObject):
    def __init__(
        self,
        actual_workdays_in_first_year: int,
        actual_workdays_in_second_year: typing.Optional[int] = None,
    ):
        self.actual_workdays_in_first_year: int = actual_workdays_in_first_year
        self.actual_workdays_in_second_year: typing.Optional[int] = actual_workdays_in_second_year

    def as_dict(self) -> typing.Dict:
        data = {
            "actualWorkdaysInFirstYear": self.actual_workdays_in_first_year,
        }
        if self.actual_workdays_in_second_year is not None:
            data["actualWorkdaysInSecondYear"] = self.actual_workdays_in_second_year
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "AverageDailyActualWorkdays":
        return cls(
            actual_workdays_in_first_year=data["actualWorkdaysInFirstYear"],
            actual_workdays_in_second_year=data.get("actualWorkdaysInSecondYear", None),
        )


class HolidaysWorkingTimeAllocation(ProcountorAPIObject):
    def __init__(
        self,
        working_time_in_first_month: float,
        working_time_in_second_month: typing.Optional[float] = None,
        working_time_type: typing.Optional[WorkingTimeType] = None,
        average_daily_actual_workdays: typing.Optional[AverageDailyActualWorkdays] = None,
    ):
        self.working_time_in_first_month: float = working_time_in_first_month
        self.working_time_in_second_month: typing.Optional[float] = working_time_in_second_month
        self.working_time_type: typing.Optional[WorkingTimeType] = working_time_type
        self.average_daily_actual_workdays: typing.Optional[AverageDailyActualWorkdays] = average_daily_actual_workdays

    def as_dict(self) -> typing.Dict:
        data = {
            "workingTimeInFirstMonth": self.working_time_in_first_month,
        }
        if self.working_time_in_second_month is not None:
            data["workingTimeInSecondMonth"] = self.working_time_in_second_month
        if self.working_time_type is not None:
            data["workingTimeType"] = self.working_time_type.value
        if self.average_daily_actual_workdays is not None:
            data["averageDailyActualWorkdays"] = self.average_daily_actual_workdays.as_dict()
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "HolidaysWorkingTimeAllocation":
        params = {
            "working_time_in_first_month": data["workingTimeInFirstMonth"],
        }
        if "workingTimeInSecondMonth" in data:
            params["working_time_in_second_month"] = data["workingTimeInSecondMonth"]
        if "workingTimeType" in data:
            params["working_time_type"] = WorkingTimeType(data["workingTimeType"])
        if "averageDailyActualWorkdays" in data and data["averageDailyActualWorkdays"]:
            params["average_daily_actual_workdays"] = AverageDailyActualWorkdays.from_dict(
                data["averageDailyActualWorkdays"]
            )
        return cls(**params)


class WorkingHourReductionWorkingTimeAllocation(ProcountorAPIObject):
    def __init__(
        self,
        working_days_in_first_year: float,
        working_days_in_second_year: typing.Optional[float] = None,
    ):
        self.working_days_in_first_year: float = working_days_in_first_year
        self.working_days_in_second_year: typing.Optional[float] = working_days_in_second_year

    def as_dict(self) -> typing.Dict:
        data = {
            "workingDaysInFirstYear": self.working_days_in_first_year,
        }
        if self.working_days_in_second_year is not None:
            data["workingDaysInSecondYear"] = self.working_days_in_second_year
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "WorkingHourReductionWorkingTimeAllocation":
        return cls(
            working_days_in_first_year=data["workingDaysInFirstYear"],
            working_days_in_second_year=data.get("workingDaysInSecondYear", None),
        )


class SalarySlipWorkingTimeAllocation(ProcountorAPIObject):
    def __init__(
        self,
        holidays_working_time: typing.Optional[HolidaysWorkingTimeAllocation] = None,
        working_hour_reduction_working_days: typing.Optional[WorkingHourReductionWorkingTimeAllocation] = None,
    ):
        self.holidays_working_time: typing.Optional[HolidaysWorkingTimeAllocation] = holidays_working_time
        self.working_hour_reduction_working_days: typing.Optional[
            WorkingHourReductionWorkingTimeAllocation
        ] = working_hour_reduction_working_days

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.holidays_working_time is not None:
            data["holidaysWorkingTime"] = self.holidays_working_time.as_dict()
        if self.working_hour_reduction_working_days is not None:
            data["workingHourReductionWorkingDays"] = self.working_hour_reduction_working_days.as_dict()
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalarySlipWorkingTimeAllocation":
        params = {}
        if "holidaysWorkingTime" in data and data["holidaysWorkingTime"]:
            params["holidays_working_time"] = HolidaysWorkingTimeAllocation.from_dict(
                data["holidaysWorkingTime"]
            )
        if "workingHourReductionWorkingDays" in data and data["workingHourReductionWorkingDays"]:
            params["working_hour_reduction_working_days"] = WorkingHourReductionWorkingTimeAllocation.from_dict(
                data["workingHourReductionWorkingDays"]
            )
        return cls(**params)


class SalaryBaseRowDimensionItem(ProcountorAPIObject):
    def __init__(
        self,
        id: int,
        name: typing.Optional[str] = None,
        quantity: typing.Optional[float] = None,
        percentage: typing.Optional[float] = None,
    ):
        self.id: int = id
        self.name: typing.Optional[str] = name
        self.quantity: typing.Optional[float] = quantity
        self.percentage: typing.Optional[float] = percentage

    def as_dict(self) -> typing.Dict:
        data = {
            "id": self.id,
        }
        if self.name is not None:
            data["name"] = self.name
        if self.quantity is not None:
            data["quantity"] = self.quantity
        if self.percentage is not None:
            data["percentage"] = self.percentage
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalaryBaseRowDimensionItem":
        return cls(
            id=data["id"],
            name=data.get("name", None),
            quantity=data.get("quantity", None),
            percentage=data.get("percentage", None),
        )


class SalaryBaseRowDimension(ProcountorAPIObject):
    def __init__(
        self,
        dimension_id: int,
        items: List[SalaryBaseRowDimensionItem],
        dimension_name: typing.Optional[str] = None,
    ):
        self.dimension_id: int = dimension_id
        self.dimension_name: typing.Optional[str] = dimension_name
        self.items: List[SalaryBaseRowDimensionItem] = items

    def as_dict(self) -> typing.Dict:
        data = {
            "dimensionId": self.dimension_id,
            "items": [item.as_dict() for item in self.items],
        }
        if self.dimension_name is not None:
            data["dimensionName"] = self.dimension_name
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalaryBaseRowDimension":
        return cls(
            dimension_id=data["dimensionId"],
            dimension_name=data.get("dimensionName", None),
            items=[SalaryBaseRowDimensionItem.from_dict(item) for item in data.get("items", [])],
        )


class HolidayRowDetails(ProcountorAPIObject):
    def __init__(
        self,
        holiday_credit_year: typing.Optional[int] = None,
        holiday_pay_percentage: typing.Optional[float] = None,
        holiday_days_spent: typing.Optional[int] = None,
        holiday_bonus_calculation_basis: typing.Optional[HolidayBonusCalculationBasis] = None,
        correction: typing.Optional[bool] = None,
    ):
        self.holiday_credit_year: typing.Optional[int] = holiday_credit_year
        self.holiday_pay_percentage: typing.Optional[float] = holiday_pay_percentage
        self.holiday_days_spent: typing.Optional[int] = holiday_days_spent
        self.holiday_bonus_calculation_basis: typing.Optional[
            HolidayBonusCalculationBasis
        ] = holiday_bonus_calculation_basis
        self.correction: typing.Optional[bool] = correction

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.holiday_credit_year is not None:
            data["holidayCreditYear"] = self.holiday_credit_year
        if self.holiday_pay_percentage is not None:
            data["holidayPayPercentage"] = self.holiday_pay_percentage
        if self.holiday_days_spent is not None:
            data["holidayDaysSpent"] = self.holiday_days_spent
        if self.holiday_bonus_calculation_basis is not None:
            data["holidayBonusCalculationBasis"] = self.holiday_bonus_calculation_basis.value
        if self.correction is not None:
            data["correction"] = self.correction
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "HolidayRowDetails":
        params = {}
        if "holidayCreditYear" in data:
            params["holiday_credit_year"] = data["holidayCreditYear"]
        if "holidayPayPercentage" in data:
            params["holiday_pay_percentage"] = data["holidayPayPercentage"]
        if "holidayDaysSpent" in data:
            params["holiday_days_spent"] = data["holidayDaysSpent"]
        if "holidayBonusCalculationBasis" in data:
            params["holiday_bonus_calculation_basis"] = HolidayBonusCalculationBasis(
                data["holidayBonusCalculationBasis"]
            )
        if "correction" in data:
            params["correction"] = data["correction"]
        return cls(**params)


class WorkingHourReductionRowDetails(ProcountorAPIObject):
    def __init__(
        self,
        year: typing.Optional[int] = None,
    ):
        self.year: typing.Optional[int] = year

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.year is not None:
            data["year"] = self.year
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "WorkingHourReductionRowDetails":
        return cls(
            year=data.get("year", None),
        )


class SalarySlipRecoveryRowDetails(ProcountorAPIObject):
    def __init__(
        self,
        payment_period_start: str,
        payment_period_end: str,
        id: typing.Optional[int] = None,
        net_recovery_tax_value: typing.Optional[float] = None,
        earnings_period_start: typing.Optional[str] = None,
        earnings_period_end: typing.Optional[str] = None,
        payday: typing.Optional[str] = None,
        tax_at_source_value: typing.Optional[float] = None,
    ):
        self.id: typing.Optional[int] = id
        self.net_recovery_tax_value: typing.Optional[float] = net_recovery_tax_value
        self.payment_period_start: str = payment_period_start
        self.payment_period_end: str = payment_period_end
        self.earnings_period_start: typing.Optional[str] = earnings_period_start
        self.earnings_period_end: typing.Optional[str] = earnings_period_end
        self.payday: typing.Optional[str] = payday
        self.tax_at_source_value: typing.Optional[float] = tax_at_source_value

    def as_dict(self) -> typing.Dict:
        data = {
            "paymentPeriodStart": self.payment_period_start,
            "paymentPeriodEnd": self.payment_period_end,
        }
        if self.id is not None:
            data["id"] = self.id
        if self.net_recovery_tax_value is not None:
            data["netRecoveryTaxValue"] = self.net_recovery_tax_value
        if self.earnings_period_start is not None:
            data["earningsPeriodStart"] = self.earnings_period_start
        if self.earnings_period_end is not None:
            data["earningsPeriodEnd"] = self.earnings_period_end
        if self.payday is not None:
            data["payday"] = self.payday
        if self.tax_at_source_value is not None:
            data["taxAtSourceValue"] = self.tax_at_source_value
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalarySlipRecoveryRowDetails":
        return cls(
            id=data.get("id", None),
            net_recovery_tax_value=data.get("netRecoveryTaxValue", None),
            payment_period_start=data["paymentPeriodStart"],
            payment_period_end=data["paymentPeriodEnd"],
            earnings_period_start=data.get("earningsPeriodStart", None),
            earnings_period_end=data.get("earningsPeriodEnd", None),
            payday=data.get("payday", None),
            tax_at_source_value=data.get("taxAtSourceValue", None),
        )


class SalarySlipCarBenefitRowDetails(ProcountorAPIObject):
    def __init__(
        self,
        car_age_group: CarAgeGroup,
        benefit_limited: bool,
        id: typing.Optional[int] = None,
        emission_value: typing.Optional[float] = None,
        odometer_reading: typing.Optional[int] = None,
    ):
        self.id: typing.Optional[int] = id
        self.car_age_group: CarAgeGroup = car_age_group
        self.benefit_limited: bool = benefit_limited
        self.emission_value: typing.Optional[float] = emission_value
        self.odometer_reading: typing.Optional[int] = odometer_reading

    def as_dict(self) -> typing.Dict:
        data = {
            "carAgeGroup": self.car_age_group.value,
            "benefitLimited": self.benefit_limited,
        }
        if self.id is not None:
            data["id"] = self.id
        if self.emission_value is not None:
            data["emissionValue"] = self.emission_value
        if self.odometer_reading is not None:
            data["odometerReading"] = self.odometer_reading
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalarySlipCarBenefitRowDetails":
        return cls(
            id=data.get("id", None),
            car_age_group=CarAgeGroup(data["carAgeGroup"]),
            benefit_limited=data["benefitLimited"],
            emission_value=data.get("emissionValue", None),
            odometer_reading=data.get("odometerReading", None),
        )


class SalarySlipRow(ProcountorAPIObject):
    def __init__(
        self,
        salary_type_code: int,
        show_earning_period_in_export: bool,
        unjust_enrichment: bool,
        id: typing.Optional[int] = None,
        custom_name: typing.Optional[str] = None,
        quantity: typing.Optional[float] = None,
        unit_value: typing.Optional[float] = None,
        payment_percent: typing.Optional[float] = None,
        recovery_details: typing.Optional[SalarySlipRecoveryRowDetails] = None,
        car_benefit_details: typing.Optional[SalarySlipCarBenefitRowDetails] = None,
        base_salary_row: typing.Optional[bool] = None,
        dimensions: typing.Optional[List[SalaryBaseRowDimension]] = None,
        earnings_period_start: typing.Optional[str] = None,
        earnings_period_end: typing.Optional[str] = None,
        comment: typing.Optional[str] = None,
        holiday_row_details: typing.Optional[HolidayRowDetails] = None,
        working_hour_reduction_row_details: typing.Optional[WorkingHourReductionRowDetails] = None,
        system_notification: typing.Optional[str] = None,
    ):
        self.id: typing.Optional[int] = id
        self.salary_type_code: int = salary_type_code
        self.custom_name: typing.Optional[str] = custom_name
        self.quantity: typing.Optional[float] = quantity
        self.unit_value: typing.Optional[float] = unit_value
        self.payment_percent: typing.Optional[float] = payment_percent
        self.recovery_details: typing.Optional[SalarySlipRecoveryRowDetails] = recovery_details
        self.car_benefit_details: typing.Optional[SalarySlipCarBenefitRowDetails] = car_benefit_details
        self.base_salary_row: typing.Optional[bool] = base_salary_row
        self.dimensions: typing.Optional[List[SalaryBaseRowDimension]] = dimensions
        self.earnings_period_start: typing.Optional[str] = earnings_period_start
        self.earnings_period_end: typing.Optional[str] = earnings_period_end
        self.show_earning_period_in_export: bool = show_earning_period_in_export
        self.unjust_enrichment: bool = unjust_enrichment
        self.comment: typing.Optional[str] = comment
        self.holiday_row_details: typing.Optional[HolidayRowDetails] = holiday_row_details
        self.working_hour_reduction_row_details: typing.Optional[
            WorkingHourReductionRowDetails
        ] = working_hour_reduction_row_details
        self.system_notification: typing.Optional[str] = system_notification

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.id is not None:
            data["id"] = self.id
        data["salaryTypeCode"] = self.salary_type_code
        if self.quantity is not None:
            data["quantity"] = self.quantity
        if self.unit_value is not None:
            data["unitValue"] = self.unit_value
        if self.payment_percent is not None:
            data["paymentPercent"] = self.payment_percent
        if self.base_salary_row is not None:
            data["baseSalaryRow"] = self.base_salary_row
        data["unjustEnrichment"] = self.unjust_enrichment
        if self.custom_name is not None:
            data["customName"] = self.custom_name
        data["showEarningPeriodInExport"] = self.show_earning_period_in_export
        if self.dimensions is not None:
            data["dimensions"] = [d.as_dict() for d in self.dimensions]
        if self.recovery_details is not None:
            data["recoveryDetails"] = self.recovery_details.as_dict()
        if self.car_benefit_details is not None:
            data["carBenefitDetails"] = self.car_benefit_details.as_dict()
        if self.earnings_period_start is not None:
            data["earningsPeriodStart"] = self.earnings_period_start
        if self.earnings_period_end is not None:
            data["earningsPeriodEnd"] = self.earnings_period_end
        if self.comment is not None:
            data["comment"] = self.comment
        if self.holiday_row_details is not None:
            data["holidayRowDetails"] = self.holiday_row_details.as_dict()
        if self.working_hour_reduction_row_details is not None:
            data["workingHourReductionRowDetails"] = self.working_hour_reduction_row_details.as_dict()
        if self.system_notification is not None:
            data["systemNotification"] = self.system_notification
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalarySlipRow":
        params = {
            "salary_type_code": data["salaryTypeCode"],
            "show_earning_period_in_export": data["showEarningPeriodInExport"],
            "unjust_enrichment": data["unjustEnrichment"],
        }
        if "id" in data:
            params["id"] = data["id"]
        if "customName" in data:
            params["custom_name"] = data["customName"]
        if "quantity" in data:
            params["quantity"] = data["quantity"]
        if "unitValue" in data:
            params["unit_value"] = data["unitValue"]
        if "paymentPercent" in data:
            params["payment_percent"] = data["paymentPercent"]
        if "recoveryDetails" in data and data["recoveryDetails"]:
            params["recovery_details"] = SalarySlipRecoveryRowDetails.from_dict(data["recoveryDetails"])
        if "carBenefitDetails" in data and data["carBenefitDetails"]:
            params["car_benefit_details"] = SalarySlipCarBenefitRowDetails.from_dict(data["carBenefitDetails"])
        if "baseSalaryRow" in data:
            params["base_salary_row"] = data["baseSalaryRow"]
        if "dimensions" in data and data["dimensions"]:
            params["dimensions"] = [SalaryBaseRowDimension.from_dict(d) for d in data["dimensions"]]
        if "earningsPeriodStart" in data:
            params["earnings_period_start"] = data["earningsPeriodStart"]
        if "earningsPeriodEnd" in data:
            params["earnings_period_end"] = data["earningsPeriodEnd"]
        if "comment" in data:
            params["comment"] = data["comment"]
        if "holidayRowDetails" in data and data["holidayRowDetails"]:
            params["holiday_row_details"] = HolidayRowDetails.from_dict(data["holidayRowDetails"])
        if "workingHourReductionRowDetails" in data and data["workingHourReductionRowDetails"]:
            params["working_hour_reduction_row_details"] = WorkingHourReductionRowDetails.from_dict(
                data["workingHourReductionRowDetails"]
            )
        if "systemNotification" in data:
            params["system_notification"] = data["systemNotification"]
        return cls(**params)


class SalarySlipSettings(ProcountorAPIObject):
    def __init__(
        self,
        pension_voluntarily_paid: bool,
        accounting_date: str,
        due_date: str,
        salary_channel: SalaryChannel,
        no_obligation_exception_types: typing.Optional[List[InsuranceNoObligationExceptionType]] = None,
        not_subject_exception_types: typing.Optional[List[InsuranceNotSubjectExceptionType]] = None,
        additional_information: typing.Optional[str] = None,
    ):
        self.no_obligation_exception_types: typing.Optional[
            List[InsuranceNoObligationExceptionType]
        ] = no_obligation_exception_types
        self.not_subject_exception_types: typing.Optional[
            List[InsuranceNotSubjectExceptionType]
        ] = not_subject_exception_types
        self.pension_voluntarily_paid: bool = pension_voluntarily_paid
        self.accounting_date: str = accounting_date
        self.due_date: str = due_date
        self.salary_channel: SalaryChannel = salary_channel
        self.additional_information: typing.Optional[str] = additional_information

    def as_dict(self) -> typing.Dict:
        data = {
            "pensionVoluntarilyPaid": self.pension_voluntarily_paid,
            "accountingDate": self.accounting_date,
            "dueDate": self.due_date,
            "salaryChannel": self.salary_channel.value,
        }
        if self.no_obligation_exception_types is not None:
            data["noObligationExceptionTypes"] = [e.value for e in self.no_obligation_exception_types]
        if self.not_subject_exception_types is not None:
            data["notSubjectExceptionTypes"] = [e.value for e in self.not_subject_exception_types]
        if self.additional_information is not None:
            data["additionalInformation"] = self.additional_information
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalarySlipSettings":
        params = {
            "pension_voluntarily_paid": data["pensionVoluntarilyPaid"],
            "accounting_date": data["accountingDate"],
            "due_date": data["dueDate"],
            "salary_channel": SalaryChannel(data["salaryChannel"]),
        }
        if "noObligationExceptionTypes" in data and data["noObligationExceptionTypes"]:
            params["no_obligation_exception_types"] = [
                InsuranceNoObligationExceptionType(e) for e in data["noObligationExceptionTypes"]
            ]
        if "notSubjectExceptionTypes" in data and data["notSubjectExceptionTypes"]:
            params["not_subject_exception_types"] = [
                InsuranceNotSubjectExceptionType(e) for e in data["notSubjectExceptionTypes"]
            ]
        if "additionalInformation" in data:
            params["additional_information"] = data["additionalInformation"]
        return cls(**params)


class SalarySlipEmployment(ProcountorAPIObject):
    def __init__(
        self,
        termination_reason: EmploymentTerminationReason,
        start_date: typing.Optional[str] = None,
        end_date: typing.Optional[str] = None,
        type: typing.Optional[EmploymentType_] = None,
        registration_ground_id: typing.Optional[str] = None,
        hours_per_week: typing.Optional[float] = None,
        employment_type: typing.Optional[EmploymentWorkType] = None,
        part_time_percent: typing.Optional[float] = None,
    ):
        self.start_date: typing.Optional[str] = start_date
        self.end_date: typing.Optional[str] = end_date
        self.type: typing.Optional[EmploymentType_] = type
        self.termination_reason: EmploymentTerminationReason = termination_reason
        self.registration_ground_id: typing.Optional[str] = registration_ground_id
        self.hours_per_week: typing.Optional[float] = hours_per_week
        self.employment_type: typing.Optional[EmploymentWorkType] = employment_type
        self.part_time_percent: typing.Optional[float] = part_time_percent

    def as_dict(self) -> typing.Dict:
        data = {
            "terminationReason": self.termination_reason.value,
        }
        if self.start_date is not None:
            data["startDate"] = self.start_date
        if self.end_date is not None:
            data["endDate"] = self.end_date
        if self.type is not None:
            data["type"] = self.type.value
        if self.registration_ground_id is not None:
            data["registrationGroundId"] = self.registration_ground_id
        if self.hours_per_week is not None:
            data["hoursPerWeek"] = self.hours_per_week
        if self.employment_type is not None:
            data["employmentType"] = self.employment_type.value
        if self.part_time_percent is not None:
            data["partTimePercent"] = self.part_time_percent
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalarySlipEmployment":
        params = {
            "termination_reason": EmploymentTerminationReason(data["terminationReason"]),
        }
        if "startDate" in data:
            params["start_date"] = data["startDate"]
        if "endDate" in data:
            params["end_date"] = data["endDate"]
        if "type" in data:
            params["type"] = EmploymentType_(data["type"])
        if "registrationGroundId" in data:
            params["registration_ground_id"] = data["registrationGroundId"]
        if "hoursPerWeek" in data:
            params["hours_per_week"] = data["hoursPerWeek"]
        if "employmentType" in data:
            params["employment_type"] = EmploymentWorkType(data["employmentType"])
        if "partTimePercent" in data:
            params["part_time_percent"] = data["partTimePercent"]
        return cls(**params)


class SalarySlipAdjustments(ProcountorAPIObject):
    def __init__(
        self,
        payday: str,
        employment: typing.Optional[SalarySlipEmployment] = None,
        pension_contract_id: typing.Optional[int] = None,
        accident_insurance_policy_id: typing.Optional[int] = None,
    ):
        self.payday: str = payday
        self.employment: typing.Optional[SalarySlipEmployment] = employment
        self.pension_contract_id: typing.Optional[int] = pension_contract_id
        self.accident_insurance_policy_id: typing.Optional[int] = accident_insurance_policy_id

    def as_dict(self) -> typing.Dict:
        data = {
            "payday": self.payday,
        }
        if self.employment is not None:
            data["employment"] = self.employment.as_dict()
        if self.pension_contract_id is not None:
            data["pensionContractId"] = self.pension_contract_id
        if self.accident_insurance_policy_id is not None:
            data["accidentInsurancePolicyId"] = self.accident_insurance_policy_id
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalarySlipAdjustments":
        params = {
            "payday": data["payday"],
        }
        if "employment" in data and data["employment"]:
            params["employment"] = SalarySlipEmployment.from_dict(data["employment"])
        if "pensionContractId" in data:
            params["pension_contract_id"] = data["pensionContractId"]
        if "accidentInsurancePolicyId" in data:
            params["accident_insurance_policy_id"] = data["accidentInsurancePolicyId"]
        return cls(**params)


class SalarySlip(ProcountorAPIObject):
    def __init__(
        self,
        id: int,
        rows: typing.Optional[List[SalarySlipRow]] = None,
        settings: typing.Optional[SalarySlipSettings] = None,
        adjustments: SalarySlipAdjustments = None,
        incomes_register_reporting_setting: IncomesRegisterReportingSetting = None,
        employee_id: typing.Optional[int] = None,
        employee_name: typing.Optional[str] = None,
        status: typing.Optional[SalarySlipStatus] = None,
        paid_status_details: typing.Optional[SalarySlipPaidStatusDetails] = None,
        slip_number: typing.Optional[int] = None,
        salary_base_note: typing.Optional[str] = None,
        working_time_allocation: typing.Optional[SalarySlipWorkingTimeAllocation] = None,
        slip_notes: typing.Optional[str] = None,
        version: typing.Optional[str] = None,
        payday: typing.Optional[str] = None,
        sent_status: typing.Optional[str] = None,
        report_status: typing.Optional[str] = None,
        salary: typing.Optional[Decimal] = None,
        fringe_benefit: typing.Optional[Decimal] = None,
        salary_for_ins: typing.Optional[Decimal] = None,
        deduction_to_taxable: typing.Optional[Decimal] = None,
        tax: typing.Optional[Decimal] = None,
        taxable_compensation: typing.Optional[Decimal] = None,
        tax_free_items: typing.Optional[Decimal] = None,
        other_deductions: typing.Optional[Decimal] = None,
        net_pay: typing.Optional[Decimal] = None,
        esalary_status: typing.Optional[str] = None,
    ):
        self.id: typing.Optional[int] = id
        self.employee_id: typing.Optional[int] = employee_id
        self.employee_name: typing.Optional[str] = employee_name
        self.status: typing.Optional[SalarySlipStatus] = status
        self.paid_status_details: typing.Optional[SalarySlipPaidStatusDetails] = paid_status_details
        self.slip_number: typing.Optional[int] = slip_number
        self.salary_base_note: typing.Optional[str] = salary_base_note
        self.incomes_register_reporting_setting: IncomesRegisterReportingSetting = incomes_register_reporting_setting
        self.working_time_allocation: typing.Optional[SalarySlipWorkingTimeAllocation] = working_time_allocation
        self.rows: List[SalarySlipRow] = rows
        self.settings: SalarySlipSettings = settings
        self.adjustments: SalarySlipAdjustments = adjustments
        self.slip_notes: typing.Optional[str] = slip_notes
        self.version: typing.Optional[str] = version
        self.payday: typing.Optional[str] = payday
        self.sent_status: typing.Optional[str] = sent_status
        self.report_status: typing.Optional[str] = report_status
        self.salary: typing.Optional[Decimal] = salary
        self.fringe_benefit: typing.Optional[Decimal] = fringe_benefit
        self.salary_for_ins: typing.Optional[Decimal] = salary_for_ins
        self.deduction_to_taxable: typing.Optional[Decimal] = deduction_to_taxable
        self.tax: typing.Optional[Decimal] = tax
        self.taxable_compensation: typing.Optional[Decimal] = taxable_compensation
        self.tax_free_items: typing.Optional[Decimal] = tax_free_items
        self.other_deductions: typing.Optional[Decimal] = other_deductions
        self.net_pay: typing.Optional[Decimal] = net_pay
        self.esalary_status: typing.Optional[str] = esalary_status

    def as_dict(self) -> typing.Dict:
        data = {
            "id": self.id,
        }
        if self.rows is not None:
            data["rows"] = [row.as_dict() for row in self.rows]
        if self.settings is not None:
            data["settings"] = self.settings.as_dict()
        if self.adjustments is not None:
            data["adjustments"] = self.adjustments.as_dict()
        if self.incomes_register_reporting_setting:
            data["incomesRegisterReportingSetting"] = self.incomes_register_reporting_setting.value
        if self.employee_id is not None:
            data["employeeId"] = self.employee_id
        if self.employee_name is not None:
            data["employeeName"] = self.employee_name
        if self.status is not None:
            data["status"] = self.status.value
        if self.paid_status_details is not None:
            data["paidStatusDetails"] = self.paid_status_details.value
        if self.slip_number is not None:
            data["slipNumber"] = self.slip_number
        if self.salary_base_note is not None:
            data["salaryBaseNote"] = self.salary_base_note
        if self.working_time_allocation is not None:
            data["workingTimeAllocation"] = self.working_time_allocation.as_dict()
        if self.slip_notes is not None:
            data["slipNotes"] = self.slip_notes
        if self.version is not None:
            data["version"] = self.version
        if self.payday is not None:
            data["payday"] = self.payday
        if self.sent_status is not None:
            data["sentStatus"] = self.sent_status
        if self.report_status is not None:
            data["reportStatus"] = self.report_status
        if self.salary is not None:
            data["salary"] = self.salary
        if self.fringe_benefit is not None:
            data["fringeBenefit"] = self.fringe_benefit
        if self.salary_for_ins is not None:
            data["salaryForIns"] = self.salary_for_ins
        if self.deduction_to_taxable is not None:
            data["deductionToTaxable"] = self.deduction_to_taxable
        if self.tax is not None:
            data["tax"] = self.tax
        if self.taxable_compensation is not None:
            data["taxableCompensation"] = self.taxable_compensation
        if self.tax_free_items is not None:
            data["taxFreeItems"] = self.tax_free_items
        if self.other_deductions is not None:
            data["otherDeductions"] = self.other_deductions
        if self.net_pay is not None:
            data["netPay"] = self.net_pay
        if self.esalary_status is not None:
            data["eSalaryStatus"] = self.esalary_status
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalarySlip":
        params = {
            "id": data["id"],
        }
        if "rows" in data:
            params["rows"] = [SalarySlipRow.from_dict(row) for row in data["rows"]]
        if "settings" in data:
            params["settings"] = SalarySlipSettings.from_dict(data["settings"])
        if "adjustments" in data:
            params["adjustments"] = SalarySlipAdjustments.from_dict(data["adjustments"])
        if "incomesRegisterReportingSetting" in data:
            params["incomes_register_reporting_setting"] = IncomesRegisterReportingSetting(
                data["incomesRegisterReportingSetting"]
            )
        if "employeeId" in data:
            params["employee_id"] = data["employeeId"]
        if "employeeName" in data:
            params["employee_name"] = data["employeeName"]
        if "status" in data:
            params["status"] = SalarySlipStatus(data["status"])
        if "paidStatusDetails" in data:
            params["paid_status_details"] = SalarySlipPaidStatusDetails(data["paidStatusDetails"])
        if "slipNumber" in data:
            params["slip_number"] = data["slipNumber"]
        if "salaryBaseNote" in data:
            params["salary_base_note"] = data["salaryBaseNote"]
        if "workingTimeAllocation" in data and data["workingTimeAllocation"]:
            params["working_time_allocation"] = SalarySlipWorkingTimeAllocation.from_dict(
                data["workingTimeAllocation"]
            )
        if "slipNotes" in data:
            params["slip_notes"] = data["slipNotes"]
        if "version" in data:
            params["version"] = data["version"]
        if "payday" in data:
            params["payday"] = data["payday"]
        if "sentStatus" in data:
            params["sent_status"] = data["sentStatus"]
        if "reportStatus" in data:
            params["report_status"] = data["reportStatus"]
        if "salary" in data:
            params["salary"] = data["salary"]
        if "fringeBenefit" in data:
            params["fringe_benefit"] = data["fringeBenefit"]
        if "salaryForIns" in data:
            params["salary_for_ins"] = data["salaryForIns"]
        if "deductionToTaxable" in data:
            params["deduction_to_taxable"] = data["deductionToTaxable"]
        if "tax" in data:
            params["tax"] = data["tax"]
        if "taxableCompensation" in data:
            params["taxable_compensation"] = data["taxableCompensation"]
        if "taxFreeItems" in data:
            params["tax_free_items"] = data["taxFreeItems"]
        if "otherDeductions" in data:
            params["other_deductions"] = data["otherDeductions"]
        if "netPay" in data:
            params["net_pay"] = data["netPay"]
        if "eSalaryStatus" in data:
            params["esalary_status"] = data["eSalaryStatus"]
        return cls(**params)


class SalarySlipTransaction(ProcountorAPIObject):
    def __init__(
        self,
        account: str,
        accounting_value: Decimal,
        transaction_type: TransactionType,
        id: typing.Optional[int] = None,
        description: typing.Optional[str] = None,
        balance_code: typing.Optional[str] = None,
        dimension_item_values: typing.Optional[List[DimensionItemValue]] = None,
    ):
        self.id: typing.Optional[int] = id
        self.transaction_type: TransactionType = transaction_type
        self.account: str = account
        self.accounting_value: Decimal = accounting_value
        self.description: typing.Optional[str] = description
        self.balance_code: typing.Optional[str] = balance_code
        self.dimension_item_values: typing.Optional[List[DimensionItemValue]] = dimension_item_values

    def as_dict(self) -> typing.Dict:
        data = {
            "account": self.account,
            "accountingValue": self.accounting_value,
            "transactionType": self.transaction_type.value,
        }
        if self.id is not None:
            data["id"] = self.id
        if self.description is not None:
            data["description"] = self.description
        if self.balance_code is not None:
            data["balanceCode"] = self.balance_code
        if self.dimension_item_values is not None:
            data["dimensionItemValues"] = [v.as_dict() for v in self.dimension_item_values]
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalarySlipTransaction":
        params: typing.Dict[str, typing.Any] = {
            "account": data["account"],
            "accounting_value": data["accountingValue"],
            "transaction_type": TransactionType(data["transactionType"]),
        }
        if "id" in data:
            params["id"] = data["id"]
        if "description" in data:
            params["description"] = data["description"]
        if "balanceCode" in data:
            params["balance_code"] = data["balanceCode"]
        if "dimensionItemValues" in data:
            params["dimension_item_values"] = [
                DimensionItemValue.from_dict(v) for v in data["dimensionItemValues"]
            ]
        return cls(**params)


class SalarySlipAccounting(ProcountorAPIObject):
    def __init__(
        self,
        name: str,
        receipt_date: str,
        transactions: List[SalarySlipTransaction],
        accountants_notes: typing.Optional[str] = None,
        transaction_description: typing.Optional[str] = None,
        receipt_validity: typing.Optional[ReceiptValidity] = None,
        period_start_date: typing.Optional[str] = None,
        period_end_date: typing.Optional[str] = None,
        version: typing.Optional[str] = None,
    ):
        self.name: str = name
        self.receipt_date: str = receipt_date
        self.accountants_notes: typing.Optional[str] = accountants_notes
        self.transaction_description: typing.Optional[str] = transaction_description
        self.receipt_validity: typing.Optional[ReceiptValidity] = receipt_validity
        self.period_start_date: typing.Optional[str] = period_start_date
        self.period_end_date: typing.Optional[str] = period_end_date
        self.transactions: List[SalarySlipTransaction] = transactions
        self.version: typing.Optional[str] = version

    def as_dict(self) -> typing.Dict:
        data = {
            "name": self.name,
            "receiptDate": self.receipt_date,
            "transactions": [t.as_dict() for t in self.transactions],
        }
        if self.accountants_notes is not None:
            data["accountantsNotes"] = self.accountants_notes
        if self.transaction_description is not None:
            data["transactionDescription"] = self.transaction_description
        if self.receipt_validity is not None:
            data["receiptValidity"] = self.receipt_validity.value
        if self.period_start_date is not None:
            data["periodStartDate"] = self.period_start_date
        if self.period_end_date is not None:
            data["periodEndDate"] = self.period_end_date
        if self.version is not None:
            data["version"] = self.version
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalarySlipAccounting":
        params: typing.Dict[str, typing.Any] = {
            "name": data["name"],
            "receipt_date": data["receiptDate"],
            "transactions": [SalarySlipTransaction.from_dict(t) for t in data["transactions"]],
        }
        if "accountantsNotes" in data:
            params["accountants_notes"] = data["accountantsNotes"]
        if "transactionDescription" in data:
            params["transaction_description"] = data["transactionDescription"]
        if "receiptValidity" in data:
            params["receipt_validity"] = ReceiptValidity(data["receiptValidity"])
        if "periodStartDate" in data:
            params["period_start_date"] = data["periodStartDate"]
        if "periodEndDate" in data:
            params["period_end_date"] = data["periodEndDate"]
        if "version" in data:
            params["version"] = data["version"]
        return cls(**params)


class SalaryInfo(ProcountorAPIObject):
    def __init__(
        self,
        person_id: int,
        income_configuration: IncomeConfiguration,
        insurances_configuration: InsurancesConfiguration,
        international_situations_configuration: InternationalSituationsConfiguration,
        employee_id: typing.Optional[int] = None,
    ):
        self.employee_id: typing.Optional[int] = employee_id
        self.person_id: int = person_id
        self.income_configuration: IncomeConfiguration = income_configuration
        self.insurances_configuration: InsurancesConfiguration = insurances_configuration
        self.international_situations_configuration: (
            InternationalSituationsConfiguration
        ) = international_situations_configuration

    def as_dict(self) -> typing.Dict:
        data = {
            "personId": self.person_id,
            "incomeConfiguration": self.income_configuration.as_dict(),
            "insurancesConfiguration": self.insurances_configuration.as_dict(),
            "internationalSituationsConfiguration": self.international_situations_configuration.as_dict(),
        }
        if self.employee_id is not None:
            data["employeeId"] = self.employee_id
        return data

    @classmethod
    def from_dict(cls, data: typing.Dict) -> "SalaryInfo":
        return cls(
            employee_id=data.get("employeeId", None),
            person_id=data["personId"],
            income_configuration=IncomeConfiguration.from_dict(data["incomeConfiguration"]),
            insurances_configuration=InsurancesConfiguration.from_dict(data["insurancesConfiguration"]),
            international_situations_configuration=InternationalSituationsConfiguration.from_dict(
                data["internationalSituationsConfiguration"]
            ),
        )


class PersonFullAddress(ProcountorAPIObject):
    def __init__(
        self,
        street: typing.Optional[str] = None,
        zip: typing.Optional[str] = None,
        city: typing.Optional[str] = None,
        country: typing.Optional[Country] = None,
        specifier: typing.Optional[str] = None,
        subdivision: typing.Optional[str] = None,
        post_office_box: typing.Optional[str] = None,
    ):
        self.street = street
        self.zip = zip
        self.city = city
        self.country = country
        self.specifier = specifier
        self.subdivision = subdivision
        self.post_office_box = post_office_box

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.street is not None:
            data["street"] = self.street
        if self.zip is not None:
            data["zip"] = self.zip
        if self.city is not None:
            data["city"] = self.city
        if self.country is not None:
            data["country"] = self.country.value
        if self.specifier is not None:
            data["specifier"] = self.specifier
        if self.subdivision is not None:
            data["subdivision"] = self.subdivision
        if self.post_office_box is not None:
            data["postOfficeBox"] = self.post_office_box
        return data

    @classmethod
    def from_dict(cls, data) -> "PersonFullAddress":
        params = {}
        if "street" in data:
            params["street"] = data["street"]
        if "zip" in data:
            params["zip"] = data["zip"]
        if "city" in data:
            params["city"] = data["city"]
        if "country" in data:
            params["country"] = Country(data["country"])
        if "specifier" in data:
            params["specifier"] = data["specifier"]
        if "subdivision" in data:
            params["subdivision"] = data["subdivision"]
        if "postOfficeBox" in data:
            params["post_office_box"] = data["postOfficeBox"]
        return cls(**params)


class PersonPaymentInfo(ProcountorAPIObject):
    def __init__(
        self,
        payment_method: PaymentMethod,
        payment_term_days: str,
        penal_interest_rate: Decimal,
        clearing_code: typing.Optional[str] = None,
        account_number: typing.Optional[str] = None,
        bic: typing.Optional[str] = None,
        payment_term_percentage: typing.Optional[Decimal] = None,
        discount_percentage: typing.Optional[Decimal] = None,
    ):
        self.payment_method = payment_method
        self.clearing_code = clearing_code
        self.account_number = account_number
        self.bic = bic
        self.payment_term_days = payment_term_days
        self.payment_term_percentage = payment_term_percentage
        self.penal_interest_rate = penal_interest_rate
        self.discount_percentage = discount_percentage

    def as_dict(self) -> typing.Dict:
        data = {
            "paymentMethod": self.payment_method.value,
            "paymentTermDays": self.payment_term_days,
            "penalInterestRate": self.penal_interest_rate,
        }
        if self.clearing_code is not None:
            data["clearingCode"] = self.clearing_code
        if self.account_number is not None:
            data["accountNumber"] = self.account_number
        if self.bic is not None:
            data["bic"] = self.bic
        if self.payment_term_percentage is not None:
            data["paymentTermPercentage"] = self.payment_term_percentage
        if self.discount_percentage is not None:
            data["discountPercentage"] = self.discount_percentage
        return data

    @classmethod
    def from_dict(cls, data) -> "PersonPaymentInfo":
        return cls(
            payment_method=PaymentMethod(data["paymentMethod"]),
            payment_term_days=data["paymentTermDays"],
            penal_interest_rate=Decimal(data["penalInterestRate"]),
            clearing_code=data.get("clearingCode", None),
            account_number=data.get("accountNumber", None),
            bic=data.get("bic", None),
            payment_term_percentage=(
                Decimal(data["paymentTermPercentage"])
                if data.get("paymentTermPercentage") is not None
                else None
            ),
            discount_percentage=(
                Decimal(data["discountPercentage"])
                if data.get("discountPercentage") is not None
                else None
            ),
        )


class PersonInvoicingInfo(ProcountorAPIObject):
    def __init__(
        self,
        language: PersonLanguage,
        gender: PersonGender,
        person_number: typing.Optional[str] = None,
        identifier: typing.Optional[str] = None,
        identifier_type: typing.Optional[PersonIdentifierType] = None,
        date_of_birth: typing.Optional[date] = None,
        home_country_person_id: typing.Optional[str] = None,
    ):
        self.person_number = person_number
        self.identifier = identifier
        self.identifier_type = identifier_type
        self.date_of_birth = date_of_birth
        self.language = language
        self.gender = gender
        self.home_country_person_id = home_country_person_id

    def as_dict(self) -> typing.Dict:
        data = {
            "language": self.language.value,
            "gender": self.gender.value,
        }
        if self.person_number is not None:
            data["personNumber"] = self.person_number
        if self.identifier is not None:
            data["identifier"] = self.identifier
        if self.identifier_type is not None:
            data["identifierType"] = self.identifier_type.value
        if self.date_of_birth is not None:
            data["dateOfBirth"] = self.date_of_birth.strftime("%Y-%m-%d")
        if self.home_country_person_id is not None:
            data["homeCountryPersonId"] = self.home_country_person_id
        return data

    @classmethod
    def from_dict(cls, data) -> "PersonInvoicingInfo":
        params = {
            "language": PersonLanguage(data["language"]),
            "gender": PersonGender(data["gender"]),
        }
        if "personNumber" in data:
            params["person_number"] = data["personNumber"]
        if "identifier" in data:
            params["identifier"] = data["identifier"]
        if "identifierType" in data:
            params["identifier_type"] = PersonIdentifierType(data["identifierType"])
        if "dateOfBirth" in data:
            params["date_of_birth"] = date.fromisoformat(data["dateOfBirth"])
        if "homeCountryPersonId" in data:
            params["home_country_person_id"] = data["homeCountryPersonId"]
        return cls(**params)


class PersonRegistryInfo(ProcountorAPIObject):
    def __init__(
        self,
        active: bool,
        mobile_phone: typing.Optional[str] = None,
        fax: typing.Optional[str] = None,
        phone: typing.Optional[str] = None,
        email: typing.Optional[str] = None,
        contact_person: typing.Optional[str] = None,
        default_reference: typing.Optional[str] = None,
        section: typing.Optional[str] = None,
        person_groups_ids: typing.Optional[List[int]] = None,
        report_group_id: typing.Optional[int] = None,
        home_municipality: typing.Optional[str] = None,
    ):
        self.active = active
        self.mobile_phone = mobile_phone
        self.fax = fax
        self.phone = phone
        self.email = email
        self.contact_person = contact_person
        self.default_reference = default_reference
        self.section = section
        self.person_groups_ids = person_groups_ids
        self.report_group_id = report_group_id
        self.home_municipality = home_municipality

    def as_dict(self) -> typing.Dict:
        data = {
            "active": self.active,
        }
        if self.mobile_phone is not None:
            data["mobilePhone"] = self.mobile_phone
        if self.fax is not None:
            data["fax"] = self.fax
        if self.phone is not None:
            data["phone"] = self.phone
        if self.email is not None:
            data["email"] = self.email
        if self.contact_person is not None:
            data["contactPerson"] = self.contact_person
        if self.default_reference is not None:
            data["defaultReference"] = self.default_reference
        if self.section is not None:
            data["section"] = self.section
        if self.person_groups_ids is not None:
            data["personGroupsIds"] = self.person_groups_ids
        if self.report_group_id is not None:
            data["reportGroupId"] = self.report_group_id
        if self.home_municipality is not None:
            data["homeMunicipality"] = self.home_municipality
        return data

    @classmethod
    def from_dict(cls, data) -> "PersonRegistryInfo":
        params = {
            "active": data["active"],
        }
        if "mobilePhone" in data:
            params["mobile_phone"] = data["mobilePhone"]
        if "fax" in data:
            params["fax"] = data["fax"]
        if "phone" in data:
            params["phone"] = data["phone"]
        if "email" in data:
            params["email"] = data["email"]
        if "contactPerson" in data:
            params["contact_person"] = data["contactPerson"]
        if "defaultReference" in data:
            params["default_reference"] = data["defaultReference"]
        if "section" in data:
            params["section"] = data["section"]
        if "personGroupsIds" in data:
            params["person_groups_ids"] = data["personGroupsIds"]
        if "reportGroupId" in data:
            params["report_group_id"] = data["reportGroupId"]
        if "homeMunicipality" in data:
            params["home_municipality"] = data["homeMunicipality"]
        return cls(**params)


class PersonBasicAddress(ProcountorAPIObject):
    def __init__(
        self,
        street: typing.Optional[str] = None,
        zip: typing.Optional[str] = None,
        city: typing.Optional[str] = None,
        country: typing.Optional[str] = None,
    ):
        self.street = street
        self.zip = zip
        self.city = city
        self.country = country

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.street is not None:
            data["street"] = self.street
        if self.zip is not None:
            data["zip"] = self.zip
        if self.city is not None:
            data["city"] = self.city
        if self.country is not None:
            data["country"] = self.country
        return data

    @classmethod
    def from_dict(cls, data) -> "PersonBasicAddress":
        params = {}
        if "street" in data:
            params["street"] = data["street"]
        if "zip" in data:
            params["zip"] = data["zip"]
        if "city" in data:
            params["city"] = data["city"]
        if "country" in data:
            params["country"] = data["country"]
        return cls(**params)


class PersonBasicInvoicingInfo(ProcountorAPIObject):
    def __init__(
        self,
        person_number: typing.Optional[str] = None,
        identifier: typing.Optional[str] = None,
        identifier_type: typing.Optional[PersonIdentifierType] = None,
    ):
        self.person_number = person_number
        self.identifier = identifier
        self.identifier_type = identifier_type

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.person_number is not None:
            data["personNumber"] = self.person_number
        if self.identifier is not None:
            data["identifier"] = self.identifier
        if self.identifier_type is not None:
            data["identifierType"] = self.identifier_type.value
        return data

    @classmethod
    def from_dict(cls, data) -> "PersonBasicInvoicingInfo":
        params = {}
        if "personNumber" in data:
            params["person_number"] = data["personNumber"]
        if "identifier" in data:
            params["identifier"] = data["identifier"]
        if "identifierType" in data:
            params["identifier_type"] = PersonIdentifierType(data["identifierType"])
        return cls(**params)


class PersonBasicRegistryInfo(ProcountorAPIObject):
    def __init__(
        self,
        active: bool,
    ):
        self.active = active

    def as_dict(self) -> typing.Dict:
        return {
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data) -> "PersonBasicRegistryInfo":
        return cls(
            active=data["active"],
        )


class PersonBasicInfo(ProcountorAPIObject):
    def __init__(
        self,
        last_name: str,
        id: typing.Optional[int] = None,
        first_name: typing.Optional[str] = None,
        delivery_address: typing.Optional[PersonBasicAddress] = None,
        invoicing_info: typing.Optional[PersonBasicInvoicingInfo] = None,
        registry_info: typing.Optional[PersonBasicRegistryInfo] = None,
    ):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.delivery_address = delivery_address
        self.invoicing_info = invoicing_info
        self.registry_info = registry_info

    def as_dict(self) -> typing.Dict:
        data = {}
        if self.id is not None:
            data["id"] = self.id
        if self.first_name is not None:
            data["firstName"] = self.first_name
        if self.last_name is not None:
            data["lastName"] = self.last_name
        if self.delivery_address is not None:
            data["deliveryAddress"] = self.delivery_address.as_dict()
        if self.invoicing_info is not None:
            data["invoicingInfo"] = self.invoicing_info.as_dict()
        if self.registry_info is not None:
            data["registryInfo"] = self.registry_info.as_dict()
        return data

    @classmethod
    def from_dict(cls, data) -> "PersonBasicInfo":
        params = {
            "last_name": data["lastName"],
        }
        if "id" in data:
            params["id"] = data["id"]
        if "firstName" in data:
            params["first_name"] = data["firstName"]
        if "deliveryAddress" in data and data["deliveryAddress"]:
            params["delivery_address"] = PersonBasicAddress.from_dict(data["deliveryAddress"])
        if "invoicingInfo" in data and data["invoicingInfo"]:
            params["invoicing_info"] = PersonBasicInvoicingInfo.from_dict(data["invoicingInfo"])
        if "registryInfo" in data and data["registryInfo"]:
            params["registry_info"] = PersonBasicRegistryInfo.from_dict(data["registryInfo"])
        return cls(**params)


class Person(ProcountorAPIObject):
    def __init__(
        self,
        last_name: str,
        payment_info: PersonPaymentInfo,
        invoicing_info: PersonInvoicingInfo,
        registry_info: PersonRegistryInfo,
        id: typing.Optional[int] = None,
        first_name: typing.Optional[str] = None,
        job_title: typing.Optional[str] = None,
        delivery_address: typing.Optional[PersonFullAddress] = None,
        home_country_address: typing.Optional[PersonFullAddress] = None,
        version: typing.Optional[str] = None,
    ):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.job_title = job_title
        self.delivery_address = delivery_address
        self.home_country_address = home_country_address
        self.payment_info = payment_info
        self.invoicing_info = invoicing_info
        self.registry_info = registry_info
        self.version = version

    def as_dict(self) -> typing.Dict:
        data = {
            "lastName": self.last_name,
            "paymentInfo": self.payment_info.as_dict(),
            "invoicingInfo": self.invoicing_info.as_dict(),
            "registryInfo": self.registry_info.as_dict(),
        }
        if self.id is not None:
            data["id"] = self.id
        if self.first_name is not None:
            data["firstName"] = self.first_name
        if self.job_title is not None:
            data["jobTitle"] = self.job_title
        if self.delivery_address is not None:
            data["deliveryAddress"] = self.delivery_address.as_dict()
        if self.home_country_address is not None:
            data["homeCountryAddress"] = self.home_country_address.as_dict()
        if self.version is not None:
            data["version"] = self.version
        return data

    @classmethod
    def from_dict(cls, data) -> "Person":
        params = {
            "last_name": data["lastName"],
            "payment_info": PersonPaymentInfo.from_dict(data["paymentInfo"]),
            "invoicing_info": PersonInvoicingInfo.from_dict(data["invoicingInfo"]),
            "registry_info": PersonRegistryInfo.from_dict(data["registryInfo"]),
        }
        if "id" in data:
            params["id"] = data["id"]
        if "firstName" in data:
            params["first_name"] = data["firstName"]
        if "jobTitle" in data:
            params["job_title"] = data["jobTitle"]
        if "deliveryAddress" in data and data["deliveryAddress"]:
            params["delivery_address"] = PersonFullAddress.from_dict(data["deliveryAddress"])
        if "homeCountryAddress" in data and data["homeCountryAddress"]:
            params["home_country_address"] = PersonFullAddress.from_dict(data["homeCountryAddress"])
        if "version" in data:
            params["version"] = data["version"]
        return cls(**params)


class LedgerAccountTranslation(ProcountorAPIObject):
    def __init__(
        self,
        language_code: str,
        translation: str,
    ):
        self.language_code: str = language_code
        self.translation: str = translation

    def as_dict(self) -> typing.Dict:
        return {
            "languageCode": self.language_code,
            "translation": self.translation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, typing.Any]) -> "LedgerAccountTranslation":
        return cls(
            language_code=data["languageCode"],
            translation=data["translation"],
        )


class LedgerAccount(ProcountorAPIObject):
    def __init__(
        self,
        ledger_account_code: str,
        name: str,
        active: bool,
        translations: Optional[List[LedgerAccountTranslation]] = None,
    ):
        self.ledger_account_code: str = ledger_account_code
        self.name: str = name
        self.active: bool = active
        self.translations: Optional[List[LedgerAccountTranslation]] = translations

    def as_dict(self) -> typing.Dict:
        data = {
            "ledgerAccountCode": self.ledger_account_code,
            "name": self.name,
            "active": self.active,
        }
        if self.translations:
            data["translations"] = [t.as_dict() for t in self.translations]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, typing.Any]) -> "LedgerAccount":
        params = {
            "ledger_account_code": data["ledgerAccountCode"],
            "name": data["name"],
            "active": data["active"],
        }
        if "translations" in data:
            params["translations"] = [
                LedgerAccountTranslation.from_dict(t) for t in data["translations"]
            ]
        return cls(**params)


class ProcountorAPIClient(object):
    def __init__(
        self,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
        api_url: Optional[str] = None
    ):
        if not api_url:
            api_url = "https://api.procountor.com/api"
        self.session = requests.Session()
        self.api_url = api_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._oauth_access_token = None
        self._oauth_refresh_token = None
        self._api_key = None
        self.state = self._generate_state()
        self.session.headers.update({"User-Agent": "Python Procountorlib"})
        retries = Retry(total=5, backoff_factor=5)
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.mount("http://", HTTPAdapter(max_retries=retries))

    def _generate_state(self):
        return "".join(
            [random.choice(string.digits + string.ascii_letters) for x in range(16)]
        )

    def _parse_procountor_error(
        self,
        message,
        url
    ) -> typing.Optional[str]:
        """
        Parse Procountor API errors to human-readable format

        {"errors":[{"status":400,"field":"date","message":"CLOSED_FISCAL_PERIOD"}]}

        """
        try:
            data = json.loads(message)

        except json.decoder.JSONDecodeError:
            return None

        if "errors" not in data:
            return None

        for error in data["errors"]:
            if "message" in error:
                message = error.get("message")
                urls_and_errors = KNOWN_PROCOUNTOR_ERRORS.get(message, None)
                if urls_and_errors:
                    for url_suffix, message in urls_and_errors.items():
                        if url.endswith(url_suffix):
                            return message

        return None

    def _error_handler(
        self,
        url: str,
        parameters: Dict,
        response: requests.Response,
        method: str = None,
    ) -> requests.Response:
        method = method or "GET"
        if response.status_code >= 400:
            human_readable_error = self._parse_procountor_error(response.content, url)
            logger.debug(response.request.body)
            logger.debug(response.request.headers)
            raise ProcountorAPIException(
                "%s %s params %s failed with error (%d) %s"
                % (method, url, parameters, response.status_code, response.content),
                human_readable_error=human_readable_error,
            )
        return response

    def request(
        self,
        method: str,
        path: str,
        body=None,
        headers: Dict = None,
        params: Dict = None,
        files: Dict = None,
        json: Dict = None,
    ) -> requests.Response:
        if not headers:
            headers = {}
        if not params:
            params = {}
        if json and body:
            raise RuntimeError("Cannot have both body and json")
        if json:
            body = simplejson.dumps(json, use_decimal=True)
            headers["Content-Type"] = "application/json"
        url = "%s/%s" % (self.api_url, path.lstrip("/"))
        try:
            response = self.session.request(
                method,
                url,
                timeout=30,
                data=body,
                params=params,
                headers=headers,
                allow_redirects=False,
                files=files,
            )
        except requests.exceptions.Timeout:
            logger.exception(
                "Timeout while connecting to Procountor API %s '%s'", method, url
            )
            raise ProcountorAPIException(
                "Timeout while communicating with Procountor API"
            )
        except requests.exceptions.ConnectionError:
            logger.exception(
                "Max retries reached while connecting to Procountor API %s '%s'",
                method,
                url,
            )
            raise ProcountorAPIException(
                "Max retries reached while communicating with Procountor API"
            )
        except requests.exceptions.RequestException:
            logger.exception(
                "Unexpected exception while communicating with Procountor API %s '%s'",
                method,
                url,
            )
            raise ProcountorAPIException(
                "Unexpected exception while communicating with Procountor API"
            )
        return self._error_handler(url, params, response, method=method)

    def get(
        self,
        path: str,
        headers: Dict = None,
        params: Dict = None,
    ) -> requests.Response:
        return self.request("GET", path=path, headers=headers, params=params)

    def post(
        self,
        path: str,
        body=None,
        headers: Dict = None,
        params: Dict = None,
        files: Dict = None,
        json: Dict = None,
    ) -> requests.Response:
        return self.request(
            "POST",
            path,
            body=body,
            headers=headers,
            params=params,
            files=files,
            json=json,
        )

    def put(
        self,
        path: str,
        body=None,
        headers: Dict = None,
        params: Dict = None,
        json: Dict = None,
    ) -> requests.Response:
        return self.request(
            "PUT", path, body=body, headers=headers, params=params, json=json
        )

    @staticmethod
    def get_jwt_data(token) -> Dict:
        if len(token.split(".")) != 3:
            raise ProcountorAPIException("Invalid JWT token")
        # Get expire time from token
        data_part = token.split(".")[1]
        # Pad to multiple of 4
        data_part += (4 - len(data_part) % 4) * "="
        return simplejson.loads(base64.b64decode(data_part))

    @staticmethod
    def token_expire_time(token) -> datetime:
        # Get expire time from token
        expire_time = 0
        if token:
            details = ProcountorAPIClient.get_jwt_data(token)
            expire_time = details.get("exp")
            if not expire_time:
                expire_time = 0
        return datetime.fromtimestamp(expire_time, tz=UTC)

    def login_m2m(
        self,
        api_key: str
    ) -> None:
        self._api_key = api_key
        self.refresh_access_token_if_needed()

    def login_oauth_redirect(self):
        # Reset state
        self.state = self._generate_state()
        # login url is always on api_url root
        url_components = list(urlparse(self.api_url))
        url_components[2] = "/login"
        url_components[4] = urlencode({
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "state": self.state,
        })
        return urlunparse(url_components), self.state

    def login_oauth_callback(self, code, state, expected_state=None):
        # Check state and fetch access and refresh tokens
        if not expected_state:
            expected_state = self.state
        if expected_state != state:
            raise ProcountorAPIException("State don't match expected state")

        post_url = "/oauth/token"
        body = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }

        # Delete old auth token
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]

        response = self.post(post_url, body=body)

        if response.status_code != 200:
            raise ProcountorAPIException(
                "Access token fetch failed, wrong response status code %d",
                response.status_code,
            )

        response_body = response.json()

        access_token = response_body.get("access_token")
        refresh_token = response_body.get("refresh_token")

        self._oauth_access_token = access_token
        self._oauth_refresh_token = refresh_token

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires": self.token_expire_time(token=access_token),
        }

    def set_access_token(
        self,
        access_token: str,
        refresh_token: Optional[str] = None
    ) -> Dict:
        self._oauth_access_token = access_token
        self._api_key = None
        if refresh_token:
            self._oauth_refresh_token = refresh_token

        self.session.headers.update(
            {"Authorization": "Bearer %s" % self._oauth_access_token}
        )

        return {
            "access_token": access_token,
            "expires": self.token_expire_time(token=access_token),
        }

    def refresh_access_token(
        self,
    ) -> str:
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }
        if self._oauth_refresh_token:
            min_validity = datetime.now(timezone.utc) + timedelta(seconds=60)
            if self.token_expire_time(token=self._oauth_refresh_token) < min_validity:
                raise ProcountorRefreshTokenExpired("Refresh token has expired")
            params.update({
                "grant_type": "refresh_token",
                "refresh_token": self._oauth_refresh_token,
            })
        elif self._api_key:
            params.update({
                "grant_type": "client_credentials",
                "api_key": self._api_key,
            })
        else:
            raise ProcountorAPIException("No refresh token or api_key for access_token refresh")

        headers = {"Content-type": "application/x-www-form-urlencoded"}

        # Delete old auth token
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]

        res = self.post("/oauth/token", body=params, headers=headers)

        if res.status_code != 200:
            raise ProcountorAPIException(
                "Access token fetch failed, wrong response status code %d",
                res.status_code,
            )

        response = res.json()

        if "access_token" not in response:
            raise ProcountorAPIException(
                "Access token fetch failed, no access_token in response"
            )

        self._oauth_access_token = response["access_token"]

        self.session.headers.update(
            {"Authorization": "Bearer %s" % self._oauth_access_token}
        )
        return response["access_token"]

    def refresh_access_token_if_needed(
        self,
    ) -> None:
        now = datetime.now(timezone.utc)

        min_expire_time = now + timedelta(minutes=10)

        expire_time = self.token_expire_time(self._oauth_access_token)

        if (
            self._oauth_access_token
            and expire_time > min_expire_time
        ):
            logger.debug(f"No need to update access token, expires in {(expire_time - now).total_seconds}")
            return

        logger.debug("Refreshing access token")

        self.refresh_access_token()

    def post_attachment(
        self,
        attachment: AttachmentMetadata,
        blob: ByteString,
    ) -> AttachmentMetadata:
        """
        Post new attachment
        :param attachment: Attachment metadata
        :param blob: file blob
        :return: AttachmentMetadata object
        """
        if len(blob) > 10000000:
            raise ProcountorAPIException("Blob is too big, max size is 10000000 bytes")
        files = {}
        if attachment.mime_type:
            files["file"] = (attachment.name, blob, attachment.mime_type)
        else:
            files["file"] = (attachment.name, blob)
        files["meta"] = (
            None,
            simplejson.dumps(attachment.as_dict()),
            "application/json",
        )
        response = self.post("/attachments", files=files)
        if response.status_code == 200:
            logger.debug("Attachment sent succesfully: %s", attachment.as_dict())
            return AttachmentMetadata.from_dict(response.json())
        raise ProcountorAPIException(
            "Failed to post attachment, got status {}".format(response.status_code)
        )

    def post_invoice(
        self,
        invoice: Invoice,
    ) -> Invoice:
        """
        Post new invoice
        :param invoice: Invoice object to send
        :return: Invoice object
        """

        request = invoice.as_dict()

        res = self.post("/invoices", json=request)
        if res.status_code == 200:
            response = res.json()
            return Invoice.from_dict(response)
        raise ProcountorAPIException("Sending invoice failed")

    def get_invoice(self, invoice_id) -> Invoice:
        res = self.get(f"/invoices/{invoice_id}")
        if res.status_code == 200:
            response = Invoice.from_dict(res.json())
            return response
        raise ProcountorAPIException(f"Getting invoice {invoice_id} failed")

    def get_currencies_exchangerate(
        self,
        base_currency: Currency,
        currency: Currency,
        date: datetime = None,
    ) -> Decimal:
        """
        Get currency rate for given currencies for optional given date
        :param base_currency: Base currency
        :param currency: Exchange currency
        :param date: Date
        :return: Exchange rate for one baseCurrency in currency
        """
        params = {
            "baseCurrency": base_currency.value,
            "currency": currency.value,
            "rateType": "ACCOUNT_CURRENCY_AVERAGE_RATE",
        }
        if date:
            params["day"] = date.strftime("%Y-%m-%d")
        res = self.get("/currencies/exchangerate", params=params)
        if res.status_code == 200:
            response = simplejson.loads(res.content, use_decimal=True)
            return response["rate"]
        raise ProcountorAPIException("Getting exchange rate failed")

    def get_vats_default(self) -> typing.Tuple[typing.List, typing.List]:
        """
        Get customers enabled VAT statuses
        First list is a list of all VATs for customers country
        Second list is a list of all VATs enabled for customer
        :return:
        """
        res = self.get("/vats/default")
        if res.status_code == 200:
            response = simplejson.loads(res.content, use_decimal=True)
            vat_country = []
            vat_status = []
            for country_data in response.get("vatInformation", []):
                for value in country_data.get("percentages", []):
                    if value["purchase"] is True:
                        vat_country.append(Decimal(value["vatPercent"]))
            for value in response.get("vatStatuses"):
                if value["purchase"] is True:
                    vat_status.append(value["vatStatus"])
            return vat_country, vat_status
        raise ProcountorAPIException("Getting VAT defaults failed")

    def get_fiscal_years(self) -> typing.List[typing.Dict[str, typing.Any]]:
        """
        Get fiscal years
        :return: fiscal years
        """
        res = self.get("/fiscalyears")
        if res.status_code != 200:
            raise ProcountorAPIException("Getting fiscal years failed")
        years = []
        response = simplejson.loads(res.content, use_decimal=True)
        for year in response.get("fiscalYears", []):
            years.append(
                {
                    "id": year["id"],
                    "start": datetime.strptime(year["startDate"], "%Y-%m-%d"),
                    "end": datetime.strptime(year["endDate"], "%Y-%m-%d"),
                    "open": year["isOpen"],
                    "periods": [
                        {
                            "id": period["id"],
                            "start": datetime.strptime(period["startDate"], "%Y-%m-%d"),
                            "end": datetime.strptime(period["endDate"], "%Y-%m-%d"),
                            "status": TrackingPeriodStatus(period["status"]),
                        }
                        for period in year.get("trackingPeriods", [])
                    ],
                }
            )
        return years

    def get_fiscal_period(
        self,
        date: datetime,
    ) -> typing.Union[typing.Dict[str, typing.Any], None]:
        """
        Get Fiscal period matching date
        :param date: date to match
        :return: period details if found, or None
        """
        fiscal_years = self.get_fiscal_years()

        for year in fiscal_years:
            if date < year["start"] or date > year["end"]:
                continue
            for period in year["periods"]:
                if date < period["start"] or date > period["end"]:
                    continue
                return period
        return None

    def send_to_circulation(
        self,
        invoice_id: int,
    ) -> InfoMessage:
        """
        Send invoice to circulation
        :param invoice_id: Invoice id to send to circulation
        :return: InfoMessage object
        """
        res = self.put("/invoices/{}/sendToCirculation".format(invoice_id))
        if res.status_code != 200:
            raise ProcountorAPIException("Send to circulation failed with status %d", res.status_code)
        return InfoMessage.from_dict(res.json())

    def get_paginated(self, path, params=None) -> List[Dict]:
        headers = {
            "Accept": "application/json",
        }
        results = []
        page = 0
        previous_id = None
        if not params:
            params = {}
        while True:
            params["page"] = page
            if previous_id:
                params["previous_id"] = previous_id
            elif "previous_id" in params:
                del params["previous_id"]
            res = self.get(path=path, params=params, headers=headers)
            page += 1
            if res.status_code == 200:
                data = res.json(use_decimal=True)
                results += data.get("results", [])
                if data["meta"]["resultCount"] == 0 or data["meta"]["resultCount"] < data["meta"]["pageSize"]:
                    break
                continue
            else:
                raise ProcountorAPIException("Getting {} with params {} failed".format(path, params))
        return results

    def get_json(self, path, name, params=None):
        result = self.get(path, params=params)
        if result.status_code != 200:
            logger.error(
                "Failed to get %s JSON response, status %s, content: %s",
                name, result.status_code, result.content
            )
            raise ProcountorAPIException("Failed to get %s JSON: %s", name, result.content)
        return result.json()

    def get_business_partners(self, partner_type: PartnerType = None) -> List[BusinessPartnerBasicInfo]:
        """
        Get business partners
        :return: Business partners
        """
        params = {
            "size": 200,
        }
        if partner_type:
            params["type"] = partner_type.value
        return [
            BusinessPartnerBasicInfo.from_dict(item)
            for item in self.get_paginated("/businesspartners", params=params)
        ]

    def get_products(
        self,
        code: typing.Optional[str] = None,
        name: typing.Optional[str] = None,
        type: typing.Optional[ProductType] = None
    ) -> List[Product]:
        """
        Get products
        :param code: optional code to match
        :param name: optional name to match
        :param type: optional code to match
        :return: list of products
        """
        params = {
            "size": 200,
        }
        if type:
            params["type"] = type.value
        else:
            params["type"] = ProductType.SALES.value
        if code:
            params["code"] = code
        if name:
            params["name"] = name
        return [
            Product.from_dict(item)
            for item in self.get_paginated("/products", params=params)
        ]

    def post_product(
        self,
        product: Product
    ) -> Product:
        """
        Create new product
        """

        data = product.as_dict()
        result = self.post("/products", json=data)
        if result.status_code != 200:
            logger.error(
                "Failed to create product, status %s, content: %s",
                result.status_code, result.content
            )
            raise ProcountorAPIException("Failed to create product: %s", result.content)
        response = result.json()
        return Product.from_dict(response)

    def get_product_groups(
        self,
        name: typing.Optional[str] = None,
        type: ProductType = None
    ) -> List[ProductGroup]:
        """
        Get product groups
        :param name: optional name to match
        :param type: optional code to match
        :return: list of products
        """
        params = {
            "size": 200,
        }
        if type:
            params["type"] = type.value
        else:
            params["type"] = ProductType.SALES.value
        if name:
            params["name"] = name
        response = self.get_json("/products/groups", params=params, name="Product Groups")
        print(response)
        return [
            ProductGroup.from_dict(item)
            for item in response["productGroups"]
        ]

    def post_product_group(
        self,
        product_group: ProductGroup
    ) -> ProductGroup:
        """
        Create new product group
        """

        data = product_group.as_dict()
        result = self.post("/products/groups", json=data)
        if result.status_code != 200:
            logger.error(
                "Failed to create product group, status %s, content: %s",
                result.status_code, result.content
            )
            raise ProcountorAPIException("Failed to create product group: %s", result.content)
        response = result.json()
        return ProductGroup.from_dict(response)

    def get_business_partner(self, partner_id: int) -> BusinessPartner:
        """
        Get business partner by id
        :param partner_id: partner id in Payment Gateway
        :return: BusinessPartner object
        """
        result = self.get(f"/businesspartners/{partner_id}")
        if result.status_code == 200:
            logger.debug("Business partner %s: %s", (partner_id, result.content))
            return BusinessPartner.from_dict(simplejson.loads(result.content, use_decimal=True))
        raise ProcountorAPIException("Getting business partner failed")

    def get_dimensions(self) -> List[Dimension]:
        """
        Get dimensions from procountor
        :return:
        """
        result = self.get("/dimensions/")
        if result.status_code != 200:
            logger.error(
                "Failed to get dimensions, status %s, content: %s",
                result.status_code, result.content
            )
            return []
        logger.debug("dimensions: %s", result.content)
        return [
            Dimension.from_dict(item)
            for item in result.json()
        ]

    def get_ledger_receipt(self, ledger_receipt_id) -> LedgerReceipt:
        """
        Get ledger receipt by id
        :param ledger_receipt_id: ledger_receipt_id
        :return: LedgerReceipt object
        """
        result = self.get(f"/ledgerreceipts/{ledger_receipt_id}")
        if result.status_code == 200:
            return LedgerReceipt.from_dict(simplejson.loads(result.content, use_decimal=True))
        raise ProcountorAPIException("Getting ledger receipt")

    def put_ledger_receipt(self, ledger_receipt: LedgerReceipt):
        """
        Update ledger receipt
        :param ledger_receipt: Ledger receipt to update
        :return: LedgerReceipt object
        """
        data = ledger_receipt.as_dict()
        result = self.put(f"/ledgerreceipts/{ledger_receipt.id}", json=data)
        if result.status_code != 200:
            logger.error(
                "Failed to update ledger receipt, status %s, content: %s",
                result.status_code, result.content
            )
            raise ProcountorAPIException("Failed to update ledgerreceipt: %s", result.content)
        response = result.json()
        return LedgerReceipt.from_dict(response)

    def get_ledger_receipts(
        self,
        start: Optional[date] = None,
        end: Optional[date] = None,
        types: Optional[List] = None,
        order_by_date: Optional[str] = None,
    ) -> List[LedgerReceipt]:
        """
        GET /ledgerreceipts
        :return:
        """
        if not types:
            types = ["JOURNAL"]
        params = {"size": 50, "types": ",".join(types), "page": 0}
        if start is not None:
            params["startDate"] = start.strftime("%Y-%m-%d")
        if end is not None:
            params["endDate"] = end.strftime("%Y-%m-%d")
        if order_by_date is not None:
            params["orderByDate"] = order_by_date
        results = []
        while True:
            response = self.get("/ledgerreceipts", params=params)
            if response.status_code != 200:
                raise ProcountorAPIException("Failed to get ledger receipts: %s", response.content)
            result = response.json(use_decimal=True).get("results", [])
            if len(result) == 0:
                break
            results += [LedgerReceipt.from_dict(item) for item in result]
            params["page"] += 1
        return results

    def get_dimension(self, dimension_id) -> Dimension:
        response = self.get(f"/dimensions/{dimension_id}")
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to get dimension %s: %s", dimension_id, response.content)
        return Dimension.from_dict(response.json(use_decimal=True))

    def post_dimension_item(self, dimension_id: int, item: DimensionItem) -> DimensionItem:
        """
        POST new dimension item
        :return:
        """
        response = self.post(f"/dimensions/{dimension_id}/items", json=item.as_dict())
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to post dimension item: %s", response.content)
        return DimensionItem.from_dict(response.json(use_decimal=True))

    def get_coa(self) -> List[LedgerAccount]:
        """
        GET Cart Of Accounts (COA)
        :return:
        """
        response = self.get("/coa")
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to get cart of accounts: %s", response.content)
        data = response.json(use_decimal=True)
        if "ledgerAccounts" not in data:
            raise ProcountorAPIException("No ledgerAccounts in response!")
        return [LedgerAccount.from_dict(account) for account in data["ledgerAccounts"]]

    def invalidate_ledger_receipt(self, ledger_receipt_id) -> InfoMessage:
        response = self.put(f"/ledgerreceipts/{ledger_receipt_id}/invalidate")
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to invalidate ledger receipt: %s", response.content)
        return InfoMessage.from_dict(response.json())

    def unfinish_ledger_receipt(self, ledger_receipt_id) -> InfoMessage:
        response = self.put(f"/ledgerreceipts/{ledger_receipt_id}/unfinished")
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to unfinish ledger receipt: %s", response.content)
        return InfoMessage.from_dict(response.json())

    def post_ledger_receipt(self, ledge_receipt: LedgerReceipt) -> LedgerReceipt:
        """
        Post new ledger receipt
        :param ledge_receipt: Ledger receipt to post
        :return: Created ledger receipt
        """
        response = self.post(
            "/ledgerreceipts",
            params={"createReconciliation": "true"},
            json=ledge_receipt.as_dict(),
        )
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to post ledger receipt: %s", response.content)
        return LedgerReceipt.from_dict(response.json(use_decimal=True))

    def get_employee_salaryinfo(self, employee_id: int) -> SalaryInfo:
        """
        GET /payrolls/employees/<id>/salaryinfo
        Returns employeeId, personId and salary/insurance configuration.
        :param employee_id: ID of the employee
        :return: SalaryInfo object
        """
        response = self.get(f"/payrolls/employees/{employee_id}/salaryinfo")
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to get salaryinfo for employee %s: %s", employee_id, response.content)
        return SalaryInfo.from_dict(response.json(use_decimal=True))

    def get_persons(
        self,
        name: Optional[str] = None,
        person_number: Optional[str] = None,
    ) -> List[PersonBasicInfo]:
        """
        GET /persons

        :return: List of persons
        """
        params = {"size": 200, "page": 0}
        if name is not None:
            params["name"] = name
        if person_number is not None:
            params["personNumber"] = person_number

        results = [PersonBasicInfo.from_dict(item) for item in self.get_paginated("/persons", params=params)]
        return results

    def get_person(self, person_id: int) -> Person:
        """
        GET /persons/<id>
        :param person_id: ID of the person
        :return: Person object
        """
        response = self.get(f"/persons/{person_id}")
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to get person %s: %s", person_id, response.content)
        return Person.from_dict(response.json(use_decimal=True))

    def get_salaryslips(
        self,
        start: Optional[date] = None,
        end: Optional[date] = None,
        name: Optional[str] = None,
        slip_number: Optional[List[str]] = None
    ) -> List[SalarySlip]:
        """
        GET /payrolls/salaryslips
        :return: List of SalarySlip objects
        """
        types = [
            "UNFINISHED",
            "APPROVED",
            "CORRECTION",
            "INVALIDATED",
            "PAYMENT_QUEUED",
            "PAYMENT_SENT_TO_BANK",
            "PAID",
            "PARTLY_PAID",
            "MARKED_PAID",
            "EARNINGS_REPORTED"
        ]

        params = {"size": 200, "types": ",".join(types), "page": 0}
        params["orderById"] = "DESC"

        if start is not None:
            params["paydayStartDate"] = start.strftime("%Y-%m-%d")
        if end is not None:
            params["paydayEndDate"] = end.strftime("%Y-%m-%d")
        if name is not None:
            params["employeeName"] = name
        if slip_number is not None:
            # Support both single string and list of strings
            if isinstance(slip_number, list):
                params["slipNumber"] = ",".join(slip_number)
            else:
                params["slipNumber"] = slip_number

        results = self.get_paginated("/payrolls/salaryslips", params=params)
        return [SalarySlip.from_dict(r) for r in results]

    def get_salaryslip(self, slip_id: int) -> SalarySlip:
        """
        GET /payrolls/salaryslips/<id>
        :param slip_id: ID of the salary slip
        :return: SalarySlip object
        """
        response = self.get(f"/payrolls/salaryslips/{slip_id}")
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to get salaryslip %s: %s", slip_id, response.content)
        return SalarySlip.from_dict(response.json(use_decimal=True))

    def get_salaryslip_accounting(self, slip_id) -> SalarySlipAccounting:
        """
        GET /payrolls/salaryslips/<id>/accounting
        :return: SalarySlipAccounting object
        """
        response = self.get(f"/payrolls/salaryslips/{slip_id}/accounting")
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to get salaryslip %s: %s", slip_id, response.content)
        return SalarySlipAccounting.from_dict(response.json(use_decimal=True))

    def put_payrolls_salaryslips_accounting(
        self,
        slip_id: int,
        salary_slip_accounting: SalarySlipAccounting,
        create_reconciliation: Optional[bool] = None,
    ) -> SalarySlipAccounting:
        """
        PUT /payrolls/salaryslips/<id>/accounting
        Updates salary slip accounting and returns it.
        :param slip_id: ID of the salary slip
        :param salary_slip_accounting: Salary slip accounting data to update
        :param create_reconciliation: Enable automatic generation of reconciliation row
        :return: Updated SalarySlipAccounting object
        """
        params = {}
        if create_reconciliation is not None:
            params["createReconciliation"] = str(create_reconciliation).lower()
        response = self.put(
            f"/payrolls/salaryslips/{slip_id}/accounting",
            params=params,
            json=salary_slip_accounting.as_dict(),
        )
        if response.status_code != 200:
            raise ProcountorAPIException(
                "Failed to update salaryslip accounting %s: %s", slip_id, response.content
            )
        return SalarySlipAccounting.from_dict(response.json(use_decimal=True))

    def get_sessioninfo(self) -> SessionInfo:
        """
        GET /sessioninfo
        Returns basic information about the current session.
        :return: SessionInfo object
        """
        response = self.get("/sessioninfo")
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to get sessioninfo: %s", response.content)
        return SessionInfo.from_dict(response.json(use_decimal=True))

    def get_company(self) -> Company:
        """
        GET /company
        Returns basic information of the currently logged in company.
        :return: Company object
        """
        response = self.get("/company")
        if response.status_code != 200:
            raise ProcountorAPIException("Failed to get company info: %s", response.content)
        return Company.from_dict(response.json(use_decimal=True))
