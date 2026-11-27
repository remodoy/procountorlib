import copy
import logging
import unittest
from unittest import mock

from procountorlib.procountorlib import (
    BusinessPartner,
    BusinessPartnerAddress,
    CounterPartyAddress,
    Country,
    Invoice,
    InvoicePhysicalAddress,
    ProcountorAPIClient,
    ProcountorAPIValidationError,
)

COMPLETE_ADDRESS = {
    "name": "Asiakas Oy",
    "specifier": "Laskutus",
    "street": "Katu 1",
    "zip": "00100",
    "city": "Helsinki",
    "country": "FINLAND",
    "subdivision": "Uusimaa",
}


def partner_data(**extra):
    data = {"id": 1, "name": "Asiakas Oy", "type": "CUSTOMER"}
    data.update(extra)
    return data


def invoice_data(**extra):
    data = {
        "id": 1,
        "type": "SALES_INVOICE",
        "status": "UNFINISHED",
        "date": "2026-11-26",
        "invoiceRows": [],
        "vatStatus": 1,
        "invoiceChannel": "EMAIL",
        "discountPercent": 0,
        "language": "FINNISH",
    }
    data.update(extra)
    return data


class BusinessPartnerAddressTest(unittest.TestCase):
    def test_complete_address(self):
        address = BusinessPartnerAddress.from_dict(COMPLETE_ADDRESS)
        self.assertEqual(address.name, "Asiakas Oy")
        self.assertEqual(address.specifier, "Laskutus")
        self.assertEqual(address.street, "Katu 1")
        self.assertEqual(address.zip, "00100")
        self.assertEqual(address.city, "Helsinki")
        self.assertEqual(address.country, Country.FINLAND)
        self.assertEqual(address.subdivision, "Uusimaa")
        self.assertEqual(address.as_dict(), COMPLETE_ADDRESS)

    def test_address_without_name(self):
        address = BusinessPartnerAddress.from_dict({"street": "Katu 1", "country": None})
        self.assertIsNone(address.name)
        self.assertEqual(address.street, "Katu 1")
        self.assertIsNone(address.country)
        self.assertEqual(address.as_dict(), {"street": "Katu 1"})


class BusinessPartnerTest(unittest.TestCase):
    def test_complete_addresses(self):
        partner = BusinessPartner.from_dict(partner_data(
            address=copy.deepcopy(COMPLETE_ADDRESS),
            billingAddress=copy.deepcopy(COMPLETE_ADDRESS),
            deliveryAddress=copy.deepcopy(COMPLETE_ADDRESS),
        ))
        for address in (partner.address, partner.billing_address, partner.delivery_address):
            self.assertEqual(address.as_dict(), COMPLETE_ADDRESS)

    def test_missing_addresses(self):
        partner = BusinessPartner.from_dict(partner_data())
        self.assertIsNone(partner.address)
        self.assertIsNone(partner.billing_address)
        self.assertIsNone(partner.delivery_address)

    def test_empty_addresses(self):
        all_null = {key: None for key in COMPLETE_ADDRESS}
        for empty in ({}, None, all_null, {"name": ""}):
            with self.subTest(empty=empty):
                partner = BusinessPartner.from_dict(partner_data(
                    address=empty, billingAddress=empty, deliveryAddress=empty,
                ))
                self.assertIsNone(partner.address)
                self.assertIsNone(partner.billing_address)
                self.assertIsNone(partner.delivery_address)

    def test_empty_billing_address_keeps_address(self):
        partner = BusinessPartner.from_dict(partner_data(
            address=copy.deepcopy(COMPLETE_ADDRESS), billingAddress={},
        ))
        self.assertEqual(partner.address.name, "Asiakas Oy")
        self.assertIsNone(partner.billing_address)

    def test_billing_address_without_name(self):
        partner = BusinessPartner.from_dict(partner_data(
            billingAddress={"street": "Katu 1", "zip": "00100", "city": "Helsinki"},
        ))
        self.assertIsNone(partner.billing_address.name)
        self.assertEqual(partner.billing_address.street, "Katu 1")
        self.assertEqual(partner.billing_address.zip, "00100")
        self.assertEqual(partner.billing_address.city, "Helsinki")
        self.assertIsNone(partner.billing_address.specifier)
        self.assertIsNone(partner.billing_address.country)


