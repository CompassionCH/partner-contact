import logging
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase

logger = logging.getLogger(__name__)


class TestSmartTagger(TransactionCase):
    @classmethod
    def setUpClass(cls):
        """Load test data."""
        super().setUpClass()

        # Create new partner records for testing
        cls.michel_fletcher = cls.env["res.partner"].create({
            "name": "Michel Fletcher",
            "email": "michel.fletcher@example.com",
            "is_company": False,
        })
        cls.chao_wang = cls.env["res.partner"].create({
            "name": "Chao Wang",
            "email": "chao.wang@example.com",
            "is_company": False,
        })
        cls.david_simpson = cls.env["res.partner"].create({
            "name": "David Simpson",
            "email": "david.simpson@example.com",
            "is_company": False,
        })
        cls.john_m_brown = cls.env["res.partner"].create({
            "name": "John M. Brown",
            "email": "john.brown@example.com",
            "is_company": False,
        })
        cls.charlie_bernard = cls.env["res.partner"].create({
            "name": "Charlie Bernard",
            "email": "charlie.bernard@example.com",
            "is_company": False,
        })

        # Combine all created partners into a single recordset
        cls.partners = (
            cls.michel_fletcher |
            cls.chao_wang |
            cls.david_simpson |
            cls.john_m_brown |
            cls.charlie_bernard
        )

    def create_condition(self):
        """
        Create a condition, which filters all objects containing the letter 'o'
        in their name.
        """
        model_res_partner = self.env.ref('base.model_res_partner')
        return self.env["ir.filters"].create(
            {
                "user_id": False,
                "model_id": model_res_partner.id,
                "active": True,
                "domain": [["name", "ilike", "o"]],
                "context": {},
                "sort": [],
                "name": "SmartTagTestCondition",
                "is_default": False,
                "action_id": False,
            }
        )

    def create_tag(self):
        """
        Create a smart tag, which tags all partners containing the letter 'o'
        in their name.
        """
        return self.env["res.partner.category"].create(
            {
                "name": "Test Smart Tag",
                "active": True,
                "smart": True,
                "parent_id": False,
                "author_id": False,
                "department_ids": False,
                "description": "",
                "valid_until": fields.Date.today(),
                "tag_filter_partner_field": "partner_id",
                "tag_filter_condition_id": self.create_condition().id,
            }
        )

    def test_create_tag(self):
        """
        Tag all partners which have the letter 'o' in the name.
        """
        smart_tag = self.create_tag()
        for partner in self.partners.filtered(lambda t: "o" in t.name.lower()):
            self.assertTrue(partner in smart_tag.partner_ids,
                            f"Partner {partner.name} should be tagged.")

        for partner in self.partners.filtered(lambda t: "o" not in t.name.lower()):
            self.assertFalse(partner in smart_tag.partner_ids,
                             f"Partner {partner.name} should not be tagged.")

        for partner in smart_tag.partner_ids:
            self.assertIn("o", partner.name.lower(),
                          f"Tagged partner {partner.name} does not contain 'o'.")

    def test_modify_partner(self):
        """
        Tag partners with the letter 'o' in the name.
        Then edit some name and check whether the smart tag updates
        """

        smart_tag = self.create_tag()

        # Update some first names
        michael = self.michel_fletcher
        michael.update({"name": "Michel Angelo"})

        # Simulate a cron trigger
        self.env["res.partner.category"].update_all_smart_tags()

        # Verify that the updated tag contains the partner 'Michel Angelo'
        self.assertTrue(michael in smart_tag.partner_ids,
                        "Michel Angelo should be tagged after name update.")

        for partner in smart_tag.partner_ids:
            self.assertIn("o", partner.name.lower(),
                          f"Tagged partner {partner.name} does not contain 'o'.")

    def test_smart_tag_sql(self):
        """Test query SQL for smart tags"""
        smart_tag = self.env["res.partner.category"].create(
            {
                "name": "Test Smart Tag SQL",
                "active": True,
                "smart": True,
                "parent_id": False,
                "tag_filter_sql_query": """
                SELECT id
                FROM res_partner
                WHERE LOWER(name) LIKE '%%o%%'
                """,
            }
        )
        # Update some first names
        michael = self.michel_fletcher
        michael.write({"name": "Michel Angelo"})

        # Trigger tag update
        smart_tag.update_partner_tags()

        # Verify that the updated tag contains the partner 'Michel Angelo'
        self.assertTrue(michael in smart_tag.partner_ids,
                        "Michel Angelo should be tagged after SQL update.")

        for partner in smart_tag.partner_ids:
            self.assertTrue("o" in partner.name.lower(),
                            f"Tagged partner {partner.name} does not contain 'o'.")

    def test_check_validity_dates(self):
        """
        Test if the valid_until functionality works correctly
        """
        # Create a new tag with a 'valid_until' date set to yesterday
        yesterday = fields.Date.today() - timedelta(days=1)

        expired_tag = self.create_tag()
        expired_tag.write({"valid_until": yesterday})
        expired_tag.update_partner_tags()

        # Reload the tags from the database
        expired_tag.invalidate_recordset()

        # Check that the expired tag is now inactive
        self.assertFalse(expired_tag.active, "Expired tag should be inactive.")
        # Check that the partner isn't tagged
        self.assertFalse(self.david_simpson in expired_tag.partner_ids,
                         "David Simpson should not be tagged by an expired tag.")

        # Modify the tag with a 'valid_until' date set to tomorrow
        tomorrow = fields.Date.today() + timedelta(days=1)
        active_tag = expired_tag
        active_tag.write({"valid_until": tomorrow, "active": True})

        # Run the method which is supposed to deactivate expired tags
        self.env["res.partner.category"]._check_validity_dates()

        # Invalidate cache for the specific record
        active_tag.invalidate_recordset()

        # Check that the active tag is still active
        self.assertTrue(active_tag.active, "Active tag should remain active.")