class InvoicePhysicalAddressTest(unittest.TestCase):
    def test_complete_address(self):
        address = InvoicePhysicalAddress.from_dict(COMPLETE_ADDRESS)
        self.assertEqual(address.name, "Asiakas Oy")
        self.assertEqual(address.country, Country.FINLAND)
        self.assertEqual(address.as_dict(), COMPLETE_ADDRESS)

    def test_address_without_name(self):
        address = InvoicePhysicalAddress.from_dict({"street": "Katu 1"})
        self.assertIsNone(address.name)
        self.assertEqual(address.street, "Katu 1")
        self.assertEqual(address.as_dict(), {"street": "Katu 1"})

    def test_copy(self):
        address = copy.deepcopy(InvoicePhysicalAddress.from_dict(COMPLETE_ADDRESS))
        self.assertEqual(address.as_dict(), COMPLETE_ADDRESS)


class CounterPartyAddressTest(unittest.TestCase):
    def test_complete_address(self):
        address = CounterPartyAddress.from_dict(COMPLETE_ADDRESS)
        self.assertEqual(address.as_dict(), COMPLETE_ADDRESS)

    def test_name_is_mandatory(self):
        # The API requires name in counterPartyAddress, unlike in other addresses
        data = {key: value for key, value in COMPLETE_ADDRESS.items() if key != "name"}
        with self.assertRaises(ProcountorAPIValidationError):
            CounterPartyAddress.from_dict(data)


class InvoiceTest(unittest.TestCase):
    def test_complete_addresses(self):
        invoice = Invoice.from_dict(invoice_data(
            billingAddress=copy.deepcopy(COMPLETE_ADDRESS),
            deliveryAddress=copy.deepcopy(COMPLETE_ADDRESS),
        ))
        self.assertEqual(invoice.billing_address.as_dict(), COMPLETE_ADDRESS)
        self.assertEqual(invoice.delivery_address.as_dict(), COMPLETE_ADDRESS)

    def test_empty_addresses(self):
        for empty in ({}, None, {"name": None, "street": None}):
            with self.subTest(empty=empty):
                invoice = Invoice.from_dict(invoice_data(
                    billingAddress=empty, deliveryAddress=empty,
                ))
                self.assertIsNone(invoice.billing_address)
                self.assertIsNone(invoice.delivery_address)

    def test_address_without_name(self):
        invoice = Invoice.from_dict(invoice_data(
            billingAddress={"street": "Katu 1"}, deliveryAddress={"city": "Helsinki"},
        ))
        self.assertIsNone(invoice.billing_address.name)
        self.assertEqual(invoice.billing_address.street, "Katu 1")
        self.assertIsNone(invoice.delivery_address.name)
        self.assertEqual(invoice.delivery_address.city, "Helsinki")


class GetBusinessPartnerTest(unittest.TestCase):
    def test_debug_logging_and_empty_billing_address(self):
        client = ProcountorAPIClient.__new__(ProcountorAPIClient)
        response = mock.Mock(
            status_code=200,
            content=b'{"id": 1, "name": "Asiakas Oy", "type": "CUSTOMER", "billingAddress": {}}',
        )
        errors = []
        handler = logging.Handler()
        handler.handleError = errors.append
        handler.emit = lambda record: record.getMessage()
        logger = logging.getLogger("ProcountorAPI")
        logger.addHandler(handler)
        old_level = logger.level
        logger.setLevel(logging.DEBUG)
        try:
            with mock.patch.object(client, "get", return_value=response, create=True):
                partner = client.get_business_partner(1)
        finally:
            logger.setLevel(old_level)
            logger.removeHandler(handler)
        self.assertIsNone(partner.billing_address)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
